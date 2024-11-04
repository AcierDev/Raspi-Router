# src/ui/components/alerts.py
from PIL import ImageDraw, ImageFont
from typing import Optional
from ..layout import Layout

class AlertComponent:
    """Handles rendering of system alerts"""
    
    def __init__(self, font: ImageFont.FreeTypeFont, layout: Layout):
        self.font = font
        self.layout = layout

    def draw(self, draw: ImageDraw.ImageDraw, x: int, y: int, width: int,
             alert_message: Optional[str]) -> None:
        """Draw the alert section if there's an active alert"""
        if not alert_message:
            return
            
        height = self.layout.alert_height
        
        # Draw section box with highlight
        self._draw_section_box(draw, "Alert", x, y, width, height, highlight=True)
        content_y = y + 22
        
        # Draw alert message with word wrap
        self._draw_wrapped_text(
            draw,
            alert_message,
            x + 20,
            content_y,
            width - 40,
            fill=(255, 0, 0)
        )