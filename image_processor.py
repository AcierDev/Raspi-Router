import requests
from datetime import datetime
import time
from requests.exceptions import RequestException, Timeout, ConnectionError

class ImageProcessor:
    def __init__(self, update_status_message):
        self.update_status_message = update_status_message
        self.refresh_ui = None  # Will be set by main process

    def get_image(self, url):
        self.update_status_message("Sensor 2 triggered - initiating image capture", is_network=True)
        if self.refresh_ui: self.refresh_ui()
        
        try:
            self.update_status_message("Opening connection to camera...", is_network=True)
            if self.refresh_ui: self.refresh_ui()
            
            # Use separate timeouts for connection and read
            response = requests.get(
                url,
                timeout=(5, 30),  # (connect_timeout, read_timeout)
                stream=True
            )
            
            self.update_status_message("Connected to camera, starting image transfer...", is_network=True)
            if self.refresh_ui: self.refresh_ui()
            
            # Get content length if available
            total_size = int(response.headers.get('content-length', 0))
            if total_size:
                self.update_status_message(f"Image size: {total_size/1024:.1f} KB", is_network=True)
                if self.refresh_ui: self.refresh_ui()
            
            # Stream the response content
            start_time = time.time()
            chunks = []
            bytes_received = 0
            last_progress_update = 0
            
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    chunks.append(chunk)
                    bytes_received += len(chunk)
                    
                    # Log progress for large images, but only if 5% or more progress made
                    if total_size > 100000:  # Only for images > 100KB
                        progress = (bytes_received / total_size) * 100
                        if progress - last_progress_update >= 5:  # Update every 5% progress
                            self.update_status_message(
                                f"Downloading: {progress:.1f}% ({bytes_received/1024:.1f} KB / {total_size/1024:.1f} KB)",
                                is_network=True
                            )
                            if self.refresh_ui: self.refresh_ui()
                            last_progress_update = progress
            
            duration = time.time() - start_time
            transfer_speed = (bytes_received / 1024) / duration  # KB/s
            
            self.update_status_message(
                f"Image download complete: {bytes_received/1024:.1f} KB in {duration:.1f}s ({transfer_speed:.1f} KB/s)",
                is_network=True
            )
            if self.refresh_ui: self.refresh_ui()
            
            return b''.join(chunks)
            
        except Timeout as e:
            self.update_status_message(f"Timeout during image capture: {str(e)}", is_network=True)
            if self.refresh_ui: self.refresh_ui()
            return None
        except ConnectionError as e:
            self.update_status_message(f"Connection error during image capture: {str(e)}", is_network=True)
            if self.refresh_ui: self.refresh_ui()
            return None
        except Exception as e:
            self.update_status_message(f"Error during image capture: {str(e)}", is_network=True)
            if self.refresh_ui: self.refresh_ui()
            return None

    def send_for_analysis(self, url, image_data):
        if not image_data:
            self.update_status_message("No image data to analyze", is_network=True)
            if self.refresh_ui: self.refresh_ui()
            return None

        self.update_status_message("Preparing to send image for analysis...", is_network=True)
        if self.refresh_ui: self.refresh_ui()
        
        try:
            self.update_status_message("Connecting to AI server...", is_network=True)
            if self.refresh_ui: self.refresh_ui()
            
            files = {'image': ('image.jpg', image_data, 'image/jpeg')}
            
            start_time = time.time()
            self.update_status_message("Uploading image to AI server...", is_network=True)
            if self.refresh_ui: self.refresh_ui()
            
            response = requests.post(url, files=files, timeout=(5, 30))
            
            upload_duration = time.time() - start_time
            self.update_status_message(
                f"Upload complete in {upload_duration:.1f}s, waiting for analysis...",
                is_network=True
            )
            if self.refresh_ui: self.refresh_ui()
            
            if response.status_code == 200:
                result = response.json()
                predictions = result.get('predictions', [])
                
                total_duration = time.time() - start_time
                self.update_status_message(
                    f"Analysis completed in {total_duration:.1f}s",
                    is_network=True
                )
                if self.refresh_ui: self.refresh_ui()
                
                if predictions:
                    high_confidence_preds = [
                        pred for pred in predictions 
                        if pred['confidence'] > 0.5
                    ]
                    
                    if high_confidence_preds:
                        for pred in high_confidence_preds:
                            self.update_status_message(
                                f"Detection: {pred.get('class', 'unknown')} "
                                f"({pred['confidence']:.2%})",
                                is_network=False
                            )
                            if self.refresh_ui: self.refresh_ui()
                        return max(pred['confidence'] for pred in high_confidence_preds)
                    else:
                        self.update_status_message("No high-confidence predictions found", is_network=True)
                        if self.refresh_ui: self.refresh_ui()
                else:
                    self.update_status_message("No predictions returned from AI server", is_network=True)
                    if self.refresh_ui: self.refresh_ui()
                return None
                
        except Timeout:
            self.update_status_message("Analysis request timed out", is_network=True)
            if self.refresh_ui: self.refresh_ui()
            return None
        except RequestException as e:
            self.update_status_message(f"Analysis request failed: {str(e)}", is_network=True)
            if self.refresh_ui: self.refresh_ui()
            return None