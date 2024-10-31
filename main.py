import curses
import time
import argparse
from config import *
from network_monitor import NetworkStatus
from gpio_controller import GPIOController
from image_processor import ImageProcessor
from ui_manager import UIManager
try:
    from fb_ui_manager import FBUIManager
except ImportError:
    FBUIManager = None
from datetime import datetime
import threading

def process_piece_curses(image_processor, ui_manager, stdscr, gpio_controller, network_status):
    """Process a piece with real-time UI updates (curses version)"""
    def refresh_ui():
        ui_manager.draw(stdscr, gpio_controller, network_status)
        stdscr.refresh()
        
    image_processor.refresh_ui = refresh_ui
    
    ui_manager.update_status_message("=== Starting piece processing ===")
    refresh_ui()
    
    image_data = image_processor.get_image(IMAGE_URL)
    
    if image_data:
        ui_manager.update_status_message("Image captured successfully, starting analysis...")
        refresh_ui()
        
        confidence = image_processor.send_for_analysis(INFERENCE_URL, image_data)
        
        if confidence:
            ui_manager.current_status['last_inference'] = datetime.now().strftime("%H:%M:%S")
            ui_manager.current_status['last_confidence'] = confidence
            ui_manager.update_status_message(f"Analysis complete - confidence: {confidence:.2%}")
        else:
            ui_manager.update_status_message("Analysis complete - no confident predictions")
    else:
        ui_manager.update_status_message("Failed to capture image", is_alert=True)
    
    ui_manager.update_status_message("=== Piece processing complete ===")
    ui_manager.current_status['state'] = 'normal'
    ui_manager.current_status['alert'] = None
    refresh_ui()

def process_piece_fb(image_processor, ui_manager, gpio_controller, network_status):
    """Process a piece with real-time UI updates (framebuffer version)"""
    def refresh_ui():
        ui_manager.update_display(gpio_controller, network_status)
        
    image_processor.refresh_ui = refresh_ui
    
    # Clear any previous image at the start of processing
    ui_manager.clear_image()
    ui_manager.update_status_message("=== Starting piece processing ===")
    refresh_ui()
    
    image_data = image_processor.get_image(IMAGE_URL)
    
    if image_data:
        # Update the UI with the captured image
        ui_manager.set_current_image(image_data)
        refresh_ui()  # Immediately refresh to show the new image
        
        ui_manager.update_status_message("Image captured successfully, starting analysis...")
        refresh_ui()
        
        confidence = image_processor.send_for_analysis(INFERENCE_URL, image_data)
        
        if confidence:
            ui_manager.current_status['last_inference'] = datetime.now().strftime("%H:%M:%S")
            ui_manager.current_status['last_confidence'] = confidence
            ui_manager.update_status_message(f"Analysis complete - confidence: {confidence:.2%}")
        else:
            ui_manager.update_status_message("Analysis complete - no confident predictions")
    else:
        ui_manager.update_status_message("Failed to capture image", is_alert=True)
    
    ui_manager.update_status_message("=== Piece processing complete ===")
    ui_manager.current_status['state'] = 'normal'
    ui_manager.current_status['alert'] = None
    refresh_ui()

def main_curses(stdscr):
    """Original curses-based main function"""
    # Initialize components
    network_status = NetworkStatus()
    gpio_controller = GPIOController()
    ui_manager = UIManager()
    image_processor = ImageProcessor(ui_manager.update_status_message)
    
    # Setup curses
    curses.curs_set(0)
    stdscr.nodelay(1)
    
    try:
        piece_in_progress = False
        waiting_for_sensor2 = False
        sensor2_check_time = None
        last_network_check = 0
        processing_thread = None
        
        while True:
            # Check for quit
            try:
                if stdscr.getch() == ord('q'):
                    break
            except:
                pass

            current_time = time.time()
            
            # Periodic network checks
            if current_time - last_network_check > NETWORK_CHECK_INTERVAL:
                network_status.check_internet()
                network_status.check_camera(IMAGE_URL)
                network_status.check_ai_server(INFERENCE_URL)
                last_network_check = current_time

            # State machine
            if ui_manager.current_status['state'] == 'normal':
                if gpio_controller.read_sensor1() and not piece_in_progress:
                    piece_in_progress = True
                    ui_manager.update_status_message("Piece detected - activating solenoid")
                    waiting_for_sensor2 = False
                    ui_manager.current_status['alert'] = None
                
                if piece_in_progress:
                    if gpio_controller.read_sensor1():
                        gpio_controller.set_solenoid(True)  # ON
                    else:
                        gpio_controller.set_solenoid(False)  # OFF
                        
                        if not waiting_for_sensor2:
                            waiting_for_sensor2 = True
                            sensor2_check_time = time.time()
                            ui_manager.update_status_message("Sensor 1 released - waiting for piece to reach slot...")
                        
                        if waiting_for_sensor2 and (time.time() - sensor2_check_time) > SENSOR2_WAIT_TIME:
                            if not gpio_controller.read_sensor2():
                                ui_manager.update_status_message("No piece fell in slot!", is_alert=True)
                                ui_manager.current_status['alert'] = "No piece fell in slot!"
                                ui_manager.current_status['state'] = 'error_recovery'
                            else:
                                ui_manager.update_status_message("Piece detected in slot - processing")
                                if not processing_thread or not processing_thread.is_alive():
                                    processing_thread = threading.Thread(
                                        target=process_piece_curses,
                                        args=(image_processor, ui_manager, stdscr, gpio_controller, network_status)
                                    )
                                    processing_thread.start()
                            
                            piece_in_progress = False
                            waiting_for_sensor2 = False
                            
            elif ui_manager.current_status['state'] == 'error_recovery':
                if gpio_controller.read_sensor1():
                    ui_manager.update_status_message("Restarting cycle from sensor 1")
                    ui_manager.current_status['state'] = 'normal'
                    piece_in_progress = True
                    waiting_for_sensor2 = False
                    ui_manager.current_status['alert'] = None
                
                elif gpio_controller.read_sensor2():
                    ui_manager.update_status_message("Manual piece placement detected")
                    if not processing_thread or not processing_thread.is_alive():
                        processing_thread = threading.Thread(
                            target=process_piece_curses,
                            args=(image_processor, ui_manager, stdscr, gpio_controller, network_status)
                        )
                        processing_thread.start()
                    piece_in_progress = False
                    waiting_for_sensor2 = False
            
            # Update UI
            ui_manager.draw(stdscr, gpio_controller, network_status)
            stdscr.refresh()
            
            time.sleep(0.05)
            
    except Exception as e:
        ui_manager.current_status['state'] = 'Error'
        ui_manager.update_status_message(f"Error: {str(e)}", is_alert=True)
        ui_manager.draw(stdscr, gpio_controller, network_status)
        stdscr.refresh()
        time.sleep(2)
    finally:
        gpio_controller.cleanup()

def main_fb():
    """Framebuffer-based main function"""
    # Initialize components
    network_status = NetworkStatus()
    gpio_controller = GPIOController()
    ui_manager = FBUIManager()
    image_processor = ImageProcessor(ui_manager.update_status_message)
    
    try:
        piece_in_progress = False
        waiting_for_sensor2 = False
        sensor2_check_time = None
        last_network_check = 0
        processing_thread = None
        
        while True:
            current_time = time.time()
            
            # Periodic network checks
            if current_time - last_network_check > NETWORK_CHECK_INTERVAL:
                network_status.check_internet()
                network_status.check_camera(IMAGE_URL)
                network_status.check_ai_server(INFERENCE_URL)
                last_network_check = current_time

            # State machine
            if ui_manager.current_status['state'] == 'normal':
                if gpio_controller.read_sensor1() and not piece_in_progress:
                    piece_in_progress = True
                    ui_manager.update_status_message("Piece detected - activating solenoid")
                    waiting_for_sensor2 = False
                    ui_manager.current_status['alert'] = None
                
                if piece_in_progress:
                    if gpio_controller.read_sensor1():
                        gpio_controller.set_solenoid(True)  # ON
                    else:
                        gpio_controller.set_solenoid(False)  # OFF
                        
                        if not waiting_for_sensor2:
                            waiting_for_sensor2 = True
                            sensor2_check_time = time.time()
                            ui_manager.update_status_message("Sensor 1 released - waiting for piece to reach slot...")
                        
                        if waiting_for_sensor2 and (time.time() - sensor2_check_time) > SENSOR2_WAIT_TIME:
                            if not gpio_controller.read_sensor2():
                                ui_manager.update_status_message("No piece fell in slot!", is_alert=True)
                                ui_manager.current_status['alert'] = "No piece fell in slot!"
                                ui_manager.current_status['state'] = 'error_recovery'
                            else:
                                ui_manager.update_status_message("Piece detected in slot - processing")
                                if not processing_thread or not processing_thread.is_alive():
                                    processing_thread = threading.Thread(
                                        target=process_piece_fb,
                                        args=(image_processor, ui_manager, gpio_controller, network_status)
                                    )
                                    processing_thread.start()
                            
                            piece_in_progress = False
                            waiting_for_sensor2 = False
                            
            elif ui_manager.current_status['state'] == 'error_recovery':
                if gpio_controller.read_sensor1():
                    ui_manager.update_status_message("Restarting cycle from sensor 1")
                    ui_manager.current_status['state'] = 'normal'
                    piece_in_progress = True
                    waiting_for_sensor2 = False
                    ui_manager.current_status['alert'] = None
                
                elif gpio_controller.read_sensor2():
                    ui_manager.update_status_message("Manual piece placement detected")
                    if not processing_thread or not processing_thread.is_alive():
                        processing_thread = threading.Thread(
                            target=process_piece_fb,
                            args=(image_processor, ui_manager, gpio_controller, network_status)
                        )
                        processing_thread.start()
                    piece_in_progress = False
                    waiting_for_sensor2 = False
            
            # Update UI
            ui_manager.update_display(gpio_controller, network_status)  # Changed from draw to update_display
            
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        ui_manager.cleanup()
        gpio_controller.cleanup()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run the inspection system with either curses or framebuffer UI')
    parser.add_argument('--hdmi', action='store_true', help='Use HDMI output (framebuffer) instead of curses')
    args = parser.parse_args()
    
    if args.hdmi:
        if FBUIManager is None:
            print("Error: Framebuffer UI manager not available. Make sure all required packages are installed.")
            sys.exit(1)
        main_fb()
    else:
        curses.wrapper(main_curses)