# ui/fb_ui.py

import os
import io
import mmap
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from .base_ui import BaseUI

class FramebufferUI(BaseUI):
    def __init__(self):
        super().__init__()
        self.fb = self._init_framebuffer()
        
        # Try to load a system font
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)
        except:
            try:
                self.font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSansMono.ttf", 14)
            except:
                self.font = ImageFont.load_default()

        # Create image buffer
        self.image = Image.new('RGB', (self.fb['width'], self.fb['height']), (0, 0, 0))
        self.drawer = ImageDraw.Draw(self.image)

        # Calculate layout dimensions
        self.ui_width = self.fb['width'] // 2
        self.image_width = self.fb['width'] - self.ui_width

        # Pre-compute colors
        self.colors = {
            'black': self._rgb_to_rgb565(0, 0, 0),
            'white': self._rgb_to_rgb565(255, 255, 255),
            'red': self._rgb_to_rgb565(255, 0, 0),
            'green': self._rgb_to_rgb565(0, 255, 0),
            'blue': self._rgb_to_rgb565(0, 0, 255),
            'cyan': self._rgb_to_rgb565(0, 255, 255)
        }

    def _init_framebuffer(self):
        """Initialize framebuffer device for Raspberry Pi"""
        try:
            # Open the framebuffer device
            fb_dev = os.open('/dev/fb0', os.O_RDWR)
            
            # Get framebuffer info using fbset
            fb_info_str = os.popen('fbset -i').read()
            
            # Parse resolution and line length
            width = height = 800  # Default values
            line_length = None
            
            for line in fb_info_str.split('\n'):
                if 'geometry' in line:
                    parts = line.split()
                    width = int(parts[1])
                    height = int(parts[2])
                elif 'LineLength' in line:
                    parts = line.split()
                    line_length = int(parts[2])
            
            # Calculate size based on line length if available
            if line_length:
                size = line_length * height
            else:
                size = width * height * 2  # 16 bits = 2 bytes per pixel
            
            # Memory map the framebuffer
            fb = mmap.mmap(fb_dev, size, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
            
            fb_info = {
                'dev': fb_dev,
                'fb': fb,
                'width': width,
                'height': height,
                'size': size,
                'line_length': line_length or (width * 2)
            }
            
            print(f"Framebuffer initialized: {width}x{height}, 16-bit color")
            return fb_info
            
        except Exception as e:
            print(f"Failed to initialize framebuffer: {e}")
            print("Debugging information:")
            try:
                print(f"Framebuffer device exists: {os.path.exists('/dev/fb0')}")
                print(f"Current user: {os.getlogin()}")
                print(f"Groups: {os.popen('groups').read().strip()}")
                print(f"Framebuffer permissions: {os.popen('ls -l /dev/fb0').read().strip()}")
                print("fbset output:")
                print(os.popen('fbset -i').read().strip())
            except:
                pass
            sys.exit(1)

    def _draw_camera_view(self, x, y, width, height):
        """Draw the camera image or placeholder"""
        # Draw border
        self.drawer.rectangle([x, y, x + width, y + height], outline=(255, 255, 255))
        
        if self.current_image and hasattr(self.current_image, 'mode'):  # Verify it's a valid PIL Image
            try:
                # Create a copy for resizing
                img_copy = self.current_image.copy()
                img_copy.thumbnail((width - 4, height - 4))
                
                # Calculate position to center the image
                img_x = x + 2 + (width - 4 - img_copy.width) // 2
                img_y = y + 2 + (height - 4 - img_copy.height) // 2
                
                # Paste the image
                self.image.paste(img_copy, (img_x, img_y))
                
                # Draw timestamp if available
                if self.image_timestamp:
                    timestamp_str = f"Captured: {self.image_timestamp.strftime('%H:%M:%S')}"
                    self.drawer.text((x + 5, y + 5), timestamp_str, 
                                font=self.font, fill=(255, 255, 0))
            except Exception as e:
                print(f"Error drawing camera view: {e}")
                self._draw_placeholder(x, y, width, height)
        else:
            self._draw_placeholder(x, y, width, height)

    def _draw_placeholder(self, x, y, width, height):
        """Draw placeholder when no image is available"""
        text = "No Camera Image"
        text_bbox = self.drawer.textbbox((0, 0), text, font=self.font)
        text_width = text_bbox[2] - text_bbox[0]
        text_x = x + (width - text_width) // 2
        text_y = y + height // 2 - 10
        self.drawer.text((text_x, text_y), text, font=self.font, fill=(128, 128, 128))

    def update_image(self, image_data):
        """Update the current camera image"""
        if image_data:
            try:
                # Create a fresh BytesIO object
                image_buffer = io.BytesIO(image_data)
                # Load the image fully before storing it
                temp_image = Image.open(image_buffer)
                self.current_image = temp_image.copy()  # Create a fully loaded copy
                self.image_timestamp = datetime.now()
                self.update_status_message("Camera image updated")
            except Exception as e:
                print(f"Error loading image: {e}")
                self.current_image = None
                self.image_timestamp = None
        else:
            self.current_image = None
            self.image_timestamp = None
            self.update_status_message("Camera image cleared")

    def update_display(self, gpio_controller, network_status):
        """Update the framebuffer display"""
        try:
            # Clear the image
            self.drawer.rectangle([0, 0, self.fb['width'], self.fb['height']], fill=(0, 0, 0))

            # Draw title section
            title = "Automated Inspection System"
            title_w = self._get_text_width(title)
            self.drawer.text(((self.ui_width - title_w) // 2, 10), title, 
                         font=self.font, fill=(255, 255, 255))

            # Draw state
            state_str = f"State: {self.current_status['state'].replace('_', ' ').title()}"
            self.drawer.text((10, 40), state_str, font=self.font, fill=(255, 255, 255))

            # Draw sections using original layout
            net_y = self._draw_section("Network Status", "", 10, 70, self.ui_width - 20, 180)
            self._draw_network_status(network_status, 20, net_y)

            sensor_y = self._draw_section("Sensor Status", "", 10, 260, self.ui_width - 20, 100)
            self._draw_sensor_status(gpio_controller, 20, sensor_y)

            if self.current_status['alert']:
                alert_y = self._draw_section("Alert", "", 10, 370, self.ui_width - 20, 60, highlight=True)
                self.drawer.text((20, alert_y), self.current_status['alert'], 
                             font=self.font, fill=(255, 0, 0))

            log_y = self._draw_section("System Log", "", 10, 440, self.ui_width - 20, 170)
            self._draw_log(20, log_y)

            # Draw camera view
            self._draw_camera_view(self.ui_width + 10, 10,
                               self.image_width - 20,
                               self.fb['height'] - 20)

            # Update framebuffer
            self._update_framebuffer()

        except Exception as e:
            print(f"Error updating display: {e}")
            import traceback
            traceback.print_exc()

    def _draw_section(self, title, content, x, y, width, height, highlight=False):
        """Draw a section with title and content using original style"""
        # Draw section box
        self.drawer.rectangle([x, y, x + width, y + height], outline=(255, 255, 255))
        
        # Draw title background
        title_bg_color = (255, 0, 0) if highlight else (0, 0, 255)
        self.drawer.rectangle([x + 1, y + 1, x + width - 1, y + 20], fill=title_bg_color)
        
        # Draw title text
        self.drawer.text((x + 5, y + 2), title, font=self.font, fill=(255, 255, 255))
        
        return y + 22

    def _draw_network_status(self, network_status, x, y):
        """Draw network status with original styling"""
        statuses = network_status.status
        y_offset = 0
        
        for service, info in statuses.items():
            # Main status with color coding
            color = (0, 255, 0) if info.get('status', 'Unknown') == 'Connected' else (255, 0, 0)
            text = f"{service.title()}: {info.get('status', 'Unknown')}"
            self.drawer.text((x, y + y_offset), text, font=self.font, fill=color)
            y_offset += 15
            
            if service in ['camera', 'ai_server']:
                if info.get('ip'):
                    self.drawer.text((x + 20, y + y_offset),
                                f"IP: {info['ip']}", 
                                font=self.font, 
                                fill=(255, 255, 255))
                    y_offset += 12

                if info.get('ping_time'):
                    self.drawer.text((x + 20, y + y_offset),
                                f"Ping: {info['ping_time']}", 
                                font=self.font, 
                                fill=(255, 255, 255))
                    y_offset += 12

                if info.get('last_success'):
                    last_success = network_status.format_last_success(info['last_success'])
                    self.drawer.text((x + 20, y + y_offset),
                                f"Last: {last_success}", 
                                font=self.font, 
                                fill=(255, 255, 255))
                    y_offset += 12
            
            y_offset += 5

    def _draw_sensor_status(self, gpio_controller, x, y):
        """Draw sensor status with original styling"""
        sensor_states = [
            ("Sensor 1", gpio_controller.read_sensor1()),
            ("Sensor 2", gpio_controller.read_sensor2()),
            ("Solenoid", gpio_controller.get_solenoid_state())
        ]
        
        for i, (name, state) in enumerate(sensor_states):
            color = (0, 255, 0) if state else (255, 0, 0)
            status_text = 'Active' if state else 'Inactive'
            text = f"{name}: {status_text}"
            
            # Draw status indicator circle
            circle_x = x + 5
            circle_y = y + (i * 20) + 7
            self.drawer.ellipse([circle_x, circle_y, circle_x + 8, circle_y + 8], fill=color)
            
            # Draw text with padding for circle
            self.drawer.text((x + 20, y + i * 20), text, font=self.font, fill=(255, 255, 255))

    def _draw_log(self, x, y):
        """Draw system log with original styling"""
        visible_messages = self.status_messages[-8:]
        
        for i, message in enumerate(visible_messages):
            color = (255, 0, 0) if 'ALERT:' in message else (
                    0, 255, 255) if 'NETWORK:' in message else (200, 200, 200)
            
            max_chars = 80
            display_message = message[:max_chars] + '...' if len(message) > max_chars else message
            
            self.drawer.text((x, y + i * 15), display_message, font=self.font, fill=color)

    def _get_text_width(self, text):
        """Get text width using current font"""
        if hasattr(self.drawer, 'textlength'):
            return self.drawer.textlength(text, font=self.font)
        else:
            bbox = self.drawer.textbbox((0, 0), text, font=self.font)
            return bbox[2] - bbox[0]

    def _rgb_to_rgb565(self, r, g, b):
        """Convert RGB888 to RGB565"""
        r = (r >> 3) & 0x1F
        g = (g >> 2) & 0x3F
        b = (b >> 3) & 0x1F
        return (r << 11) | (g << 5) | b

    def _update_framebuffer(self):
        """Convert PIL image to framebuffer format and update display"""
        # Convert PIL image to numpy array
        image_array = np.array(self.image)
        height, width, _ = image_array.shape
        
        # Create numpy arrays for RGB components
        r = image_array[:, :, 0].astype(np.uint16)
        g = image_array[:, :, 1].astype(np.uint16)
        b = image_array[:, :, 2].astype(np.uint16)
        
        # Convert to RGB565 format
        rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        
        # Convert to bytes in correct order
        fb_bytes = np.zeros((height, width, 2), dtype=np.uint8)
        fb_bytes[:, :, 0] = rgb565 & 0xFF  # Low byte
        fb_bytes[:, :, 1] = (rgb565 >> 8) & 0xFF  # High byte
        
        # Write to framebuffer
        self.fb['fb'].seek(0)
        self.fb['fb'].write(fb_bytes.tobytes())