# core/controller.py
import json
import time
import threading
import logging
from typing import Dict, Any
from datetime import datetime

from config.settings import (
    NETWORK_CHECK_INTERVAL,
    SENSOR2_WAIT_TIME,
    IMAGE_URL,
    EJECTION_THRESHOLDS,
    SOLENOID_SETTINGS
)

class InspectionController:
    def __init__(self, system):
        self.system = system
        self.logger = logging.getLogger(__name__)

    def process_piece(self):
        """Process a piece with enhanced logging"""
        self.system.analysis_in_progress = True
        self.system.processing_complete = False
        self.system.solenoid_locked = True
        self.system.wait_warning_shown = False
        self.system.ui.start_processing()
        
        try:
            self.logger.info("=== Starting piece processing ===")
            self.system.ui.update_status_message("=== Starting piece processing ===")
            
            # Get image
            image_data = self.system.processor.get_image(IMAGE_URL)
            if not image_data:
                raise Exception("Failed to capture image")
            
            # Update UI with image
            self.system.ui.update_image(image_data)
            
            # Analyze image
            results = self.system.processor.analyze_image(image_data)
            
            if results:
                # Get processing time
                start_time = self.system.ui.metrics.get_current_processing_start()
                processing_time = time.time() - start_time if start_time is not None else None
                
                self.system.metrics_manager.update_metrics(
                    success=True,
                    processing_time=processing_time
                )
                
                # Update UI
                self.system.ui.update_metrics(results=results, processing_time=processing_time)
                self.system.ui.update_predictions(results)
                
                # Log inspection decision
                self.logger.info("\n=== Inspection Decision Analysis ===")
                should_eject = self._has_imperfections(results)
                
                if should_eject:
                    message = "Defects detected - ejecting piece"
                    self.logger.info(f"DECISION: {message}")
                    self.system.ui.update_status_message(message, is_alert=True)
                    self.system.ejection_in_progress = True
                    self.system.ejection_start_time = time.time()
                    self.system.gpio.set_ejection_cylinder(True)
                else:
                    message = "Piece passed inspection"
                    self.logger.info(f"DECISION: {message}")
                    self.system.ui.update_status_message(message)
                    self.system.processing_complete = True
                    self.system.solenoid_locked = False
                
            else:
                raise Exception("Analysis failed to produce results")
                
        except Exception as e:
            self.logger.error(f"Processing error: {str(e)}", exc_info=True)
            self.system.metrics_manager.update_metrics(
                success=False,
                error=str(e)
            )
            
            start_time = self.system.ui.metrics.get_current_processing_start()
            processing_time = time.time() - start_time if start_time is not None else None
            
            self.system.ui.update_metrics(error=str(e), processing_time=processing_time)
            self.system.ui.update_status_message(f"Processing error: {str(e)}", is_alert=True)
            
        finally:
            self.system.analysis_in_progress = False
            if not self.system.ejection_in_progress:
                self.system.processing_complete = True
                self.system.solenoid_locked = False
            self.system.ui.current_status['state'] = 'normal'
            self.system.ui.current_status['alert'] = None

    def _has_imperfections(self, results: Dict[str, Any]) -> bool:
        """Enhanced imperfection detection logic with detailed logging"""
        if not results or 'predictions' not in results:
            self.logger.warning("No results available - failing safe by ejecting")
            return True
            
        predictions = results.get('predictions', [])
        summary = results.get('summary', {})
        
        self.logger.info(f"Analyzing {len(predictions)} predictions")
        self.logger.info(f"Summary: {json.dumps(summary, indent=2)}")
        
        for i, pred in enumerate(predictions, 1):
            confidence = pred.get('confidence', 0)
            area = pred.get('metadata', {}).get('area', 0)
            severity = pred.get('metadata', {}).get('severity', 'unknown')
            class_name = pred.get('class_name', 'unknown')
            
            self.logger.info(
                f"Defect {i}: type={class_name}, confidence={confidence:.3f}, "
                f"area={area:.6f}, severity={severity}"
            )
            
            if confidence > EJECTION_THRESHOLDS['confidence_min']:
                self.logger.info(
                    f"EJECTING: Defect {i} confidence {confidence:.3f} exceeds "
                    f"minimum threshold {EJECTION_THRESHOLDS['confidence_min']}"
                )
                return True
                
            if area > EJECTION_THRESHOLDS['area_max']:
                self.logger.info(
                    f"EJECTING: Defect {i} area {area:.6f} exceeds "
                    f"maximum threshold {EJECTION_THRESHOLDS['area_max']}"
                )
                return True
        
        severity_counts = summary.get('severity_counts', {})
        critical_defects = severity_counts.get('critical', 0)
        major_defects = severity_counts.get('major', 0)
        total_defects = sum(severity_counts.values())
        
        self.logger.info(
            f"Severity counts: critical={critical_defects}, major={major_defects}, "
            f"total={total_defects}"
        )
        
        if critical_defects > EJECTION_THRESHOLDS['critical_count']:
            self.logger.info(
                f"EJECTING: {critical_defects} critical defects exceed threshold "
                f"{EJECTION_THRESHOLDS['critical_count']}"
            )
            return True
            
        if major_defects > EJECTION_THRESHOLDS['major_count']:
            self.logger.info(
                f"EJECTING: {major_defects} major defects exceed threshold "
                f"{EJECTION_THRESHOLDS['major_count']}"
            )
            return True
            
        if total_defects >= EJECTION_THRESHOLDS['total_defects']:
            self.logger.info(
                f"EJECTING: {total_defects} total defects exceed threshold "
                f"{EJECTION_THRESHOLDS['total_defects']}"
            )
            return True
            
        self.logger.info("Piece passed all inspection criteria")
        return False

    def run_state_machine(self):
        """Main state machine logic with ejection control"""
        try:
            current_time = time.time()
            
            # Handle ejection cycle timing
            if self.system.ejection_in_progress:
                elapsed_ms = (current_time - self.system.ejection_start_time) * 1000
                if elapsed_ms >= SOLENOID_SETTINGS['EJECTION_TIME_MS']:
                    self.system.gpio.set_ejection_cylinder(False)
                    self.system.ejection_in_progress = False
                    self.system.post_ejection_delay = True
                    self.system.post_ejection_start_time = current_time
                return
            
            # Handle post-ejection delay
            if self.system.post_ejection_delay:
                elapsed_ms = (current_time - self.system.post_ejection_start_time) * 1000
                if elapsed_ms >= SOLENOID_SETTINGS['POST_EJECTION_DELAY_MS']:
                    self.system.post_ejection_delay = False
                    self.system.processing_complete = True
                    self.system.solenoid_locked = False
                    self.system.ui.update_status_message("Ready for next piece")
                return
            
            # Network checks
            if current_time - self.system.last_network_check > NETWORK_CHECK_INTERVAL:
                self.system.network.check_all()
                self.system.last_network_check = current_time

            # Handle locked solenoid state
            if self.system.solenoid_locked:
                self.system.gpio.set_solenoid(False)
                if self.system.gpio.read_sensor1():
                    if not self.system.wait_warning_shown:
                        self.system.ui.update_status_message(
                            "Please wait for current piece processing to complete",
                            is_alert=True
                        )
                        self.system.wait_warning_shown = True
                return

            current_sensor1_state = self.system.gpio.read_sensor1()
            
            if not self.system.solenoid_locked:
                if self.system.last_sensor1_state and not current_sensor1_state:
                    self.system.solenoid_deactivation_time = time.time()
                    
                if not self.system.last_sensor1_state and current_sensor1_state:
                    self.system.solenoid_activation_time = time.time()
                
                self.system.last_sensor1_state = current_sensor1_state

                should_activate = self._calculate_solenoid_state(
                    current_sensor1_state,
                    current_time
                )
                self.system.gpio.set_solenoid(should_activate)

            if self.system.processing_complete:
                self._handle_piece_processing(current_sensor1_state)
                
        except Exception as e:
            self.system.metrics_manager.metrics['total_errors'] += 1
            self.system.ui.update_status_message(f"State machine error: {str(e)}", is_alert=True)

    def _calculate_solenoid_state(self, sensor1_state: bool, current_time: float) -> bool:
        """Calculate whether solenoid should be active"""
        if self.system.solenoid_locked:
            return False
            
        if sensor1_state:
            if self.system.solenoid_activation_time is not None:
                elapsed_ms = (current_time - self.system.solenoid_activation_time) * 1000
                return elapsed_ms >= SOLENOID_SETTINGS['START_DELAY_MS']
        elif self.system.solenoid_deactivation_time is not None:
            elapsed_ms = (current_time - self.system.solenoid_deactivation_time) * 1000
            return elapsed_ms < SOLENOID_SETTINGS['DELAY_MS']
        
        return False

    def _handle_piece_processing(self, sensor1_state: bool):
        """Handle piece processing logic with AI toggle switch support"""
        ai_disabled = self.system.gpio.read_ai_toggle_switch()
        
        if self.system.ui.current_status['state'] == 'normal':
            if sensor1_state and not self.system.piece_in_progress and not self.system.solenoid_locked:
                self.system.piece_in_progress = True
                self.system.ui.update_status_message("Piece detected")
                self.system.waiting_for_sensor2 = False
                self.system.ui.current_status['alert'] = None
            
            if self.system.piece_in_progress and not self.system.solenoid_locked:
                if not sensor1_state:
                    if ai_disabled:
                        self.system.piece_in_progress = False
                        self.system.processing_complete = True
                        self.system.ui.update_status_message("AI check skipped - toggle switch active")
                    else:
                        if not self.system.waiting_for_sensor2:
                            self.system.waiting_for_sensor2 = True
                            self.system.sensor2_check_time = time.time()
                        
                        if self.system.waiting_for_sensor2 and (time.time() - self.system.sensor2_check_time) > SENSOR2_WAIT_TIME:
                            if not self.system.gpio.read_sensor2():
                                self.system.ui.current_status['alert'] = "No piece fell in slot!"
                                self.system.ui.current_status['state'] = 'error_recovery'
                                self.system.processing_complete = True
                                self.system.solenoid_locked = False
                            else:
                                if not self.system.processing_thread or not self.system.processing_thread.is_alive():
                                    self.system.processing_thread = threading.Thread(
                                        target=self.process_piece
                                    )
                                    self.system.processing_thread.start()
                            
                            self.system.piece_in_progress = False
                            self.system.waiting_for_sensor2 = False

        elif self.system.ui.current_status['state'] == 'error_recovery':
            if sensor1_state and not self.system.solenoid_locked:
                self.system.ui.current_status['state'] = 'normal'
                self.system.piece_in_progress = True
                self.system.waiting_for_sensor2 = False
                self.system.ui.current_status['alert'] = None
            elif self.system.gpio.read_sensor2() and not self.system.solenoid_locked:
                if not ai_disabled:
                    if not self.system.processing_thread or not self.system.processing_thread.is_alive():
                        self.system.processing_thread = threading.Thread(
                            target=self.process_piece
                        )
                        self.system.processing_thread.start()
                self.system.ui.current_status['state'] = 'normal'
                self.system.piece_in_progress = False
                self.system.waiting_for_sensor2 = False