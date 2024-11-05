import time
import threading
from datetime import datetime
import os
from typing import Dict, Any
from dotenv import load_dotenv
import json

from config import (
    NETWORK_CHECK_INTERVAL,
    SENSOR2_WAIT_TIME,
    UI_REFRESH_RATE,
    IMAGE_URL,
)

from core.hardware import GPIOController
from core.network import NetworkManager
from core.processing import ImageProcessor
from ui.fb_ui import FramebufferUI

import logging

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

        # Add ejection control thresholds
        self.EJECTION_THRESHOLDS = {
            'confidence_min': 0.01,  # Extremely low confidence threshold - almost any detection counts
            'area_max': 0.0001,     # Tiny defect area threshold - even smallest defects trigger
            'critical_count': 0,     # Any critical defect causes ejection
            'major_count': 0,        # Any major defect causes ejection
            'total_defects': 1       # Any single defect causes ejection
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
                status_callback=self.ui.update_status_message
            )
        except Exception as e:
            if hasattr(self, 'gpio'):
                self.gpio.cleanup()
            if hasattr(self, 'ui'):
                self.ui.cleanup()
            raise
        
        # State variables
        self.piece_in_progress = False
        self.waiting_for_sensor2 = False
        self.sensor2_check_time = None
        self.last_network_check = time.time()
        self.processing_thread = None
        self.running = True
        self.analysis_in_progress = False
        
        # Processing completion state
        self.processing_complete = True  # Start as True to allow initial cycle
        
        # Solenoid timing variables
        self.solenoid_deactivation_time = None
        self.solenoid_activation_time = None
        self.SOLENOID_DELAY_MS = 500
        self.SOLENOID_START_DELAY_MS = 300
        self.last_sensor1_state = False
        
        # Ejection control variables
        self.EJECTION_TIME_MS = 500
        self.POST_EJECTION_DELAY_MS = 500
        self.ejection_start_time = None
        self.post_ejection_start_time = None
        self.ejection_in_progress = False
        self.post_ejection_delay = False
        
        # Force solenoid off during processing
        self.solenoid_locked = False
        
        # Warning message state
        self.wait_warning_shown = False

        # Enhanced error tracking
        self.error_count = 0
        self.last_error = None
        self.last_successful_process = None
        
        # Processing history
        self.results_history = []
        self.MAX_HISTORY = 100

        self.logger = logging.getLogger(__name__)

    def _has_imperfections(self, results: Dict[str, Any]) -> bool:
        """
        Enhanced imperfection detection logic that examines prediction results
        and determines if the piece should be ejected based on defects.
        
        Args:
            results: Dictionary containing prediction results and metadata
            
        Returns:
            bool: True if piece should be ejected, False otherwise
        """
        if not results or 'predictions' not in results:
            return False
            
        summary = results.get('summary', {})
        predictions = results.get('predictions', [])
        
        # Check if we have any predictions to analyze
        if not predictions:
            return False
            
        # Get severity counts from summary
        severity_counts = summary.get('severity_counts', {})
        critical_defects = severity_counts.get('critical', 0)
        major_defects = severity_counts.get('major', 0)
        total_defects = sum(severity_counts.values())
        
        # Check if any single prediction has very high confidence of a defect
        for pred in predictions:
            confidence = pred.get('confidence', 0)
            area = pred.get('metadata', {}).get('area', 0)
            
            # If we have a high-confidence, large defect, eject immediately
            if (confidence >= self.EJECTION_THRESHOLDS['confidence_min'] and 
                area >= self.EJECTION_THRESHOLDS['area_max']):
                return True
                
        # Check against threshold counts
        if any([
            critical_defects >= self.EJECTION_THRESHOLDS['critical_count'],
            major_defects >= self.EJECTION_THRESHOLDS['major_count'],
            total_defects >= self.EJECTION_THRESHOLDS['total_defects']
        ]):
            return True
            
        return False

    def process_piece(self):
        """Process a piece with enhanced logging"""
        self.analysis_in_progress = True
        self.processing_complete = False
        self.solenoid_locked = True
        self.wait_warning_shown = False
        self.ui.start_processing()
        
        try:
            self.logger.info("=== Starting piece processing ===")
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
                
                # Log details about the inspection decision
                self.logger.info("\n=== Inspection Decision Analysis ===")
                should_eject = self._has_imperfections(results)
                
                if should_eject:
                    message = "Defects detected - ejecting piece"
                    self.logger.info(f"DECISION: {message}")
                    self.ui.update_status_message(message, is_alert=True)
                    self.ejection_in_progress = True
                    self.ejection_start_time = time.time()
                    self.gpio.set_ejection_cylinder(True)
                else:
                    message = "Piece passed inspection"
                    self.logger.info(f"DECISION: {message}")
                    self.ui.update_status_message(message)
                    self.processing_complete = True
                    self.solenoid_locked = False
                
            else:
                raise Exception("Analysis failed to produce results")
                
        except Exception as e:
            self.logger.error(f"Processing error: {str(e)}", exc_info=True)
            self.metrics['error_count'] += 1
            self.last_error = str(e)
            processing_time = time.time() - self.ui.metrics['current_processing_start']
            self.ui.update_metrics(error=str(e), processing_time=processing_time)
            self.ui.update_status_message(f"Processing error: {str(e)}", is_alert=True)
            
        finally:
            self.analysis_in_progress = False
            if not self.ejection_in_progress:
                self.processing_complete = True
                self.solenoid_locked = False
            self.ui.current_status['state'] = 'normal'
            self.ui.current_status['alert'] = None

    def _has_imperfections(self, results: Dict[str, Any]) -> bool:
        """
        Enhanced imperfection detection logic with detailed logging
        """
        if not results or 'predictions' not in results:
            self.logger.warning("No results available - failing safe by ejecting")
            return True
            
        predictions = results.get('predictions', [])
        summary = results.get('summary', {})
        
        # Log the basic stats
        self.logger.info(f"Analyzing {len(predictions)} predictions")
        self.logger.info(f"Summary: {json.dumps(summary, indent=2)}")
        
        # Log each prediction's details
        for i, pred in enumerate(predictions, 1):
            confidence = pred.get('confidence', 0)
            area = pred.get('metadata', {}).get('area', 0)
            severity = pred.get('metadata', {}).get('severity', 'unknown')
            class_name = pred.get('class_name', 'unknown')
            
            self.logger.info(
                f"Defect {i}: type={class_name}, confidence={confidence:.3f}, "
                f"area={area:.6f}, severity={severity}"
            )
            
            # Check individual prediction thresholds
            if confidence > self.EJECTION_THRESHOLDS['confidence_min']:
                self.logger.info(
                    f"EJECTING: Defect {i} confidence {confidence:.3f} exceeds "
                    f"minimum threshold {self.EJECTION_THRESHOLDS['confidence_min']}"
                )
                return True
                
            if area > self.EJECTION_THRESHOLDS['area_max']:
                self.logger.info(
                    f"EJECTING: Defect {i} area {area:.6f} exceeds "
                    f"maximum threshold {self.EJECTION_THRESHOLDS['area_max']}"
                )
                return True
        
        # Check severity counts
        severity_counts = summary.get('severity_counts', {})
        critical_defects = severity_counts.get('critical', 0)
        major_defects = severity_counts.get('major', 0)
        total_defects = sum(severity_counts.values())
        
        self.logger.info(
            f"Severity counts: critical={critical_defects}, major={major_defects}, "
            f"total={total_defects}"
        )
        
        if critical_defects > self.EJECTION_THRESHOLDS['critical_count']:
            self.logger.info(
                f"EJECTING: {critical_defects} critical defects exceed threshold "
                f"{self.EJECTION_THRESHOLDS['critical_count']}"
            )
            return True
            
        if major_defects > self.EJECTION_THRESHOLDS['major_count']:
            self.logger.info(
                f"EJECTING: {major_defects} major defects exceed threshold "
                f"{self.EJECTION_THRESHOLDS['major_count']}"
            )
            return True
            
        if total_defects >= self.EJECTION_THRESHOLDS['total_defects']:
            self.logger.info(
                f"EJECTING: {total_defects} total defects exceed threshold "
                f"{self.EJECTION_THRESHOLDS['total_defects']}"
            )
            return True
            
        self.logger.info("Piece passed all inspection criteria")
        return False

    def run_state_machine(self):
        """Main state machine logic with ejection control"""
        try:
            current_time = time.time()
            
            # Handle ejection cycle timing
            if self.ejection_in_progress:
                elapsed_ms = (current_time - self.ejection_start_time) * 1000
                if elapsed_ms >= self.EJECTION_TIME_MS:
                    self.gpio.set_ejection_cylinder(False)
                    self.ejection_in_progress = False
                    self.post_ejection_delay = True
                    self.post_ejection_start_time = current_time
                return  # Skip rest of state machine during ejection
            
            # Handle post-ejection delay
            if self.post_ejection_delay:
                elapsed_ms = (current_time - self.post_ejection_start_time) * 1000
                if elapsed_ms >= self.POST_EJECTION_DELAY_MS:
                    self.post_ejection_delay = False
                    self.processing_complete = True
                    self.solenoid_locked = False
                    self.ui.update_status_message("Ready for next piece")
                return  # Skip rest of state machine during post-ejection delay
            
            # Periodic network checks
            if current_time - self.last_network_check > NETWORK_CHECK_INTERVAL:
                self.network.check_all()
                self.last_network_check = current_time

            # If solenoid is locked, force it off regardless of other conditions
            if self.solenoid_locked:
                self.gpio.set_solenoid(False)
                if self.gpio.read_sensor1():
                    if not self.wait_warning_shown:
                        self.ui.update_status_message(
                            "Please wait for current piece processing to complete",
                            is_alert=True
                        )
                        self.wait_warning_shown = True
                return  # Skip rest of state machine while locked

            # Regular state machine logic continues as before...
            current_sensor1_state = self.gpio.read_sensor1()
            
            if not self.solenoid_locked:
                if self.last_sensor1_state and not current_sensor1_state:
                    self.solenoid_deactivation_time = time.time()
                    
                if not self.last_sensor1_state and current_sensor1_state:
                    self.solenoid_activation_time = time.time()
                
                self.last_sensor1_state = current_sensor1_state

                should_activate = self._calculate_solenoid_state(
                    current_sensor1_state,
                    current_time
                )
                self.gpio.set_solenoid(should_activate)

            if self.processing_complete:
                self._handle_piece_processing(current_sensor1_state)
                
        except Exception as e:
            self.metrics['total_errors'] += 1
            self.ui.update_status_message(f"State machine error: {str(e)}", is_alert=True)

    def _calculate_solenoid_state(self, sensor1_state: bool, current_time: float) -> bool:
        """Calculate whether solenoid should be active"""
        if self.solenoid_locked:
            return False
            
        if sensor1_state:
            if self.solenoid_activation_time is not None:
                elapsed_ms = (current_time - self.solenoid_activation_time) * 1000
                return elapsed_ms >= self.SOLENOID_START_DELAY_MS
        elif self.solenoid_deactivation_time is not None:
            elapsed_ms = (current_time - self.solenoid_deactivation_time) * 1000
            return elapsed_ms < self.SOLENOID_DELAY_MS
        
        return False

    def _handle_piece_processing(self, sensor1_state: bool):
        """Handle piece processing logic with AI toggle switch support"""
        # Check AI toggle switch state
        ai_disabled = self.gpio.read_ai_toggle_switch()
        
        if self.ui.current_status['state'] == 'normal':
            if sensor1_state and not self.piece_in_progress and not self.solenoid_locked:
                self.piece_in_progress = True
                self.ui.update_status_message("Piece detected")
                self.waiting_for_sensor2 = False
                self.ui.current_status['alert'] = None
            
            if self.piece_in_progress and not self.solenoid_locked:
                if not sensor1_state:
                    if ai_disabled:
                        # If AI is disabled, skip sensor2 check and image processing
                        self.piece_in_progress = False
                        self.processing_complete = True
                        self.ui.update_status_message("AI check skipped - toggle switch active")
                    else:
                        # Normal processing path with sensor2 and AI
                        if not self.waiting_for_sensor2:
                            self.waiting_for_sensor2 = True
                            self.sensor2_check_time = time.time()
                        
                        if self.waiting_for_sensor2 and (time.time() - self.sensor2_check_time) > SENSOR2_WAIT_TIME:
                            if not self.gpio.read_sensor2():
                                self.ui.current_status['alert'] = "No piece fell in slot!"
                                self.ui.current_status['state'] = 'error_recovery'
                                self.processing_complete = True  # Allow retry in error state
                                self.solenoid_locked = False
                            else:
                                if not self.processing_thread or not self.processing_thread.is_alive():
                                    self.processing_thread = threading.Thread(
                                        target=self.process_piece
                                    )
                                    self.processing_thread.start()
                            
                            self.piece_in_progress = False
                            self.waiting_for_sensor2 = False

        elif self.ui.current_status['state'] == 'error_recovery':
            if sensor1_state and not self.solenoid_locked:
                self.ui.current_status['state'] = 'normal'
                self.piece_in_progress = True
                self.waiting_for_sensor2 = False
                self.ui.current_status['alert'] = None
            elif self.gpio.read_sensor2() and not self.solenoid_locked:
                if not ai_disabled:  # Only process if AI is enabled
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