# src/ui/components/logs.py
from PIL import ImageDraw, ImageFont
from typing import List, Tuple
from ..layout import Layout

class LogComponent:
    """Handles rendering of system logs"""
    
    def __init__(self, font: ImageFont.FreeTypeFont, layout: Layout):
        self.font = font
        self.layout = layout

    def draw(self, draw: ImageDraw.ImageDraw, x: int, y: int, width: int,
             messages: List[str], max_messages: int) -> None:
        """Draw the system log section"""
        height = self.layout.log_height
        
        # Draw section box
        self._draw_section_box(draw, "System Log", x, y, width, height)
        content_y = y + 22
        
        # Get visible messages
        visible_messages = messages[-max_messages:]
        
        # Draw each message
        for i, message in enumerate(visible_messages):
            color = self._get_message_color(message)
            
            # Truncate message if too long
            display_message = self._truncate_text(
                draw,
                message,
                width - 30,
                self.font
            )
            
            # Draw message
            draw.text(
                (x + 15, content_y + i * 15),
                display_message,
                font=self.font,
                fill=color
            )

    @staticmethod
    def _get_message_color(message: str) -> Tuple[int, int, int]:
        """Get appropriate color for log message"""
        if 'ALERT:' in message:
            return (255, 0, 0)
        elif 'NETWORK:' in message:
            return (0, 255, 255)
        return (200, 200, 200)