# src/ui/fb_manager.py
import logging
from datetime import datetime
from typing import List, Optional
from PIL import Image, ImageDraw, ImageFont
import io
import numpy as np

from .state import UIState
from .layout import LayoutManager
from .framebuffer import FramebufferManager
from .colors import ColorManager
from .components.header import HeaderComponent
from .components.network import NetworkComponent
from .components.camera import CameraComponent

logger = logging.getLogger(__name__)

class FBUIManager:
    """Manages framebuffer-based UI rendering with efficient updates"""

    def __init__(self, max_log_messages: int = 8):
        """
        Initialize the UI manager.
        
        Args:
            max_log_messages: Maximum number of log messages to display
        """
        self.status_messages = []
        self.current_status = UIState()
        self.current_image: Optional[Image.Image] = None
        self.image_timestamp: Optional[datetime] = None
        self.max_log_messages = max_log_messages
        
        # Initialize framebuffer
        self.fb = FramebufferManager.init_framebuffer()
        
        # Initialize font
        self.font = self._init_font()
        
        # Create image buffer for double buffering
        self.image = Image.new('RGB', (self.fb.width, self.fb.height), (0, 0, 0))
        self.draw = ImageDraw.Draw(self.image)
        
        # Calculate layout
        self.layout = LayoutManager.calculate_layout(self.fb.width, self.fb.height)
        
        # Initialize components
        self.components = {
            'header': HeaderComponent(self.font, self.layout),
            'network': NetworkComponent(self.font, self.layout),
            'sensors': SensorsComponent(self.font, self.layout),
            'alerts': AlertComponent(self.font, self.layout),
            'logs': LogComponent(self.font, self.layout),
            'camera': CameraComponent(self.font, self.layout)
        }
        
        logger.info("FBUIManager initialized successfully")

    def _init_font(self) -> ImageFont.FreeTypeFont:
        """Initialize system font with fallbacks"""
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf"
        ]
        
        for font_path in font_paths:
            if Path(font_path).exists():
                try:
                    return ImageFont.truetype(font_path, 14)
                except Exception as e:
                    logger.warning(f"Failed to load font {font_path}: {e}")
        
        logger.warning("No system fonts found, using default font")
        return ImageFont.load_default()

    def clear_image(self):
        """Clear the current camera image"""
        self.current_image = None
        self.image_timestamp = None
        self.update_status_message("Camera view cleared")

    def set_current_image(self, image_data: bytes):
        """Update the current camera image with verification"""
        if not image_data:
            self.clear_image()
            return

        try:
            image_buffer = io.BytesIO(image_data)
            temp_image = Image.open(image_buffer)
            
            # Verify image
            if temp_image.size[0] < 10 or temp_image.size[1] < 10:
                raise ValueError("Image dimensions too small")
            
            # Create a copy in RGB mode
            if temp_image.mode != 'RGB':
                temp_image = temp_image.convert('RGB')
            
            self.current_image = temp_image.copy()
            self.image_timestamp = datetime.now()
            self.update_status_message("Camera image updated")
            
        except Exception as e:
            logger.error(f"Error loading image: {e}")
            self.current_image = None
            self.image_timestamp = None
            self.update_status_message(f"Error loading image: {str(e)}")

    def update_status_message(self, message: str, is_alert: bool = False, is_network: bool = False):
        """Update status messages with timestamps"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        prefix = "ALERT: " if is_alert else "NETWORK: " if is_network else ""
        self.status_messages.append(f"[{timestamp}] {prefix}{message}")
        
        while len(self.status_messages) > self.max_log_messages:
            self.status_messages.pop(0)

    def update_display(self, gpio_controller, network_status):
        """Update the display with double buffering"""
        try:
            # Clear the image
            self.draw.rectangle([0, 0, self.fb.width, self.fb.height], fill=(0, 0, 0))
            
            # Draw UI components
            self.components['header'].draw(
                self.draw,
                self.current_status.state
            )
            
            self.components['network'].draw(
                self.draw,
                10,
                70,
                self.layout.ui_width - 20,
                network_status
            )
            
            self.components['sensors'].draw(
                self.draw,
                10,
                260,
                self.layout.ui_width - 20,
                gpio_controller
            )
            
            if self.current_status.alert:
                self.components['alerts'].draw(
                    self.draw,
                    10,
                    370,
                    self.layout.ui_width - 20,
                    self.current_status.alert
                )
            
            self.components['logs'].draw(
                self.draw,
                10,
                440,
                self.layout.ui_width - 20,
                self.status_messages,
                self.max_log_messages
            )
            
            self.components['camera'].draw(
                self.draw,
                self.current_image,
                self.layout.ui_width + 10,
                10,
                self.layout.image_width - 20,
                self.fb.height - 20,
                self.image_timestamp,
                self.current_status.last_inference,
                self.current_status.last_confidence
            )
            
            # Convert image to framebuffer format
            self._write_to_framebuffer()
            
        except Exception as e:
            logger.error(f"Error updating display: {e}")
            self.update_status_message(f"Display error: {str(e)}", is_alert=True)

    def _write_to_framebuffer(self):
        """Convert and write image data to framebuffer"""
        try:
            # Convert PIL image to numpy array
            image_array = np.array(self.image)
            height, width, _ = image_array.shape
            
            # Create RGB565 data
            r = image_array[:, :, 0].astype(np.uint16)
            g = image_array[:, :, 1].astype(np.uint16)
            b = image_array[:, :, 2].astype(np.uint16)
            
            rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
            
            # Convert to bytes
            fb_bytes = np.zeros((height, width, 2), dtype=np.uint8)
            fb_bytes[:, :, 0] = rgb565 & 0xFF
            fb_bytes[:, :, 1] = (rgb565 >> 8) & 0xFF
            
            # Write to framebuffer
            self.fb.fb.seek(0)
            self.fb.fb.write(fb_bytes.tobytes())
            
        except Exception as e:
            logger.error(f"Error writing to framebuffer: {e}")
            raise

    def cleanup(self):
        """Clean up resources"""
        try:
            if hasattr(self, 'fb'):
                if self.fb.fb:
                    self.fb.fb.close()
                if self.fb.dev is not None:
                    os.close(self.fb.dev)
            logger.info("UI resources cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")