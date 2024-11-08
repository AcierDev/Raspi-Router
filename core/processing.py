import requests
from typing import Optional, Dict, List, Any, Tuple
import logging
from datetime import datetime
import json
from io import BytesIO
import tempfile
import os
import subprocess
from config import INFERENCE_URL, NETWORK_TIMEOUTS
import time

class ImageProcessor:
    def __init__(self, status_callback=None):
        self.status_callback = status_callback
        self.refresh_ui = None
        self.logger = logging.getLogger(__name__)
        self.last_predictions = None
        self.image_size = (3024, 3024)  # Default size, will be updated when processing
        self.temp_dir = tempfile.mkdtemp()
        
        # ADB configuration
        # Updated to use internal storage path instead of SD card
        self.device_path = "/storage/emulated/0/DCIM/Camera"  # Internal storage path
        self.local_path = self.temp_dir
        
        # Confidence thresholds
        self.CONFIDENCE_THRESHOLDS = {
            'high': 0.85,
            'medium': 0.65,
            'low': 0.50
        }

    def _capture_via_adb(self) -> Optional[bytes]:
        """Attempt to capture image using ADB"""
        try:
            self.update_status("Initiating ADB image capture...")
            
            # Generate unique filename with known pattern
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"capture_{timestamp}.jpg"
            remote_file = f"{self.device_path}/{filename}"
            local_file = os.path.join(self.local_path, filename)
            
            # Simplified capture sequence
            self.update_status("Capturing image via ADB...")
            
            capture_commands = (
                f"am force-stop com.android.camera && "
                f"am start -a android.media.action.STILL_IMAGE_CAMERA --ez android.intent.extra.QUICK_CAPTURE true && "
                f"sleep 1.5 && "
                f"input keyevent 24 && "  # KEYCODE_VOLUME_UP
                f"sleep 1 && "
                f"am force-stop com.android.camera"
            )
            
            subprocess.run(["adb", "shell", capture_commands], 
                        capture_output=True, check=True)
            
            # Simple ls command to list files
            list_cmd = f"ls -t {self.device_path}/*.jpg | head -1"
            result = subprocess.run(["adb", "shell", list_cmd],
                                capture_output=True, text=True, check=True)
            
            latest_file = result.stdout.strip()
            if not latest_file:
                raise Exception("No jpg files found in camera directory")
            
            # Pull the file
            self.update_status("Transferring image from device...")
            pull_cmd = ["adb", "pull", latest_file, local_file]
            subprocess.run(pull_cmd, capture_output=True, text=True, check=True)
            
            # Read file
            with open(local_file, 'rb') as f:
                image_data = f.read()
            
            # Clean up
            os.remove(local_file)
            
            if len(image_data) < 100:
                raise ValueError(f"Suspiciously small image data: {len(image_data)} bytes")
            
            self.update_status(f"ADB capture complete: {len(image_data)/1024:.1f} KB")
            return image_data
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            self.logger.error(f"ADB command failed: {error_msg}", exc_info=True)
            self.update_status(f"ADB capture failed: {error_msg}")
            return None
        except Exception as e:
            self.logger.error(f"ADB capture failed: {str(e)}", exc_info=True)
            self.update_status(f"ADB capture failed: {str(e)}")
            return None

    def _capture_via_network(self, image_url: str) -> Optional[bytes]:
        """Fallback method to capture image via network request"""
        try:
            self.update_status("Attempting network image capture...", is_network=True)
            
            response = requests.get(
                image_url, 
                timeout=NETWORK_TIMEOUTS['connect']
            )
            response.raise_for_status()
            
            # Verify content type
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                raise ValueError(f"Invalid content type: {content_type}")
            
            image_data = response.content
            
            # Verify image data
            if len(image_data) < 100:
                raise ValueError(f"Suspiciously small image data: {len(image_data)} bytes")
            
            self.update_status(f"Network image capture complete: {len(image_data)/1024:.1f} KB", is_network=True)
            return image_data
            
        except Exception as e:
            self.logger.error(f"Network capture failed: {str(e)}", exc_info=True)
            self.update_status(f"Network capture failed: {str(e)}", is_network=True)
            return None

    def get_image(self, image_url: str) -> Optional[bytes]:
        """Capture image, trying ADB first then falling back to network request"""
        self.update_status("Starting image capture process...")
        
        # First attempt: ADB capture
        image_data = self._capture_via_adb()
        if image_data:
            return image_data
            
        # Fallback: Network capture
        self.update_status("ADB capture failed, falling back to network capture...")
        return self._capture_via_network(image_url)

    def analyze_image(self, image_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Send image to inference endpoint for analysis
        """
        if not image_data:
            self.update_status("No image data to analyze", is_network=True)
            return None

        try:
            self.update_status("Sending image for analysis...", is_network=True)
            
            # Prepare the image file for upload
            files = {
                'image': ('image.jpg', image_data, 'image/jpeg')
            }
            
            # Send POST request to inference endpoint
            response = requests.post(
                INFERENCE_URL,
                files=files,
                timeout=NETWORK_TIMEOUTS['read']
            )
            response.raise_for_status()
            
            # Parse the response
            result = response.json()
            
            # Print raw response for debugging
            print("\nRaw Inference Response:")
            print(json.dumps(result, indent=2))
            
            # Check if response indicates success
            if not result.get('success', False):
                raise Exception("Inference request was not successful")
            
            # Process the predictions
            processed_results = self._process_predictions(result)
            
            self.last_predictions = processed_results
            
            # Debug prints
            print(f"Updating predictions: {bool(processed_results)}")
            if processed_results:
                print(f"Number of predictions: {len(processed_results.get('predictions', []))}")
                print(f"First prediction: {processed_results.get('predictions', [])[0] if processed_results.get('predictions') else None}")
            
            return processed_results
                
        except Exception as e:
            self.logger.error(f"Analysis failed: {str(e)}", exc_info=True)
            self.update_status(f"Analysis failed: {str(e)}", is_network=True)
            return None

    def _normalize_to_pixels(self, bbox: List[float]) -> Dict[str, int]:
        """Convert normalized coordinates to pixel coordinates"""
        width, height = self.image_size
        
        # Calculate the actual coordinates and dimensions
        x1 = int(bbox[0] * width)
        y1 = int(bbox[1] * height)
        x2 = int(bbox[2] * width)
        y2 = int(bbox[3] * height)
        
        return {
            'x': x1,  # Left coordinate
            'y': y1,  # Top coordinate
            'width': x2 - x1,  # Width is the difference between right and left
            'height': y2 - y1   # Height is the difference between bottom and top
        }

    def _process_predictions(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Process and validate prediction results with new response format"""
        try:
            # Extract image dimensions from file info if available
            data = result.get('data', {})
            file_info = data.get('file_info', {})
            if 'width' in file_info and 'height' in file_info:
                self.image_size = (file_info['width'], file_info['height'])
            
            predictions = data.get('predictions', [])
            timestamp = result.get('timestamp')
            
            if not predictions:
                return {
                    'predictions': [],
                    'metadata': {
                        'timestamp': timestamp,
                        'file_info': file_info
                    },
                    'summary': self._summarize_predictions([])
                }
            
            # Process each prediction
            processed_preds = []
            for pred in predictions:
                try:
                    confidence = pred.get('confidence', 0)
                    
                    # Skip low confidence predictions
                    if confidence < self.CONFIDENCE_THRESHOLDS['low']:
                        continue
                    
                    # Get bbox coordinates (already in normalized format)
                    bbox = pred.get('bbox', [0, 0, 0, 0])
                    
                    # Calculate pixel coordinates
                    pixel_coords = self._normalize_to_pixels(bbox)
                    
                    # Determine confidence level
                    confidence_level = self._get_confidence_level(confidence)
                    
                    processed_pred = {
                        'class_name': pred.get('class_name', 'unknown'),
                        'confidence': confidence,
                        'confidence_level': confidence_level,
                        'bbox': bbox,  # Original normalized coordinates
                        'detection_id': pred.get('detection_id', 'unknown'),
                        'metadata': {
                            'area': self._calculate_bbox_area(bbox),
                            'center': self._calculate_bbox_center(bbox),
                            'severity': self._estimate_severity(confidence, bbox),
                            'original_coords': pixel_coords  # Keep original_coords for compatibility
                        }
                    }
                    processed_preds.append(processed_pred)
                    
                    # Debug logging
                    self.logger.debug(f"Processed prediction: class={processed_pred['class_name']}, "
                                    f"bbox={bbox}, pixel_coords={pixel_coords}")
                    
                except Exception as e:
                    self.logger.error(f"Error processing prediction: {e}")
                    continue
            
            # Sort predictions by confidence
            processed_preds.sort(key=lambda x: x['confidence'], reverse=True)
            
            # Create final processed results
            processed_results = {
                'predictions': processed_preds,
                'metadata': {
                    'file_info': file_info,
                    'timestamp': timestamp,
                    'stored_locations': file_info.get('stored_locations', {}),
                    'image_size': self.image_size
                },
                'summary': self._summarize_predictions(processed_preds)
            }
            
            return processed_results
            
        except Exception as e:
            self.logger.error(f"Error in _process_predictions: {e}")
            return None

    def _calculate_bbox_center(self, bbox: List[float]) -> Tuple[float, float]:
        """Calculate center point of bounding box in normalized coordinates"""
        if not bbox or len(bbox) != 4:
            return (0.0, 0.0)
        center_x = (bbox[0] + bbox[2]) / 2
        center_y = (bbox[1] + bbox[3]) / 2
        return (center_x, center_y)

    def _get_confidence_level(self, confidence: float) -> str:
        """Determine confidence level category"""
        if confidence >= self.CONFIDENCE_THRESHOLDS['high']:
            return 'high'
        elif confidence >= self.CONFIDENCE_THRESHOLDS['medium']:
            return 'medium'
        return 'low'

    def _calculate_bbox_area(self, bbox: List[float]) -> float:
        """Calculate normalized area of bounding box"""
        if not bbox or len(bbox) != 4:
            return 0.0
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        return width * height

    def _estimate_severity(self, confidence: float, bbox: List[float]) -> str:
        """Estimate defect severity based on confidence and size"""
        area = self._calculate_bbox_area(bbox)
        
        if confidence >= self.CONFIDENCE_THRESHOLDS['high']:
            if area > 0.1:
                return 'critical'
            elif area > 0.05:
                return 'major'
            return 'minor'
        elif confidence >= self.CONFIDENCE_THRESHOLDS['medium']:
            if area > 0.1:
                return 'major'
            return 'minor'
        return 'negligible'

    def _summarize_predictions(self, predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create comprehensive summary of predictions"""
        if not predictions:
            return {
                'count': 0,
                'class_counts': {},
                'severity_counts': {},
                'average_confidence': 0.0,
                'total_area': 0.0
            }
            
        class_counts = {}
        severity_counts = {}
        total_area = 0.0
        
        for pred in predictions:
            class_name = pred.get('class_name', 'unknown')
            class_counts[class_name] = class_counts.get(class_name, 0) + 1
            
            severity = pred.get('metadata', {}).get('severity', 'unknown')
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            total_area += pred['metadata']['area']
            
        return {
            'count': len(predictions),
            'class_counts': class_counts,
            'severity_counts': severity_counts,
            'best_prediction': predictions[0] if predictions else None,
            'average_confidence': sum(p['confidence'] for p in predictions) / len(predictions),
            'total_area': total_area,
            'timestamp': datetime.now().isoformat()
        }

    def update_status(self, message: str, is_network: bool = False) -> None:
        """Update status with callback if available"""
        self.logger.info(message)
        if self.status_callback:
            self.status_callback(message, is_network=is_network)
        if self.refresh_ui:
            self.refresh_ui()

    def get_last_predictions(self) -> Optional[Dict[str, Any]]:
        """Get the most recent prediction results"""
        return self.last_predictions