import os
import sys
from datetime import datetime
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
import mmap
from config import MAX_LOG_MESSAGES
import io

class FBUIManager:
    def __init__(self):
        self.status_messages = []
        self.current_status = {
            'state': 'normal',
            'alert': None,
            'last_inference': None,
            'last_confidence': None,
            'system_status': 'Running'
        }
        self.current_image = None
        self.image_timestamp = None  # Add timestamp for image tracking
        
        # Initialize framebuffer
        self.fb = self._init_framebuffer()
        
        # Try to load a system font
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)
        except:
            try:
                self.font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSansMono.ttf", 14)
            except:
                self.font = ImageFont.load_default()
        
        # Create an image buffer
        self.image = Image.new('RGB', (self.fb['width'], self.fb['height']), (0, 0, 0))
        self.draw = ImageDraw.Draw(self.image)

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

    def clear_image(self):
        """Clear the current camera image"""
        self.current_image = None
        self.image_timestamp = None
        self.update_status_message("Camera view cleared")

    def set_current_image(self, image_data):
        """Update the current camera image"""
        if image_data:
            try:
                # Convert bytes to PIL Image
                self.current_image = Image.open(io.BytesIO(image_data))
                self.image_timestamp = datetime.now()
                self.update_status_message("Camera image updated")
            except Exception as e:
                print(f"Error loading image: {e}")
                self.current_image = None
                self.image_timestamp = None
        else:
            self.current_image = None
            self.image_timestamp = None

    def _draw_camera_view(self, x, y, width, height):
        """Draw the camera image or placeholder"""
        # Draw border
        self.draw.rectangle([x, y, x + width, y + height], outline=(255, 255, 255))
        
        if self.current_image:
            # Resize image to fit the area while maintaining aspect ratio
            img_copy = self.current_image.copy()
            img_copy.thumbnail((width - 4, height - 4), Image.Resampling.LANCZOS)
            
            # Calculate position to center the image
            img_x = x + 2 + (width - 4 - img_copy.width) // 2
            img_y = y + 2 + (height - 4 - img_copy.height) // 2
            
            # Paste the image
            self.image.paste(img_copy, (img_x, img_y))
            
            # Draw timestamp if available
            if self.image_timestamp:
                timestamp_str = f"Captured: {self.image_timestamp.strftime('%H:%M:%S')}"
                self.draw.text((x + 5, y + 5), timestamp_str, font=self.font, fill=(255, 255, 0))
        else:
            # Draw placeholder text
            text = "No Camera Image"
            text_bbox = self.draw.textbbox((0, 0), text, font=self.font)
            text_width = text_bbox[2] - text_bbox[0]
            text_x = x + (width - text_width) // 2
            text_y = y + height // 2 - 10
            self.draw.text((text_x, text_y), text, font=self.font, fill=(128, 128, 128))

    def update_display(self, gpio_controller, network_status):
        """Draw the entire UI"""
        try:
            # Clear the image
            self.draw.rectangle([0, 0, self.fb['width'], self.fb['height']], fill=(0, 0, 0))
            
            # Draw title
            title = "Automated Inspection System"
            title_w = self._get_text_width(title)
            self.draw.text(((self.ui_width - title_w) // 2, 10), title, font=self.font, fill=(255, 255, 255))
            
            # Draw state
            state_str = f"State: {self.current_status['state'].replace('_', ' ').title()}"
            self.draw.text((10, 40), state_str, font=self.font, fill=(255, 255, 255))
            
            # Network status section - increased height from 150 to 180
            net_y = self._draw_section("Network Status", "", 10, 70, self.ui_width - 20, 180)
            self._draw_network_status(network_status, 20, net_y)
            
            # Sensor status section - moved down by 30 pixels
            sensor_y = self._draw_section("Sensor Status", "", 10, 260, self.ui_width - 20, 100)
            self._draw_sensor_status(gpio_controller, 20, sensor_y)
            
            # Alert section (if any) - moved down accordingly
            if self.current_status['alert']:
                alert_y = self._draw_section("Alert", "", 10, 370, self.ui_width - 20, 60, highlight=True)
                self.draw.text((20, alert_y), self.current_status['alert'], font=self.font, fill=(255, 0, 0))
            
            # Log section - adjusted position and height
            log_y = self._draw_section("System Log", "", 10, 440, self.ui_width - 20, 170)
            self._draw_log(20, log_y)
            
            # Draw camera view on right half
            self._draw_camera_view(self.ui_width + 10, 10, 
                                self.image_width - 20, 
                                self.fb['height'] - 20)
            
            # Convert PIL image to framebuffer format
            image_array = np.array(self.image)
            height, width, _ = image_array.shape
            
            # Create numpy arrays for RGB components
            r = image_array[:, :, 0].astype(np.uint16)
            g = image_array[:, :, 1].astype(np.uint16)
            b = image_array[:, :, 2].astype(np.uint16)
            
            # Convert to RGB565 using numpy operations
            rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
            
            # Convert to bytes in correct order
            fb_bytes = np.zeros((height, width, 2), dtype=np.uint8)
            fb_bytes[:, :, 0] = rgb565 & 0xFF  # Low byte
            fb_bytes[:, :, 1] = (rgb565 >> 8) & 0xFF  # High byte
            
            # Reshape and write to framebuffer
            self.fb['fb'].seek(0)
            self.fb['fb'].write(fb_bytes.tobytes())
            
        except Exception as e:
            print(f"Error drawing to framebuffer: {e}")
            import traceback
            traceback.print_exc()

    def _get_text_width(self, text):
        """Get the width of text using the current font"""
        if hasattr(self.draw, 'textlength'):
            return self.draw.textlength(text, font=self.font)
        else:
            bbox = self.draw.textbbox((0, 0), text, font=self.font)
            return bbox[2] - bbox[0]

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

    def _rgb_to_rgb565(self, r, g, b):
        """Convert RGB888 to RGB565"""
        r = (r >> 3) & 0x1F
        g = (g >> 2) & 0x3F
        b = (b >> 3) & 0x1F
        return (r << 11) | (g << 5) | b

    def update_status_message(self, message, is_alert=False, is_network=False):
        """Update the status message list with a new message"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        prefix = "ALERT: " if is_alert else "NETWORK: " if is_network else ""
        self.status_messages.append(f"[{timestamp}] {prefix}{message}")
        if len(self.status_messages) > MAX_LOG_MESSAGES:
            self.status_messages.pop(0)

    def _draw_section(self, title, content, x, y, width, height, highlight=False):
        """Draw a section with title and content"""
        # Draw section box
        self.draw.rectangle([x, y, x + width, y + height], outline=(255, 255, 255))
        
        # Draw title background
        title_bg_color = (255, 0, 0) if highlight else (0, 0, 255)
        self.draw.rectangle([x + 1, y + 1, x + width - 1, y + 20], fill=title_bg_color)
        
        # Draw title text
        self.draw.text((x + 5, y + 2), title, font=self.font, fill=(255, 255, 255))
        
        return y + 22  # Return the y position for content

    def cleanup(self):
        """Clean up framebuffer resources"""
        if hasattr(self, 'fb'):
            if self.fb.get('fb'):
                self.fb['fb'].close()
            if self.fb.get('dev') is not None:
                os.close(self.fb['dev'])

    def _draw_network_status(self, network_status, x, y):
        """Draw network status information with optimized spacing"""
        statuses = network_status.status
        y_offset = 0
        
        for service, info in statuses.items():
            # Main status with color coding
            color = (0, 255, 0) if info.get('status', 'Unknown') == 'Connected' else (255, 0, 0)
            text = f"{service.title()}: {info.get('status', 'Unknown')}"
            self.draw.text((x, y + y_offset), text, font=self.font, fill=color)
            y_offset += 15  # Reduced from 20
            
            # Additional details for camera and ai_server
            if service in ['camera', 'ai_server']:
                # Show IP if available
                if info.get('ip'):
                    self.draw.text((x + 20, y + y_offset),
                                f"IP: {info['ip']}", 
                                font=self.font, 
                                fill=(255, 255, 255))
                    y_offset += 12  # Reduced from 15
                
                # Show ping time if available
                if info.get('ping_time'):
                    self.draw.text((x + 20, y + y_offset),
                                f"Ping: {info['ping_time']}", 
                                font=self.font, 
                                fill=(255, 255, 255))
                    y_offset += 12  # Reduced from 15
                    
                # Show last successful connection if available
                if info.get('last_success'):
                    last_success = network_status.format_last_success(info['last_success'])
                    self.draw.text((x + 20, y + y_offset),
                                f"Last: {last_success}", 
                                font=self.font, 
                                fill=(255, 255, 255))
                    y_offset += 12  # Reduced from 15
            
            y_offset += 5  # Spacing between services

    def _draw_sensor_status(self, gpio_controller, x, y):
        """Draw sensor status information"""
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
            self.draw.ellipse([circle_x, circle_y, circle_x + 8, circle_y + 8], fill=color)
            
            # Draw text with padding for circle
            self.draw.text((x + 20, y + i * 20), text, font=self.font, fill=(255, 255, 255))

    def _draw_log(self, x, y):
        """Draw system log messages"""
        visible_messages = self.status_messages[-8:]  # Reduced from 10 to 8 messages
        
        for i, message in enumerate(visible_messages):
            color = (255, 0, 0) if 'ALERT:' in message else (0, 255, 255) if 'NETWORK:' in message else (200, 200, 200)
            
            # Truncate message if too long
            max_chars = 45  # Adjusted for display width
            display_message = message[:max_chars] + '...' if len(message) > max_chars else message
            
            self.draw.text((x, y + i * 15), display_message, font=self.font, fill=color)