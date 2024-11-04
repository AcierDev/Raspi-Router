# src/ui/components/sensors.py
from PIL import ImageDraw, ImageFont
from typing import List, Tuple
from ..layout import Layout

class SensorsComponent:
    """Handles rendering of sensor status"""
    
    def __init__(self, font: ImageFont.FreeTypeFont, layout: Layout):
        self.font = font
        self.layout = layout

    def draw(self, draw: ImageDraw.ImageDraw, x: int, y: int, width: int,
             gpio_controller) -> None:
        """Draw the sensor status section"""
        height = self.layout.sensor_height
        
        # Draw section box
        self._draw_section_box(draw, "Sensor Status", x, y, width, height)
        content_y = y + 22
        
        # Get sensor states
        sensor_states = [
            ("Sensor 1", gpio_controller.read_sensor1()),
            ("Sensor 2", gpio_controller.read_sensor2()),
            ("Solenoid", gpio_controller.get_solenoid_state())
        ]
        
        # Draw each sensor status
        self._draw_sensor_states(draw, x, content_y, sensor_states)

    def _draw_sensor_states(self, draw: ImageDraw.ImageDraw, x: int, content_y: int,
                           sensor_states: List[Tuple[str, bool]]) -> None:
        """Draw status indicators for all sensors"""
        for i, (name, state) in enumerate(sensor_states):
            color = (0, 255, 0) if state else (255, 0, 0)
            status_text = 'Active' if state else 'Inactive'
            
            # Draw indicator circle
            circle_x = x + 25
            circle_y = content_y + (i * 20) + 7
            draw.ellipse(
                [circle_x, circle_y, circle_x + 8, circle_y + 8],
                fill=color
            )
            
            # Draw status text
            draw.text(
                (circle_x + 20, content_y + i * 20),
                f"{name}: {status_text}",
                font=self.font,
                fill=(255, 255, 255)
            )