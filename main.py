import curses
import time
import argparse
import threading
from datetime import datetime
import os
from dotenv import load_dotenv

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

# Load environment variables
load_dotenv()

class InspectionSystem:
    def __init__(self):
        # Initialize components
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
        
        # State variables
        self.piece_in_progress = False
        self.waiting_for_sensor2 = False
        self.sensor2_check_time = None
        self.last_network_check = 0
        self.processing_thread = None
        self.running = True
        self.analysis_in_progress = False
        
        # Solenoid timing variables
        self.solenoid_deactivation_time = None
        self.solenoid_activation_time = None
        self.SOLENOID_DELAY_MS = 500
        self.SOLENOID_START_DELAY_MS = 300
        self.last_sensor1_state = False

    def process_piece(self):
        """Process a piece with UI updates"""
        self.analysis_in_progress = True  # Set analysis flag
        self.ui.update_status_message("=== Starting piece processing ===")
        
        try:
            # Early return to skip processing
            self.ui.current_status['last_inference'] = datetime.now().strftime("%H:%M:%S")
            self.ui.current_status['last_confidence'] = 0.0
            self.ui.update_status_message("Processing skipped")
            return
            # First get the image using the processor with IMAGE_URL
            image_data = self.processor.get_image(IMAGE_URL)
            if image_data:
                # Update the UI with the image first
                self.ui.update_image(image_data)
                
                # Then analyze the image
                success = False
                results = None
                
                if results := self.processor.analyze_image(image_data):
                    success = True
                
                if success and results:
                    self.ui.current_status['last_inference'] = datetime.now().strftime("%H:%M:%S")
                    
                    # Update predictions in UI
                    self.ui.update_predictions(results)
                    
                    # Get the highest confidence prediction
                    if results['predictions']:
                        best_pred = results['summary']['best_prediction']
                        self.ui.current_status['last_confidence'] = best_pred['confidence']
                        self.ui.update_status_message(
                            f"Analysis complete - {best_pred['class_name']} "
                            f"({best_pred['confidence']:.1%} confidence)"
                        )
                    else:
                        self.ui.update_status_message("Analysis complete - no detections")
                        self.ui.current_status['last_confidence'] = 0.0
                else:
                    self.ui.update_status_message("Analysis failed", is_alert=True)
                    self.ui.current_status['last_confidence'] = 0.0
            else:
                self.ui.update_status_message("Failed to capture image", is_alert=True)
                
        except Exception as e:
            self.ui.update_status_message(f"Processing error: {str(e)}", is_alert=True)
            self.ui.current_status['last_confidence'] = 0.0
        finally:
            self.analysis_in_progress = False  # Clear analysis flag
            self.ui.update_status_message("=== Piece processing complete ===")
            self.ui.current_status['state'] = 'normal'
            self.ui.current_status['alert'] = None

    def run_state_machine(self):
        """Main state machine logic"""
        try:
            current_time = time.time()
            
            # Periodic network checks
            if current_time - self.last_network_check > NETWORK_CHECK_INTERVAL:
                self.network.check_all()
                self.last_network_check = current_time

            # Handle solenoid timing independent of state
            current_sensor1_state = self.gpio.read_sensor1()
            
            # Detect falling edge of sensor1
            if self.last_sensor1_state and not current_sensor1_state:
                self.solenoid_deactivation_time = time.time()
                self.ui.update_status_message(f"Sensor1 deactivated - starting {self.SOLENOID_DELAY_MS}ms countdown")
            
            # Detect rising edge of sensor1
            if not self.last_sensor1_state and current_sensor1_state:
                self.solenoid_activation_time = time.time()
                self.ui.update_status_message(f"Sensor1 activated - waiting {self.SOLENOID_START_DELAY_MS}ms before solenoid")
            
            # Update last sensor state
            self.last_sensor1_state = current_sensor1_state

            # Determine if solenoid should be active - independent of system state
            should_activate = False
            
            if current_sensor1_state:
                # Check if the initial delay has passed
                if self.solenoid_activation_time is not None:
                    elapsed_ms = (time.time() - self.solenoid_activation_time) * 1000
                    if elapsed_ms >= self.SOLENOID_START_DELAY_MS:
                        should_activate = True
                        if elapsed_ms < self.SOLENOID_START_DELAY_MS + 100:  # Only show message once
                            self.ui.update_status_message("Activating solenoid")
                    else:
                        self.ui.update_status_message(f"Waiting for initial delay - {int(self.SOLENOID_START_DELAY_MS - elapsed_ms)}ms remaining")
            elif self.solenoid_deactivation_time is not None:
                # Calculate time since deactivation
                elapsed_ms = (time.time() - self.solenoid_deactivation_time) * 1000
                should_activate = elapsed_ms < self.SOLENOID_DELAY_MS
                
                if should_activate:
                    self.ui.update_status_message(f"Holding solenoid - {int(self.SOLENOID_DELAY_MS - elapsed_ms)}ms remaining")
            
            # Set solenoid state based on timing logic
            self.gpio.set_solenoid(should_activate)

            # If analysis is in progress, ignore new pieces
            if self.analysis_in_progress:
                self.ui.update_status_message("Analysis in progress - waiting before accepting new pieces")
                return

            # State machine
            if self.ui.current_status['state'] == 'normal':
                if current_sensor1_state and not self.piece_in_progress:
                    self.piece_in_progress = True
                    self.ui.update_status_message("Piece detected")
                    self.waiting_for_sensor2 = False
                    self.ui.current_status['alert'] = None
                
                if self.piece_in_progress:
                    if not current_sensor1_state:
                        if not self.waiting_for_sensor2:
                            self.waiting_for_sensor2 = True
                            self.sensor2_check_time = time.time()
                            self.ui.update_status_message("Sensor 1 released - waiting for piece to reach slot...")
                        
                        if self.waiting_for_sensor2 and (time.time() - self.sensor2_check_time) > SENSOR2_WAIT_TIME:
                            if not self.gpio.read_sensor2():
                                self.ui.update_status_message("No piece fell in slot!", is_alert=True)
                                self.ui.current_status['alert'] = "No piece fell in slot!"
                                self.ui.current_status['state'] = 'error_recovery'
                            else:
                                self.ui.update_status_message("Piece detected in slot - processing")
                                if not self.processing_thread or not self.processing_thread.is_alive():
                                    self.processing_thread = threading.Thread(
                                        target=self.process_piece
                                    )
                                    self.processing_thread.start()
                            
                            self.piece_in_progress = False
                            self.waiting_for_sensor2 = False

            elif self.ui.current_status['state'] == 'error_recovery':
                if self.gpio.read_sensor1():
                    self.ui.update_status_message("Restarting cycle from sensor 1")
                    self.ui.current_status['state'] = 'normal'
                    self.piece_in_progress = True
                    self.waiting_for_sensor2 = False
                    self.ui.current_status['alert'] = None
                    self.last_sensor1_state = True
                
                elif self.gpio.read_sensor2():
                    self.ui.update_status_message("Manual piece placement detected")
                    if not self.processing_thread or not self.processing_thread.is_alive():
                        self.processing_thread = threading.Thread(
                            target=self.process_piece
                        )
                        self.processing_thread.start()
                    self.ui.current_status['state'] = 'normal'
                    self.piece_in_progress = False
                    self.waiting_for_sensor2 = False

        except Exception as e:
            self.ui.current_status['state'] = 'Error'
            self.ui.update_status_message(f"Error: {str(e)}", is_alert=True)

    def run(self):
        """Run with framebuffer UI"""
        try:
            while self.running:
                # Run state machine
                self.run_state_machine()
                
                # Update UI
                self.ui.update_display(self.gpio, self.network)
                
                time.sleep(UI_REFRESH_RATE)
                
        except KeyboardInterrupt:
            print("\nShutting down...")
        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up system resources"""
        self.running = False
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join()
        self.gpio.cleanup()
        self.ui.cleanup()

def main():
    try:
        system = InspectionSystem()
        system.run()
    except ValueError as e:
        print(f"Configuration error: {str(e)}")
        return 1
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())