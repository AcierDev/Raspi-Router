from PIL import Image, ImageDraw
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import numpy as np
import io

class ImageDisplayManager:
    """Manages image display and detection overlay rendering"""
    
    def __init__(self, drawing_utils):
        self.drawing = drawing_utils
        self.current_image = None
        self.image_timestamp = None
        
        # Standard colors for different defect types
        self.defect_colors = {
            'knot': (255, 99, 71),     # Tomato red
            'edge': (65, 105, 225),    # Royal blue
            'corner': (50, 205, 50),   # Lime green
            'damage': (255, 0, 0),     # Red
            'side': (147, 112, 219),   # Medium purple
            'default': (255, 165, 0)   # Orange (for unknown types)
        }

    def draw_camera_view(self, drawer: ImageDraw, image: bytes,
                        predictions: Dict[str, Any], x: int, y: int,
                        width: int, height: int, target_image: Image.Image) -> None:
        """Draw the camera image with detection overlays"""
        # Draw border
        drawer.rectangle([x, y, x + width, y + height], outline=(255, 255, 255))
        
        if not image:
            self._draw_placeholder(drawer, x, y, width, height)
            return
            
        try:
            # Convert bytes to PIL Image if needed
            if isinstance(image, bytes):
                image_buffer = io.BytesIO(image)
                pil_image = Image.open(image_buffer)
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')
            else:
                pil_image = image
            
            # Create a copy for resizing
            img_copy = pil_image.copy()
            img_copy.thumbnail((width - 4, height - 4))
            
            # Calculate position to center the image
            img_x = x + 2 + (width - 4 - img_copy.width) // 2
            img_y = y + 2 + (height - 4 - img_copy.height) // 2
            
            # Paste the image onto the target image
            target_image.paste(img_copy, (img_x, img_y))
            
            # Draw detections if available
            if predictions and 'predictions' in predictions:
                self._draw_detections(drawer, predictions['predictions'],
                                   img_x, img_y, img_copy.width, img_copy.height,
                                   pil_image.width, pil_image.height)
            
            # Draw timestamp
            if self.image_timestamp:
                timestamp_str = f"Captured: {self.image_timestamp.strftime('%H:%M:%S')}"
                drawer.text((x + 5, y + 5), timestamp_str,
                          font=self.drawing.font, fill=(255, 255, 0))
                
        except Exception as e:
            print(f"Error drawing camera view: {e}")
            import traceback
            traceback.print_exc()
            self._draw_placeholder(drawer, x, y, width, height)

    def _draw_detections(self, drawer: ImageDraw, predictions: list,
                    img_x: int, img_y: int, display_width: int,
                    display_height: int, source_width: int,
                    source_height: int) -> None:
        """Draw detection boxes and labels on the image"""
        
        for pred in predictions:
            try:
                # Get normalized bounding box and convert to pixel coordinates
                bbox = pred['bbox']
                x1 = bbox[0] * source_width
                y1 = bbox[1] * source_height
                x2 = bbox[2] * source_width
                y2 = bbox[3] * source_height
                
                # Adjust for image display position and scale if necessary
                x1_display = img_x + (x1 * (display_width / source_width))
                y1_display = img_y + (y1 * (display_height / source_height))
                x2_display = img_x + (x2 * (display_width / source_width))
                y2_display = img_y + (y2 * (display_height / source_height))

                # Draw bounding box
                color = self.defect_colors.get(pred['class_name'], self.defect_colors['default'])
                drawer.rectangle([x1_display, y1_display, x2_display, y2_display], outline=color, width=2)
                
                # Add label above the bounding box
                label = f"{pred['class_name']}: {pred['confidence']:.2f}"
                label_y = max(y1_display - 5, img_y)  # Prevent label from going above image
                drawer.text(
                    (x1_display, label_y), label,
                    fill="white", font=self.drawing.small_font,
                    bbox=dict(facecolor='black', alpha=0.8, pad=2, edgecolor='none')
                )
                
            except Exception as e:
                print(f"Error drawing detection: {e}")
                continue


    def _draw_detection_label(self, drawer: ImageDraw, pred: Dict[str, Any],
                            x1: float, y1: float, img_y: float,
                            color: Tuple[int, int, int]) -> None:
        """Draw detection label with background"""
        label = f"{pred['class_name']} {pred['confidence']:.1%}"
        text_bb = drawer.textbbox((0, 0), label, font=self.drawing.small_font)
        text_width = text_bb[2] - text_bb[0]
        text_height = text_bb[3] - text_bb[1]
        
        # Position label above box if possible
        label_x = x1
        label_y = y1 - text_height - 4
        if label_y < img_y:  # If label would go above image, put it inside box
            label_y = y1 + 2
        
        # Draw label background
        drawer.rectangle(
            [label_x, label_y,
             label_x + text_width + 4,
             label_y + text_height + 2],
            fill=color
        )
        
        # Draw label text
        drawer.text(
            (label_x + 2, label_y + 1),
            label,
            font=self.drawing.small_font,
            fill=(0, 0, 0)
        )

    def _draw_placeholder(self, drawer: ImageDraw, x: int, y: int,
                         width: int, height: int) -> None:
        """Draw placeholder when no image is available"""
        text = "No Camera Image"
        text_bbox = drawer.textbbox((0, 0), text, font=self.drawing.font)
        text_width = text_bbox[2] - text_bbox[0]
        text_x = x + (width - text_width) // 2
        text_y = y + height // 2 - 10
        drawer.text((text_x, text_y), text,
                   font=self.drawing.font, fill=(128, 128, 128))
    
    def convert_to_fb_format(self, image: Image.Image) -> bytes:
        """Convert PIL image to framebuffer format"""
        try:
            # Convert PIL image to numpy array
            image_array = np.array(image)
            height, width, _ = image_array.shape
            
            # Create numpy arrays for RGB components
            r = image_array[:, :, 0].astype(np.uint16)
            g = image_array[:, :, 1].astype(np.uint16)
            b = image_array[:, :, 2].astype(np.uint16)
            
            # Convert to RGB565 format
            rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
            
            # Convert to bytes in correct order (little-endian)
            fb_bytes = np.zeros((height, width, 2), dtype=np.uint8)
            fb_bytes[:, :, 0] = rgb565 & 0xFF  # Low byte
            fb_bytes[:, :, 1] = (rgb565 >> 8) & 0xFF  # High byte
            
            return fb_bytes.tobytes()
            
        except Exception as e:
            print(f"Error converting image to framebuffer format: {e}")
            import traceback
            traceback.print_exc()
            # Return black screen in case of error
            fb_bytes = np.zeros((height, width, 2), dtype=np.uint8)
            return fb_bytes.tobytes()