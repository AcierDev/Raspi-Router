# src/imaging/processor.py
import asyncio
from datetime import datetime
import hashlib
import logging
import time
from typing import Optional, Dict, Any
import aiohttp

from .analysis import ImageAnalysis
from .cache import ImageCache
from .verification import verify_image

logger = logging.getLogger(__name__)

class ImageProcessor:
    """Handles image processing, verification, and AI analysis"""

    def __init__(self, update_status_message, cache_size_mb: int = 100):
        """
        Initialize the image processor.
        
        Args:
            update_status_message: Callback function for status updates
            cache_size_mb: Maximum cache size in megabytes
        """
        self.update_status_message = update_status_message
        self.refresh_ui = None
        self._session: Optional[aiohttp.ClientSession] = None
        self.image_cache = ImageCache(max_size_mb=cache_size_mb)
        self.last_analysis: Optional[ImageAnalysis] = None

    async def __aenter__(self):
        """Async context manager entry"""
        timeout = aiohttp.ClientTimeout(total=30, connect=5)
        self._session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._session and not self._session.closed:
            await self._session.close()
            await asyncio.sleep(0.25)  # Allow time for cleanup

    @staticmethod
    def _calculate_image_hash(image_data: bytes) -> str:
        """Calculate a hash of image data for caching"""
        return hashlib.sha256(image_data).hexdigest()

    async def get_image(self, url: str) -> Optional[bytes]:
        """
        Asynchronously download and verify an image.
        
        Args:
            url: URL of the image to download
            
        Returns:
            Optional[bytes]: Image data if successful, None otherwise
        """
        cache_key = f"{url}:{datetime.now().strftime('%Y%m%d%H%M')}"
        
        # Check cache first
        cached_data = self.image_cache.get(cache_key)
        if cached_data:
            self.update_status_message("Using cached image")
            return cached_data
        
        try:
            if not self._session or self._session.closed:
                raise RuntimeError("HTTP session not initialized")

            async with self._session.get(url) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status}")
                
                content_length = int(response.headers.get('content-length', 0))
                chunks = []
                bytes_received = 0
                start_time = time.time()
                last_update = start_time
                
                async for chunk in response.content.iter_chunked(8192):
                    chunks.append(chunk)
                    bytes_received += len(chunk)
                    current_time = time.time()
                    
                    # Update progress every 0.5 seconds or on completion
                    if current_time - last_update >= 0.5 or bytes_received == content_length:
                        progress = (bytes_received / content_length * 100) if content_length else 0
                        speed = bytes_received / (current_time - start_time) / 1024  # KB/s
                        self.update_status_message(
                            f"Downloading: {progress:.1f}% ({bytes_received/1024:.1f} KB) - {speed:.1f} KB/s"
                        )
                        last_update = current_time
                
                image_data = b''.join(chunks)
                if verify_image(image_data):
                    self.image_cache.put(cache_key, image_data)
                    return image_data
                return None
                
        except asyncio.TimeoutError:
            self.update_status_message("Image download timed out")
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            self.update_status_message(f"Image download error: {str(e)}")
        return None

    async def send_for_analysis(self, url: str, image_data: bytes) -> Optional[ImageAnalysis]:
        """
        Send an image for AI analysis.
        
        Args:
            url: AI service URL
            image_data: Image data to analyze
            
        Returns:
            Optional[ImageAnalysis]: Analysis results if successful
        """
        if not image_data:
            self.update_status_message("No image data to analyze")
            return None
            
        try:
            if not self._session or self._session.closed:
                raise RuntimeError("HTTP session not initialized")

            start_time = time.time()
            self.update_status_message("Preparing image for analysis...")
            
            # Verify image again before sending
            if not verify_image(image_data):
                raise ValueError("Image validation failed before analysis")
            
            form = aiohttp.FormData()
            form.add_field('image', image_data, 
                        filename='image.jpg',
                        content_type='image/jpeg')
            
            self.update_status_message("Sending image to AI server...")
            
            async with self._session.post(url, data=form) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status}")
                    
                result = await response.json()
                
                processing_time = time.time() - start_time
                self.update_status_message(f"Analysis completed in {processing_time:.2f}s")
                
                predictions = result.get('predictions', [])
                if not predictions:
                    return None
                
                # Get the best prediction
                valid_predictions = [
                    pred for pred in predictions 
                    if pred.get('confidence', 0) > 0.5
                ]
                
                if not valid_predictions:
                    return None
                
                best_prediction = max(valid_predictions, 
                                key=lambda x: x.get('confidence', 0))
                
                analysis = ImageAnalysis(
                    confidence=best_prediction['confidence'],
                    class_name=best_prediction['class_name'],
                    timestamp=datetime.now(),
                    processing_time=processing_time,
                    additional_predictions=valid_predictions[1:],
                    metadata={
                        'total_predictions': len(predictions),
                        'valid_predictions': len(valid_predictions),
                        'server_response_time': processing_time,
                        'model_name': result.get('metadata', {}).get('model_name')
                    }
                )
                
                self.last_analysis = analysis
                return analysis
                
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            self.update_status_message(f"Analysis error: {str(e)}")
            return None