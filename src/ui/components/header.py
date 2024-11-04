# src/ui/components/header.py
from PIL import ImageDraw, ImageFont
from typing import Tuple
from ..layout import Layout

class HeaderComponent:
    """Handles rendering of the header section"""
    
    def __init__(self, font: ImageFont.FreeTypeFont, layout: Layout):
        self.font = font
        self.layout = layout

    def draw(self, draw: ImageDraw.ImageDraw, state: str):
        """Draw the header section"""
        title = "Automated Inspection System"
        
        # Calculate title position
        title_bbox = draw.textbbox((0, 0), title, font=self.font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (self.layout.ui_width - title_width) // 2
        
        # Draw title
        draw.text(
            (title_x, 10),
            title,
            font=self.font,
            fill=(255, 255, 255)
        )
        
        # Draw system state
        state_str = f"State: {state.replace('_', ' ').title()}"
        draw.text(
            (10, 40),
            state_str,
            font=self.font,
            fill=(255, 255, 255)
        )