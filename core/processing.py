# core/processing.py

import requests
from config import (
    IMAGE_URL, 
    INFERENCE_URL, 
    NETWORK_TIMEOUTS, 
    DOWNLOAD_CHUNK_SIZE
)

class ImageProcessor:
    def __init__(self, status_callback=None):
        self.status_callback = status_callback
        self.refresh_ui = None

    def update_status(self, message, is_network=False):
        """Update status with callback if available"""
        if self.status_callback:
            self.status_callback(message, is_network=is_network)
        if self.refresh_ui:
            self.refresh_ui()

    def get_image(self):
        """Capture image from camera"""
        self.update_status("Initiating image capture", is_network=True)
        
        try:
            self.update_status("Opening connection to camera...", is_network=True)
            
            response = requests.get(
                IMAGE_URL,
                timeout=(NETWORK_TIMEOUTS['connect'], NETWORK_TIMEOUTS['read']),
                stream=True
            )
            
            self.update_status("Connected to camera, starting image transfer...", is_network=True)
            
            # Get content length if available
            total_size = int(response.headers.get('content-length', 0))
            if total_size:
                self.update_status(f"Image size: {total_size/1024:.1f} KB", is_network=True)
            
            # Stream the response content
            chunks = []
            bytes_received = 0
            last_progress_update = 0
            
            for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                if chunk:
                    chunks.append(chunk)
                    bytes_received += len(chunk)
                    
                    if total_size > 100000:  # Only for images > 100KB
                        progress = (bytes_received / total_size) * 100
                        if progress - last_progress_update >= 5:  # Update every 5% progress
                            self.update_status(
                                f"Downloading: {progress:.1f}% ({bytes_received/1024:.1f} KB / {total_size/1024:.1f} KB)",
                                is_network=True
                            )
                            last_progress_update = progress
            
            self.update_status("Image download complete", is_network=True)
            return b''.join(chunks)
            
        except Exception as e:
            self.update_status(f"Error during image capture: {str(e)}", is_network=True)
            return None

    def analyze_image(self, image_data):
        """Send image to AI server for analysis"""
        if not image_data:
            self.update_status("No image data to analyze", is_network=True)
            return None

        try:
            self.update_status("Sending image for analysis...", is_network=True)
            
            files = {'image': ('image.jpg', image_data, 'image/jpeg')}
            response = requests.post(
                INFERENCE_URL, 
                files=files,
                timeout=(NETWORK_TIMEOUTS['connect'], NETWORK_TIMEOUTS['read'])
            )
            
            if response.status_code == 200:
                result = response.json()
                predictions = result.get('predictions', [])
                
                if predictions:
                    high_confidence_preds = [
                        pred for pred in predictions 
                        if pred['confidence'] > 0.5
                    ]
                    
                    if high_confidence_preds:
                        best_prediction = max(high_confidence_preds, 
                                           key=lambda x: x['confidence'])
                        self.update_status(
                            f"Detection: {best_prediction['class']} "
                            f"({best_prediction['confidence']:.2%})"
                        )
                        return best_prediction['confidence']
                
                self.update_status("No high-confidence predictions found")
                return None
                
        except Exception as e:
            self.update_status(f"Analysis failed: {str(e)}", is_network=True)
            return None

    def process_piece(self):
        """Complete piece processing pipeline"""
        # Get image
        image_data = self.get_image()
        if not image_data:
            return False, None
        
        # Analyze image
        confidence = self.analyze_image(image_data)
        return True, confidence