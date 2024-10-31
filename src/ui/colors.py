# src/ui/colors.py
from typing import Dict, Tuple

class ColorManager:
    """Manages color operations and conversions"""
    
    @staticmethod
    def rgb_to_rgb565(r: int, g: int, b: int) -> int:
        """Convert RGB888 to RGB565 format"""
        r = (r >> 3) & 0x1F
        g = (g >> 2) & 0x3F
        b = (b >> 3) & 0x1F
        return (r << 11) | (g << 5) | b

    @staticmethod
    def get_color_palette() -> Dict[str, Tuple[int, int, int]]:
        """Get the default color palette"""
        return {
            'black': (0, 0, 0),
            'white': (255, 255, 255),
            'red': (255, 0, 0),
            'green': (0, 255, 0),
            'blue': (0, 0, 255),
            'cyan': (0, 255, 255),
            'yellow': (255, 255, 0),
            'gray': (128, 128, 128)
        }
