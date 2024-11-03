import time
import argparse
import threading
import queue
from datetime import datetime
import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import json

from config import (
    NETWORK_CHECK_INTERVAL,
    SENSOR2_WAIT_TIME,
    UI_REFRESH_RATE,
    IMAGE_URL
)

from core.hardware import GPIOController
from core.network import NetworkManager
from core.processing import ImageProcessor
from ui.fb_ui import FramebufferUI

class InspectionSystem:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Initialize basic metrics and state
        self.metrics = {
            'processed_count': 0,
            'error_count': 0,
            'start_time': datetime.now(),
            'last_process_time': None,
            'total_errors': 0
        }
        
        # Initialize components
        try:
            self.gpio = GPIOController()
            self.network = NetworkManager()
            self.ui = FramebufferUI()
            
            # Initialize ImageProcessor with Roboflow credentials
            self.roboflow_api_key = os.getenv('ROBOFLOW_API_KEY')
            self.roboflow_model_id = os.getenv('ROBOFLOW_MODEL_ID')
            
            if not self.roboflow_api_key or not self.roboflow_model_id:
                raise ValueError(
                    "Missing Roboflow credentials. Please set ROBOFLOW_API_KEY and "
                    "ROBOFLOW_MODEL_ID environment variables."
                )
            
            self.processor = ImageProcessor(
                api_key=self.roboflow_api_key,
                model_id=self.roboflow_model_id,
                status_callback=self.ui.update_status_message
            )
        except Exception as e:
            if hasattr(self, 'gpio'):
                self.gpio.cleanup()
            if hasattr(self, 'ui'):
                self.ui.cleanup()
            raise
        
        # State variables (keeping original ones)
        self.piece_in_progress = False
        self.waiting_for_sensor2 = False
        self.sensor2_check_time = None
        self.last_network_check = time.time()
        self.processing_thread = None
        self.running = True
        self.analysis_in_progress = False
        
        # Solenoid timing variables (from original)
        self.solenoid_deactivation_time = None
        self.solenoid_activation_time = None
        self.SOLENOID_DELAY_MS = 500
        self.SOLENOID_START_DELAY_MS = 300
        self.last_sensor1_state = False

        # Enhanced error tracking
        self.error_count = 0
        self.last_error = None
        self.last_successful_process = None
        
        # Processing history
        self.results_history = []
        self.MAX_HISTORY = 100

    def process_piece(self):
        """Process a piece with enhanced metrics tracking"""
        self.analysis_in_progress = True
        self.ui.start_processing()  # Start timing the process
        
        try:
            self.ui.update_status_message("=== Starting piece processing ===")
            
            # Get image
            image_data = self.processor.get_image(IMAGE_URL)
            if not image_data:
                raise Exception("Failed to capture image")
            
            # Update UI with image
            self.ui.update_image(image_data)
            
            # Analyze image
            results = self.processor.analyze_image(image_data)
            
            if results:
                processing_time = time.time() - self.ui.metrics['current_processing_start']
                self.metrics['processed_count'] += 1
                self.last_successful_process = datetime.now()
                
                # Update UI with results and processing time
                self.ui.update_metrics(results=results, processing_time=processing_time)
                self.ui.update_predictions(results)
                
            else:
                raise Exception("Analysis failed to produce results")
                
        except Exception as e:
            self.metrics['error_count'] += 1
            self.last_error = str(e)
            processing_time = time.time() - self.ui.metrics['current_processing_start']
            self.ui.update_metrics(error=str(e), processing_time=processing_time)
            self.ui.update_status_message(f"Processing error: {str(e)}", is_alert=True)
            
        finally:
            self.analysis_in_progress = False
            self.ui.current_status['state'] = 'normal'
            self.ui.current_status['alert'] = None

    def run_state_machine(self):
        """Main state machine logic with error handling"""
        try:
            current_time = time.time()
            
            # Periodic network checks
            if current_time - self.last_network_check > NETWORK_CHECK_INTERVAL:
                self.network.check_all()
                self.last_network_check = current_time

            # Handle solenoid timing
            current_sensor1_state = self.gpio.read_sensor1()
            
            # Detect edges
            if self.last_sensor1_state and not current_sensor1_state:
                self.solenoid_deactivation_time = time.time()
                
            if not self.last_sensor1_state and current_sensor1_state:
                self.solenoid_activation_time = time.time()
            
            self.last_sensor1_state = current_sensor1_state

            # Determine solenoid state
            should_activate = self._calculate_solenoid_state(
                current_sensor1_state,
                current_time
            )
            
            # Set solenoid state
            self.gpio.set_solenoid(should_activate)

            # Handle piece processing
            if not self.analysis_in_progress:
                self._handle_piece_processing(current_sensor1_state)
                
        except Exception as e:
            self.metrics['total_errors'] += 1
            self.ui.update_status_message(f"State machine error: {str(e)}", is_alert=True)

    def _calculate_solenoid_state(self, sensor1_state: bool, current_time: float) -> bool:
        """Calculate whether solenoid should be active"""
        if sensor1_state:
            if self.solenoid_activation_time is not None:
                elapsed_ms = (current_time - self.solenoid_activation_time) * 1000
                return elapsed_ms >= self.SOLENOID_START_DELAY_MS
        elif self.solenoid_deactivation_time is not None:
            elapsed_ms = (current_time - self.solenoid_deactivation_time) * 1000
            return elapsed_ms < self.SOLENOID_DELAY_MS
        
        return False

    def _handle_piece_processing(self, sensor1_state: bool):
        """Handle piece processing logic"""
        if self.ui.current_status['state'] == 'normal':
            if sensor1_state and not self.piece_in_progress:
                self.piece_in_progress = True
                self.ui.update_status_message("Piece detected")
                self.waiting_for_sensor2 = False
                self.ui.current_status['alert'] = None
            
            if self.piece_in_progress:
                if not sensor1_state:
                    if not self.waiting_for_sensor2:
                        self.waiting_for_sensor2 = True
                        self.sensor2_check_time = time.time()
                    
                    if self.waiting_for_sensor2 and (time.time() - self.sensor2_check_time) > SENSOR2_WAIT_TIME:
                        if not self.gpio.read_sensor2():
                            self.ui.current_status['alert'] = "No piece fell in slot!"
                            self.ui.current_status['state'] = 'error_recovery'
                        else:
                            if not self.processing_thread or not self.processing_thread.is_alive():
                                self.processing_thread = threading.Thread(
                                    target=self.process_piece
                                )
                                self.processing_thread.start()
                        
                        self.piece_in_progress = False
                        self.waiting_for_sensor2 = False

        elif self.ui.current_status['state'] == 'error_recovery':
            if sensor1_state:
                self.ui.current_status['state'] = 'normal'
                self.piece_in_progress = True
                self.waiting_for_sensor2 = False
                self.ui.current_status['alert'] = None
            elif self.gpio.read_sensor2():
                if not self.processing_thread or not self.processing_thread.is_alive():
                    self.processing_thread = threading.Thread(
                        target=self.process_piece
                    )
                    self.processing_thread.start()
                self.ui.current_status['state'] = 'normal'
                self.piece_in_progress = False
                self.waiting_for_sensor2 = False

    def run(self):
        """Main run loop with error handling"""
        try:
            while self.running:
                self.run_state_machine()
                self.ui.update_display(self.gpio, self.network)
                time.sleep(UI_REFRESH_RATE)
                
        except KeyboardInterrupt:
            self.ui.update_status_message("Shutdown requested...")
        except Exception as e:
            self.ui.update_status_message(f"Critical error: {str(e)}", is_alert=True)
        finally:
            self.cleanup()

    def cleanup(self):
        """Enhanced cleanup with state saving"""
        self.running = False
        
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2.0)
        
        if hasattr(self, 'gpio'):
            self.gpio.cleanup()
        
        if hasattr(self, 'ui'):
            self.ui.cleanup()
        
        # Save final state
        try:
            end_time = datetime.now()
            run_time = (end_time - self.metrics['start_time']).total_seconds()
            
            final_state = {
                'metrics': {
                    'processed_count': self.metrics['processed_count'],
                    'error_count': self.metrics['error_count'],
                    'total_errors': self.metrics['total_errors'],
                    'run_time_seconds': run_time,
                    'average_process_time': self.metrics.get('last_process_time', 0),
                },
                'last_run': end_time.isoformat(),
                'last_error': self.last_error
            }
            
            with open('system_state.json', 'w') as f:
                json.dump(final_state, f, indent=2)
                
        except Exception as e:
            print(f"Failed to save system state: {e}")

def main():
    try:
        system = InspectionSystem()
        system.run()
    except Exception as e:
        print(f"Failed to start system: {str(e)}")
        return 1
    return 0

if __name__ == "__main__":
    exit(main())