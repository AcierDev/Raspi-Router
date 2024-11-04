# src/ui/framebuffer.py
import os
import mmap
import logging
from dataclasses import dataclass
from typing import Dict
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class FramebufferInfo:
    """Stores framebuffer device information"""
    dev: int
    fb: mmap.mmap
    width: int
    height: int
    size: int
    line_length: int
    bits_per_pixel: int = 16  # Assuming RGB565

class FramebufferManager:
    """Handles framebuffer initialization and raw pixel operations"""
    
    @staticmethod
    def init_framebuffer() -> FramebufferInfo:
        """Initialize framebuffer device with error handling"""
        try:
            # Check for framebuffer device
            if not os.path.exists('/dev/fb0'):
                raise RuntimeError("Framebuffer device not found")

            # Open the framebuffer device
            fb_dev = os.open('/dev/fb0', os.O_RDWR)
            
            # Get framebuffer info
            fb_info = FramebufferManager._get_fb_info()
            
            # Calculate size and map memory
            size = fb_info['size']
            fb = mmap.mmap(fb_dev, size, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
            
            return FramebufferInfo(
                dev=fb_dev,
                fb=fb,
                width=fb_info['width'],
                height=fb_info['height'],
                size=size,
                line_length=fb_info['line_length']
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize framebuffer: {e}")
            FramebufferManager._log_fb_debug_info()
            raise

    @staticmethod
    def _get_fb_info() -> Dict[str, int]:
        """Get framebuffer information using fbset"""
        try:
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
            
            if not line_length:
                line_length = width * 2  # Assume 16-bit color
            
            return {
                'width': width,
                'height': height,
                'line_length': line_length,
                'size': line_length * height
            }
        except Exception as e:
            logger.error(f"Error getting framebuffer info: {e}")
            raise

    @staticmethod
    def _log_fb_debug_info():
        """Log debug information for framebuffer initialization"""
        logger.debug("Framebuffer Debug Information:")
        try:
            logger.debug(f"Framebuffer device exists: {os.path.exists('/dev/fb0')}")
            logger.debug(f"Current user: {os.getlogin()}")
            logger.debug(f"Groups: {os.popen('groups').read().strip()}")
            logger.debug(f"Framebuffer permissions: {os.popen('ls -l /dev/fb0').read().strip()}")
            logger.debug("fbset output:")
            logger.debug(os.popen('fbset -i').read().strip())
        except Exception as e:
            logger.error(f"Error collecting debug info: {e}")