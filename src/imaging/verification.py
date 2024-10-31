# src/imaging/verification.py
from PIL import Image
import io
import logging

logger = logging.getLogger(__name__)

def verify_image(image_data: bytes) -> bool:
    """
    Verify image data integrity.
    
    Args:
        image_data: Raw image bytes
        
    Returns:
        bool: True if image is valid
    """
    try:
        # First verification pass
        with io.BytesIO(image_data) as bio:
            img = Image.open(bio)
            img.verify()
            
            # Second verification pass - try to fully load
            bio.seek(0)
            img = Image.open(bio)
            img.load()
            
            # Additional checks
            if img.size[0] < 10 or img.size[1] < 10:
                raise ValueError("Image dimensions too small")
            if len(image_data) < 100:
                raise ValueError("Image data suspiciously small")
                
        return True
        
    except Exception as e:
        logger.error(f"Image verification failed: {e}")
        return False