# src/ui/components/camera.py
import logging
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from typing import Optional
from ..layout import Layout

logger = logging.getLogger(__name__)

class CameraComponent:
    """Handles rendering of the camera view"""
    
    def __init__(self, font: ImageFont.FreeTypeFont, layout: Layout):
        self.font = font
        self.layout = layout

    def draw(self, draw: ImageDraw.ImageDraw, image: Optional[Image.Image],
             x: int, y: int, width: int, height: int,
             timestamp: Optional[datetime] = None,
             inference_time: Optional[str] = None,
             confidence: Optional[float] = None):
        """Draw the camera view or placeholder"""
        # Draw border
        draw.rectangle(
            [x, y, x + width, y + height],
            outline=(255, 255, 255)
        )
        
        if image and image.mode:
            self._draw_camera_image(
                draw, image, x, y, width, height,
                timestamp, inference_time, confidence
            )
        else:
            self._draw_placeholder(draw, x, y, width, height)

    def _draw_camera_image(self, draw: ImageDraw.ImageDraw, image: Image.Image,
                          x: int, y: int, width: int, height: int,
                          timestamp: Optional[datetime],
                          inference_time: Optional[str],
                          confidence: Optional[float]):
        """Draw the camera image with overlay information"""
        try:
            # Create a copy for resizing
            img_copy = image.copy()
            img_copy.thumbnail(
                (width - 4, height - 4),
                Image.Resampling.LANCZOS
            )
            
            # Calculate centered position
            img_x = x + 2 + (width - 4 - img_copy.width) // 2
            img_y = y + 2 + (height - 4 - img_copy.height) // 2
            
            # Draw image
            draw.bitmap((img_x, img_y), img_copy)
            
            # Draw timestamp if available
            if timestamp:
                timestamp_str = f"Captured: {timestamp.strftime('%H:%M:%S')}"
                draw.text(
                    (x + 5, y + 5),
                    timestamp_str,
                    font=self.font,
                    fill=(255, 255, 0)
                )
            
            # Draw analysis results if available
            if inference_time and confidence is not None:
                confidence_str = (
                    f"Last Analysis: {inference_time}\n"
                    f"Confidence: {confidence:.1%}"
                )
                self._draw_wrapped_text(
                    draw,
                    confidence_str,
                    x + 5,
                    y + height - 40,
                    width - 10,
                    fill=(0, 255, 0)
                )
                
        except Exception as e:
            logger.error(f"Error drawing camera image: {e}")
            self._draw_placeholder(draw, x, y, width, height)

    def _draw_placeholder(self, draw: ImageDraw.ImageDraw,
                         x: int, y: int, width: int, height: int):
        """Draw placeholder when no camera image is available"""
        text = "No Camera Image"
        text_bbox = draw.textbbox((0, 0), text, font=self.font)
        text_width = text_bbox[2] - text_bbox[0]
        text_x = x + (width - text_width) // 2
        text_y = y + height // 2 - 10
        
        draw.text(
            (text_x, text_y),
            text,
            font=self.font,
            fill=(128, 128, 128)
        )