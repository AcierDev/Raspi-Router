# ui/fb_ui/framebuffer_ui.py
import os
import io
import sys
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from .fb_device import FramebufferDevice
from .metrics_manager import MetricsManager
from .ui_components import UIComponentDrawer
from .image_processor import ImageProcessor
from ..base_ui import BaseUI

class FramebufferUI(BaseUI):
    def __init__(self):
        super().__init__()
        self.fb = FramebufferDevice()._init_framebuffer()
        self.metrics = MetricsManager()
        self.ui_drawer = UIComponentDrawer()
        self.image_processor = ImageProcessor()
        self.current_predictions = None
        self.last_draw_time = None
        self.REDRAW_INTERVAL = 1.0
        
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)
            self.small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 10)
        except:
            try:
                self.font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSansMono.ttf", 14)
                self.small_font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSansMono.ttf", 10)
            except:
                self.font = ImageFont.load_default()
                self.small_font = ImageFont.load_default()

        self.image = Image.new('RGB', (self.fb['width'], self.fb['height']), (0, 0, 0))
        self.drawer = ImageDraw.Draw(self.image)
        
        self.ui_width = self.fb['width'] // 2
        self.image_width = self.fb['width'] - self.ui_width
        self.image_display_size = (936, 936)

    def start_processing(self):
        self.metrics.start_processing()

    def get_processing_start_time(self):
        return self.metrics.get_current_processing_start()

    def update_metrics(self, results=None, error=None, processing_time=None):
        self.metrics.update_metrics(results, error, processing_time)

    def update_predictions(self, predictions):
        try:
            print("Updating predictions:", predictions is not None)
            self.current_predictions = predictions
            if predictions:
                print(f"Number of predictions: {len(predictions.get('predictions', []))}")
                print(f"First prediction: {predictions['predictions'][0] if predictions['predictions'] else 'None'}")
            self.update_status_message("Updated detection display")
        except Exception as e:
            print(f"Error in update_predictions: {e}")
            import traceback
            traceback.print_exc()

    def update_image(self, image_data):
        self.image_processor.update_image(image_data, self)

    def update_display(self, gpio_controller, network_status):
        current_time = datetime.now()
        
        if self.last_draw_time and (current_time - self.last_draw_time).total_seconds() < self.REDRAW_INTERVAL:
            return
            
        try:
            # Clear the image
            self.drawer.rectangle([0, 0, self.fb['width'], self.fb['height']], fill=(0, 0, 0))
            
            # Draw all components using UIComponentDrawer
            self.ui_drawer.draw_all_components(self, gpio_controller, network_status)
            
            # Update framebuffer
            self.image_processor._update_framebuffer(self)
            self.last_draw_time = current_time
            
        except Exception as e:
            print(f"Error updating display: {e}")
            import traceback
            traceback.print_exc()