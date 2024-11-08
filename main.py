# main.py
import time
import threading
import logging
from datetime import datetime

from config.settings import (
    UI_REFRESH_RATE,
    ROBOFLOW_API_KEY,
    ROBOFLOW_MODEL_ID
)

from core.hardware import GPIOController
from core.network import NetworkManager
from core.processing import ImageProcessor
from core.metrics import MetricsManager
from core.controller import InspectionController
from ui.fb_ui.framebuffer_ui import FramebufferUI
from utils.state_manager import StateManager

class InspectionSystem:
    def __init__(self):
        self.setup_logging()
        self.setup_components()
        self.setup_state_variables()
        
    def setup_logging(self):
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def setup_components(self):
        """Initialize system components"""
        try:
            self.gpio = GPIOController()
            self.network = NetworkManager()
            self.ui = FramebufferUI()
            self.metrics_manager = MetricsManager()
            
            # Initialize ImageProcessor with Roboflow credentials
            if not ROBOFLOW_API_KEY or not ROBOFLOW_MODEL_ID:
                raise ValueError(
                    "Missing Roboflow credentials. Please set ROBOFLOW_API_KEY and "
                    "ROBOFLOW_MODEL_ID environment variables."
                )
            
            self.processor = ImageProcessor(
                status_callback=self.ui.update_status_message
            )
            
            # Initialize controller
            self.controller = InspectionController(self)
            
        except Exception as e:
            self.cleanup()
            raise

    def setup_state_variables(self):
        """Initialize state tracking variables"""
        # Basic state
        self.piece_in_progress = False
        self.waiting_for_sensor2 = False
        self.sensor2_check_time = None
        self.last_network_check = time.time()
        self.processing_thread = None
        self.running = True
        self.analysis_in_progress = False
        
        # Processing state
        self.processing_complete = True
        self.solenoid_locked = False
        self.wait_warning_shown = False
        
        # Solenoid timing
        self.solenoid_deactivation_time = None
        self.solenoid_activation_time = None
        self.last_sensor1_state = False
        
        # Ejection control
        self.ejection_start_time = None
        self.post_ejection_start_time = None
        self.ejection_in_progress = False
        self.post_ejection_delay = False

    def run(self):
        """Main run loop with error handling"""
        try:
            while self.running:
                self.controller.run_state_machine()
                self.ui.update_display(self.gpio, self.network)
                time.sleep(UI_REFRESH_RATE)
                
        except KeyboardInterrupt:
            self.ui.update_status_message("Shutdown requested...")
        except Exception as e:
            self.ui.update_status_message(f"Critical error: {str(e)}", is_alert=True)
        finally:
            self.cleanup()

    def cleanup(self):
        """System cleanup and state saving"""
        self.running = False
        
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2.0)
        
        if hasattr(self, 'gpio'):
            self.gpio.cleanup()
        
        if hasattr(self, 'ui'):
            self.ui.cleanup()
            
        if hasattr(self, 'metrics_manager'):
            StateManager.save_state(
                self.metrics_manager.metrics,
                self.metrics_manager.last_error
            )

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