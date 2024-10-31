# src/ui/components/network.py
from PIL import ImageDraw, ImageFont
from typing import Dict, Any, Tuple
from ..layout import Layout

class NetworkComponent:
    """Handles rendering of network status"""
    
    def __init__(self, font: ImageFont.FreeTypeFont, layout: Layout):
        self.font = font
        self.layout = layout

    def draw(self, draw: ImageDraw.ImageDraw, x: int, y: int, width: int,
             network_status: Dict[str, Any]):
        """Draw the network status section"""
        height = self.layout.network_height
        
        # Draw section box
        self._draw_section_box(draw, "Network Status", x, y, width, height)
        content_y = y + 22
        
        # Draw status for each service
        y_offset = 0
        for service_name, service_status in network_status.status.items():
            y_offset = self._draw_service_status(
                draw, x, content_y, y_offset, service_name, service_status
            )

    def _draw_service_status(self, draw: ImageDraw.ImageDraw, x: int, content_y: int,
                           y_offset: int, service_name: str, service_status: Dict[str, Any]) -> int:
        """Draw status information for a single service"""
        status_str = service_status.get('status', 'Unknown')
        status_color = self._get_status_color(status_str)
        
        # Draw main status
        text = f"{service_name.title()}: {status_str}"
        draw.text(
            (x + 20, content_y + y_offset),
            text,
            font=self.font,
            fill=status_color
        )
        y_offset += 15
        
        # Draw additional details for camera and ai_server
        if service_name in ['camera', 'ai_server']:
            y_offset = self._draw_service_details(
                draw, x, content_y, y_offset, service_status
            )
        
        return y_offset + 5

    def _draw_service_details(self, draw: ImageDraw.ImageDraw, x: int, content_y: int,
                            y_offset: int, service_status: Dict[str, Any]) -> int:
        """Draw detailed status information for a service"""
        details = [
            ('IP', service_status.get('ip')),
            ('Ping', f"{service_status.get('ping_time', 0):.1f}ms" 
             if service_status.get('ping_time') is not None else None),
            ('Last Success', service_status.get('last_success'))
        ]
        
        for label, value in details:
            if value:
                draw.text(
                    (x + 40, content_y + y_offset),
                    f"{label}: {value}",
                    font=self.font,
                    fill=(255, 255, 255)
                )
                y_offset += 12
        
        return y_offset

    @staticmethod
    def _get_status_color(status: str) -> Tuple[int, int, int]:
        """Get appropriate color for status text"""
        status_colors = {
            'Connected': (0, 255, 0),
            'Disconnected': (255, 0, 0),
            'Unknown': (255, 255, 0)
        }
        return status_colors.get(status, (255, 255, 255))