import io
import numpy as np
from datetime import datetime
from PIL import Image

class ImageProcessor:
    def update_image(self, image_data, ui):
        if image_data:
            try:
                print(f"Received image data of length: {len(image_data)}")
                
                image_buffer = io.BytesIO(image_data)
                temp_image = Image.open(image_buffer)
                
                print(f"Loaded image: size={temp_image.size}, mode={temp_image.mode}")
                
                if temp_image.mode != 'RGB':
                    temp_image = temp_image.convert('RGB')
                    print("Converted image to RGB mode")
                
                ui.current_image = temp_image.copy()
                ui.image_timestamp = datetime.now()
                
                print(f"Stored image: size={ui.current_image.size}, mode={ui.current_image.mode}")
                ui.update_status_message("Camera image updated")
                
            except Exception as e:
                print(f"Error loading image: {e}")
                import traceback
                traceback.print_exc()
                ui.current_image = None
                ui.image_timestamp = None
        else:
            ui.current_image = None
            ui.image_timestamp = None
            ui.update_status_message("Camera image cleared")

    def _rgb_to_rgb565(self, r, g, b):
        r = (r >> 3) & 0x1F
        g = (g >> 2) & 0x3F
        b = (b >> 3) & 0x1F
        return (r << 11) | (g << 5) | b

    def _update_framebuffer(self, ui):
        image_array = np.array(ui.image)
        height, width, _ = image_array.shape
        
        r = image_array[:, :, 0].astype(np.uint16)
        g = image_array[:, :, 1].astype(np.uint16)
        b = image_array[:, :, 2].astype(np.uint16)
        
        rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        
        fb_bytes = np.zeros((height, width, 2), dtype=np.uint8)
        fb_bytes[:, :, 0] = rgb565 & 0xFF
        fb_bytes[:, :, 1] = (rgb565 >> 8) & 0xFF
        
        ui.fb['fb'].seek(0)
        ui.fb['fb'].write(fb_bytes.tobytes())
