import requests
from inference_sdk import InferenceHTTPClient
from typing import Optional, Dict, List, Any, Tuple
import logging
from datetime import datetime
import json
from io import BytesIO
import tempfile
import os

class ImageProcessor:
    def __init__(self, api_key: str, model_id: str, status_callback=None):
        self.status_callback = status_callback
        self.refresh_ui = None
        self.logger = logging.getLogger(__name__)
        self.last_predictions = None
        
        # Initialize Roboflow client
        self.client = InferenceHTTPClient(
            api_url="https://detect.roboflow.com",
            api_key=api_key
        )
        self.model_id = model_id
        
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
            
            response = requests.get(image_url, timeout=5)  # Add timeout
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
        Send image to Roboflow for analysis and process results
        """
        if not image_data:
            self.update_status("No image data to analyze", is_network=True)
            return None

        temp_path = None
        try:
            self.update_status("Sending image to Roboflow for analysis...", is_network=True)
            
            # Save image data to temporary file
            temp_path = os.path.join(self.temp_dir, f"temp_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
            with open(temp_path, 'wb') as f:
                f.write(image_data)
            
            # Call Roboflow inference with file path
            result = self.client.infer(
                temp_path,
                model_id=self.model_id
            )
            
            # Print raw response for debugging
            print("\nRaw Roboflow Response:")
            print(json.dumps(result, indent=2))
            
            # Process the predictions
            processed_results = self._process_predictions({
                'predictions': result.get('predictions', []),
                'metadata': {
                    'model_version': result.get('model_version', 'unknown'),
                    'processing_time': result.get('inference_time', 0)
                }
            })
            
            self.last_predictions = processed_results
            return processed_results
                
        except Exception as e:
            self.logger.error(f"Analysis failed: {str(e)}", exc_info=True)
            self.update_status(f"Analysis failed: {str(e)}", is_network=True)
            return None
        finally:
            # Clean up temporary file
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e:
                    self.logger.error(f"Error cleaning up temporary file: {str(e)}")

    def _process_predictions(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Process and validate Roboflow prediction results"""
        try:
            predictions = result.get('predictions', [])
            image_info = result.get('image', {})
            
            if not predictions:
                return {
                    'predictions': [],
                    'metadata': {
                        'image_size': image_info,
                        'timestamp': datetime.now().isoformat()
                    },
                    'summary': self._summarize_predictions([])
                }
            
            # Process each prediction
            processed_preds = []
            for i, pred in enumerate(predictions):
                try:
                    # Get confidence (already in decimal form in new response)
                    confidence = pred.get('confidence', 0)
                    
                    # Skip low confidence predictions
                    if confidence < self.CONFIDENCE_THRESHOLDS['low']:
                        continue
                    
                    # Get original pixel coordinates
                    x = pred.get('x', 0)
                    y = pred.get('y', 0)
                    width = pred.get('width', 0)
                    height = pred.get('height', 0)
                    
                    # Calculate normalized coordinates [0,1]
                    img_width = image_info.get('width', 1)
                    img_height = image_info.get('height', 1)
                    
                    # Store original coordinates for UI scaling
                    original_coords = {
                        'x': x,
                        'y': y,
                        'width': width,
                        'height': height
                    }
                    
                    # Calculate normalized coordinates
                    x_norm = x / img_width
                    y_norm = y / img_height
                    w_norm = width / img_width
                    h_norm = height / img_height
                    
                    bbox = [
                        max(0, min(1, x_norm - w_norm/2)),  # x1
                        max(0, min(1, y_norm - h_norm/2)),  # y1
                        max(0, min(1, x_norm + w_norm/2)),  # x2
                        max(0, min(1, y_norm + h_norm/2))   # y2
                    ]
                    
                    # Determine confidence level
                    confidence_level = self._get_confidence_level(confidence)
                    
                    processed_pred = {
                        'class_name': pred.get('class', 'unknown'),
                        'confidence': confidence,
                        'confidence_level': confidence_level,
                        'bbox': bbox,
                        'detection_id': pred.get('detection_id', f'det_{i}'),
                        'metadata': {
                            'area': self._calculate_bbox_area(bbox),
                            'center': self._calculate_bbox_center(bbox),
                            'severity': self._estimate_severity(confidence, bbox),
                            'original_coords': original_coords
                        }
                    }
                    processed_preds.append(processed_pred)
                    
                except Exception as e:
                    print(f"Error processing prediction {i}: {e}")
                    continue
            
            # Sort predictions by confidence
            processed_preds.sort(key=lambda x: x['confidence'], reverse=True)
            
            processed_results = {
                'predictions': processed_preds,
                'metadata': {
                    'image_size': image_info,
                    'processing_time': result.get('time', 0),
                    'inference_id': result.get('inference_id', ''),
                    'timestamp': datetime.now().isoformat()
                },
                'summary': self._summarize_predictions(processed_preds)
            }
            
            return processed_results
            
        except Exception as e:
            print(f"Error in _process_predictions: {e}")
            import traceback
            traceback.print_exc()
            return {
                'predictions': [],
                'metadata': {},
                'summary': self._summarize_predictions([]),
                'timestamp': datetime.now().isoformat()
            }

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
        if self.refresh_ui:
            self.refresh_ui()

    def get_last_predictions(self) -> Optional[Dict[str, Any]]:
        """Get the most recent prediction results"""
        return self.last_predictions

    def process_piece(self, image_url: str) -> tuple[bool, Optional[Dict[str, Any]]]:
        """
        Complete piece processing pipeline
        
        Args:
            image_url: URL of the image to process
            
        Returns:
            Tuple of (success: bool, results: Optional[Dict])
            where results contains the full prediction data if successful
        """
        # Get image
        image_data = self.get_image(image_url)
        if not image_data:
            return False, None
        
        # Analyze image
        results = self.analyze_image(image_data)
        return bool(results), results