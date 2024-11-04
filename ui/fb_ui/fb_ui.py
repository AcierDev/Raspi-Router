from PIL import Image, ImageDraw
import time
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from ..base_ui.base_ui import BaseUI
from ..base_ui.drawing import DrawingUtils
from .framebuffer import FramebufferDevice
from .image_display import ImageDisplayManager
from .section_renderer import SectionRenderer

class FramebufferUI(BaseUI):
    """Main framebuffer UI implementation"""
    
    def __init__(self):
        super().__init__()
        self.fb = FramebufferDevice()
        self.drawer = None
        self.image = None
        self.last_draw_time = None
        self.REDRAW_INTERVAL = 1.0
        
        # Initialize components
        self.drawing = DrawingUtils()
        self.image_display = ImageDisplayManager(self.drawing)
        self.renderer = SectionRenderer(self.drawing)

        
        # Calculate dimensions
        self.fb_width, self.fb_height = self.fb.get_dimensions()
        self.ui_width = self.fb_width // 2
        self.image_width = self.fb_width - self.ui_width
        
        # Initialize drawing surface
        self._init_drawing_surface()

    def _init_drawing_surface(self) -> None:
        """Initialize the PIL Image and ImageDraw objects"""
        self.image = Image.new('RGB', (self.fb_width, self.fb_height), (0, 0, 0))
        self.drawer = ImageDraw.Draw(self.image)

    def update_display(self, gpio_controller: Any, network_status: Any) -> None:
        """Update the framebuffer display with all UI elements"""
        current_time = time.time()

        if (self.last_draw_time and
            (current_time - self.last_draw_time) < self.REDRAW_INTERVAL):
            return

        try:
            # Clear the image
            self._clear_display()

            # Draw title
            self._draw_title()

            # Draw state
            state_y = self._draw_state()
            current_y = state_y + self.drawing.LINE_HEIGHT + 10

            # Check if there's an active alert
            has_alert = bool(self.status.current_status.get('alert'))

            # Calculate total height needed for all sections
            total_height = self.renderer.calculate_total_height(
                self.metrics.metrics,
                network_status,
                has_alert,
                self.status.get_visible_messages()
            )

            # If total height exceeds framebuffer height, reduce section gap
            if total_height > self.fb_height:
                self.drawing.SECTION_GAP = 5  # Reduce gap if content overflows

            # Draw sections below title and state
            current_y = self._draw_sections(current_y, gpio_controller, network_status)

            # Draw camera view, if applicable
            self._draw_camera_view()

            # Update framebuffer with the drawn content
            self._update_framebuffer()
            self.last_draw_time = current_time

        except Exception as e:
            print(f"Error updating display: {e}")
            import traceback
            traceback.print_exc()



    def _clear_display(self) -> None:
        """Clear the display surface"""
        self.drawer.rectangle([0, 0, self.fb_width, self.fb_height], fill=(0, 0, 0))

    def _draw_title(self) -> None:
        """Draw the main title"""
        title = "Automated Inspection System"
        title_w = self.drawing.get_text_width(self.drawer, title)
        self.drawer.text(((self.ui_width - title_w) // 2, 10),
                        title, font=self.drawing.font, fill=(255, 255, 255))

    def _draw_state(self) -> int:
        """Draw current state information"""
        state_y = 40  # Below title
        state_str = f"State: {self.status.current_status['state'].replace('_', ' ').title()}"
        self.drawer.text((10, state_y), state_str,
                        font=self.drawing.font, fill=(255, 255, 255))
        return state_y

    def _draw_boxed_section(self, title: str, start_y: int, content_height: int, padding: int = 10) -> Tuple[int, int]:
        """Draw a boxed section with a title"""
        box_x = 10
        box_width = self.ui_width - 20
        header_height = self.drawing.LINE_HEIGHT + padding

        # Draw the outer box
        self.drawer.rectangle(
            [box_x, start_y, box_x + box_width, start_y + content_height + header_height],
            outline=(255, 255, 255), width=2
        )
        
        # Draw the header background
        self.drawer.rectangle(
            [box_x, start_y, box_x + box_width, start_y + header_height],
            fill=(50, 50, 50)
        )
        
        # Draw the header text
        title_w = self.drawing.get_text_width(self.drawer, title)
        self.drawer.text(
            (box_x + (box_width - title_w) // 2, start_y + padding // 2),
            title, font=self.drawing.font, fill=(255, 255, 255)
        )
        
        # Return the start of content area
        return start_y + header_height + padding, box_x + padding

    def _draw_sections(self, start_y: int, gpio_controller: Any, network_status: Any) -> int:
        """Draw all UI sections with headers in boxes, dynamically positioned to avoid overlap"""
        current_y = start_y

        # Draw each section with calculated height and spacing
        sections = [
            ("System Metrics", self.renderer._calculate_metrics_height(), 
            lambda y: self.drawing.draw_metrics(self.drawer, self.metrics.metrics, 10, y, self.ui_width - 20)),
            
            ("Network Status", self.renderer._calculate_network_height(network_status),
            lambda y: self.drawing.draw_network_status(self.drawer, network_status.status, 10, y)),
            
            ("Sensor Status", self.renderer._calculate_sensor_height(),
            lambda y: self.drawing.draw_sensor_status(self.drawer, self.status.get_sensor_status_text(gpio_controller), 10, y)),
            
            ("System Log", self.renderer._calculate_log_height(self.status.get_visible_messages()),
            lambda y: self.drawing.draw_log_messages(self.drawer, self.status.get_visible_messages(), 10, y, self.ui_width - 20))
        ]
        
        # Render each section with spacing
        for title, height, draw_func in sections:
            section_y, content_x = self._draw_boxed_section(title, current_y, height)
            current_y = draw_func(section_y) + self.drawing.SECTION_GAP  # Update y with section height and add spacing
        
        return current_y


    def _draw_camera_view(self) -> None:
        """Draw the camera view and detections"""
        self.image_display.draw_camera_view(
            self.drawer,
            self.current_image,
            self.current_predictions,
            self.ui_width + 10,
            10,
            self.image_width - 20,
            self.fb_height - 20,
            self.image  # Pass the target image
        )

    def _update_framebuffer(self) -> None:
        """Convert and write image to framebuffer"""
        fb_data = self.image_display.convert_to_fb_format(self.image)
        self.fb.update_display(fb_data)

    def cleanup(self) -> None:
        """Clean up resources"""
        if hasattr(self, 'fb'):
            self.fb.cleanup()
