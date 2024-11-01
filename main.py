import curses
import time
import argparse
import threading
from datetime import datetime

from config import (
    NETWORK_CHECK_INTERVAL,
    SENSOR2_WAIT_TIME,
    UI_REFRESH_RATE
)

from core.hardware import GPIOController
from core.network import NetworkManager
from core.processing import ImageProcessor
from ui.curses_ui import CursesUI
from ui.fb_ui import FramebufferUI

class InspectionSystem:
    def __init__(self, use_framebuffer=False):
        # Initialize components
        self.gpio = GPIOController()
        self.network = NetworkManager()
        self.ui = FramebufferUI() if use_framebuffer else CursesUI()
        self.processor = ImageProcessor(self.ui.update_status_message)
        
        # State variables
        self.piece_in_progress = False
        self.waiting_for_sensor2 = False
        self.sensor2_check_time = None
        self.last_network_check = 0
        self.processing_thread = None
        self.running = True
        
        # Solenoid timing variables
        self.solenoid_deactivation_time = None
        self.SOLENOID_DELAY_MS = 500  # 500ms delay
        self.last_sensor1_state = False  # Track sensor1's previous state

    def process_piece(self):
        """Process a piece with UI updates"""
        self.ui.update_status_message("=== Starting piece processing ===")
        
        # Capture image
        image_data = self.processor.get_image()
        if image_data:
            self.ui.update_image(image_data)
            self.ui.update_status_message("Image captured successfully, starting analysis...")
            
            # Analyze image
            confidence = self.processor.analyze_image(image_data)
            
            if confidence:
                self.ui.current_status['last_inference'] = datetime.now().strftime("%H:%M:%S")
                self.ui.current_status['last_confidence'] = confidence
                self.ui.update_status_message(f"Analysis complete - confidence: {confidence:.2%}")
            else:
                self.ui.update_status_message("Analysis complete - no confident predictions")
        else:
            self.ui.update_status_message("Failed to capture image", is_alert=True)
        
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

            # State machine
            if self.ui.current_status['state'] == 'normal':
                current_sensor1_state = self.gpio.read_sensor1()
                
                # Detect falling edge of sensor1
                if self.last_sensor1_state and not current_sensor1_state:
                    self.solenoid_deactivation_time = time.time()
                    self.ui.update_status_message(f"Sensor1 deactivated - starting {self.SOLENOID_DELAY_MS}ms countdown")
                
                # Update last sensor state
                self.last_sensor1_state = current_sensor1_state

                if current_sensor1_state and not self.piece_in_progress:
                    self.piece_in_progress = True
                    self.ui.update_status_message("Piece detected - activating solenoid")
                    self.waiting_for_sensor2 = False
                    self.ui.current_status['alert'] = None
                    self.solenoid_deactivation_time = None
                
                if self.piece_in_progress:
                    # Determine if solenoid should be active
                    should_activate = False
                    
                    if current_sensor1_state:
                        # Keep solenoid on while sensor1 is active
                        should_activate = True
                    elif self.solenoid_deactivation_time is not None:
                        # Calculate time since deactivation
                        elapsed_ms = (time.time() - self.solenoid_deactivation_time) * 1000
                        should_activate = elapsed_ms < self.SOLENOID_DELAY_MS
                        
                        if should_activate:
                            self.ui.update_status_message(f"Holding solenoid - {int(self.SOLENOID_DELAY_MS - elapsed_ms)}ms remaining")
                    
                    # Set solenoid state
                    self.gpio.set_solenoid(should_activate)
                    
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
                            self.solenoid_deactivation_time = None
                            
            elif self.ui.current_status['state'] == 'error_recovery':
                if self.gpio.read_sensor1():
                    self.ui.update_status_message("Restarting cycle from sensor 1")
                    self.ui.current_status['state'] = 'normal'
                    self.piece_in_progress = True
                    self.waiting_for_sensor2 = False
                    self.ui.current_status['alert'] = None
                    self.solenoid_deactivation_time = None
                    self.last_sensor1_state = True
                
                elif self.gpio.read_sensor2():
                    self.ui.update_status_message("Manual piece placement detected")
                    if not self.processing_thread or not self.processing_thread.is_alive():
                        self.processing_thread = threading.Thread(
                            target=self.process_piece
                        )
                        self.processing_thread.start()
                    self.piece_in_progress = False
                    self.waiting_for_sensor2 = False
                    self.solenoid_deactivation_time = None

        except Exception as e:
            self.ui.current_status['state'] = 'Error'
            self.ui.update_status_message(f"Error: {str(e)}", is_alert=True)

    def run_curses(self, stdscr):
        """Run with curses UI"""
        # Setup curses
        curses.curs_set(0)
        stdscr.nodelay(1)
        
        try:
            while self.running:
                # Check for quit
                try:
                    if stdscr.getch() == ord('q'):
                        break
                except:
                    pass

                # Run state machine
                self.run_state_machine()
                
                # Update UI
                self.ui.update_display(stdscr, self.gpio, self.network)
                stdscr.refresh()
                
                time.sleep(UI_REFRESH_RATE)
                
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()

    def run_framebuffer(self):
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
    parser = argparse.ArgumentParser(
        description='Run the inspection system with either curses or framebuffer UI'
    )
    parser.add_argument(
        '--hdmi',
        action='store_true',
        help='Use HDMI output (framebuffer) instead of curses'
    )
    args = parser.parse_args()
    
    system = InspectionSystem(use_framebuffer=args.hdmi)
    
    if args.hdmi:
        system.run_framebuffer()
    else:
        curses.wrapper(system.run_curses)

if __name__ == "__main__":
    main()