# ui/fb_ui/fb_device.py
import os
import mmap
import sys

class FramebufferDevice:
    def _init_framebuffer(self):
        """Initialize framebuffer device for Raspberry Pi"""
        try:
            fb_dev = os.open('/dev/fb0', os.O_RDWR)
            fb_info_str = os.popen('fbset -i').read()
            
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
            
            if line_length:
                size = line_length * height
            else:
                size = width * height * 2
            
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