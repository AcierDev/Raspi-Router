import os
import mmap
import sys
from typing import Dict, Any

class FramebufferDevice:
    """Manages the framebuffer device interface"""
    
    def __init__(self):
        self.fb_info = self._init_framebuffer()

    def _init_framebuffer(self) -> Dict[str, Any]:
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
            self._print_debug_info()
            sys.exit(1)

    def _print_debug_info(self):
        """Print debugging information for framebuffer initialization"""
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

    def update_display(self, image_data: bytes) -> None:
        """Write image data to framebuffer"""
        try:
            self.fb_info['fb'].seek(0)
            self.fb_info['fb'].write(image_data)
        except Exception as e:
            print(f"Error updating framebuffer: {e}")

    def cleanup(self) -> None:
        """Clean up framebuffer resources"""
        try:
            if hasattr(self, 'fb_info'):
                self.fb_info['fb'].close()
                os.close(self.fb_info['dev'])
        except Exception as e:
            print(f"Error cleaning up framebuffer: {e}")

    def get_dimensions(self) -> tuple:
        """Get framebuffer dimensions"""
        return (self.fb_info['width'], self.fb_info['height'])

    def convert_rgb_to_fb(self, r: int, g: int, b: int) -> int:
        """Convert RGB color to framebuffer format"""
        r = (r >> 3) & 0x1F
        g = (g >> 2) & 0x3F
        b = (b >> 3) & 0x1F
        return (r << 11) | (g << 5) | b