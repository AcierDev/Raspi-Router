import requests
from typing import Optional, Dict, List, Any, Tuple
import logging
from datetime import datetime
import json
from io import BytesIO
import tempfile
import os
from config import INFERENCE_URL, NETWORK_TIMEOUTS

class ImageProcessor:
    def __init__(self, status_callback=None):
        self.status_callback = status_callback
        self.logger = logging.getLogger(__name__)
        self.last_predictions = None
        self.image_size = (3024, 3024)
        
        # Create a temporary directory for image processing
        self.temp_dir = tempfile.mkdtemp()
        
        # Confidence thresholds
        self.CONFIDENCE_THRESHOLDS = {
            'high': 0.85,
            'medium': 0.65,
            'low': 0.50
        }

    def get_image(self, image_url: str) -> Optional[bytes]:
        """Capture image from camera"""
        self.update_status("Initiating image capture", is_network=True)
        
        try:
            self.update_status("Opening connection to camera...", is_network=True)
            
            response = requests.get(
                image_url, 
                timeout=NETWORK_TIMEOUTS['connect']
            )
            response.raise_for_status()
            
            self.update_status("Connected to camera, starting image transfer...", is_network=True)
            
            # Verify content type is an image
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                raise ValueError(f"Invalid content type: {content_type}")
                
            image_data = response.content
            
            # Verify we got actual image data
            if len(image_data) < 100:  # Basic sanity check
                raise ValueError(f"Suspiciously small image data: {len(image_data)} bytes")
                
            self.update_status(f"Image download complete: {len(image_data)/1024:.1f} KB", is_network=True)
            return image_data
            
        except Exception as e:
            self.logger.error(f"Error during image capture: {str(e)}", exc_info=True)
            self.update_status(f"Error during image capture: {str(e)}", is_network=True)
            return None

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
        """Convert normalized coordinates to pixel coordinates and ensure alignment."""
        width, height = self.image_size
        x_min, y_min, x_max, y_max = bbox  # Normalize bbox [x_min, y_min, x_max, y_max]
        
        # Convert to pixel-based coordinates, ensuring proper alignment with origin
        pixel_bbox = {
            'x': round(x_min * width),  # Top-left x in pixels
            'y': round(y_min * height),  # Top-left y in pixels
            'width': round((x_max - x_min) * width),  # Width in pixels
            'height': round((y_max - y_min) * height)  # Height in pixels
        }
        
        # Debug log for verification
        print(f"Normalized bbox: {bbox} -> Pixel bbox: {pixel_bbox}")
        return pixel_bbox


    def _process_predictions(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Process and validate prediction results with new response format"""
        try:
            # Extract data from nested structure
            data = result.get('data', {})
            predictions = data.get('predictions', [])
            file_info = data.get('file_info', {})
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
                    
                    # Calculate original pixel coordinates
                    original_coords = self._normalize_to_pixels(bbox)
                    
                    # Determine confidence level
                    confidence_level = self._get_confidence_level(confidence)
                    
                    processed_pred = {
                        'class_name': pred.get('class_name', 'unknown'),
                        'confidence': confidence,
                        'confidence_level': confidence_level,
                        'bbox': bbox,
                        'detection_id': pred.get('detection_id', 'unknown'),
                        'metadata': {
                            'area': self._calculate_bbox_area(bbox),
                            'center': self._calculate_bbox_center(bbox),
                            'severity': self._estimate_severity(confidence, bbox),
                            'original_coords': original_coords  # Add original coordinates
                        }
                    }
                    processed_preds.append(processed_pred)
                    
                except Exception as e:
                    print(f"Error processing prediction: {e}")
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
            print(f"Error in _process_predictions: {e}")
            import traceback
            traceback.print_exc()
            return None

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

    def _calculate_bbox_center(self, bbox: List[float]) -> Tuple[float, float]:
        """Calculate center point of bounding box"""
        if not bbox or len(bbox) != 4:
            return (0.0, 0.0)
        center_x = (bbox[0] + bbox[2]) / 2
        center_y = (bbox[1] + bbox[3]) / 2
        return (center_x, center_y)

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

    def get_last_predictions(self) -> Optional[Dict[str, Any]]:
        """Get the most recent prediction results"""
        return self.last_predictions