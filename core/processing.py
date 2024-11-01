import requests
from config import (
    IMAGE_URL, 
    INFERENCE_URL, 
    NETWORK_TIMEOUTS, 
    DOWNLOAD_CHUNK_SIZE
)
from typing import Optional, Dict, List, Any, Tuple
import logging
from datetime import datetime
import json

class ImageProcessor:
    def __init__(self, status_callback=None):
        self.status_callback = status_callback
        self.refresh_ui = None
        self.logger = logging.getLogger(__name__)
        self.last_predictions = None
        
        # Confidence thresholds
        self.CONFIDENCE_THRESHOLDS = {
            'high': 0.85,
            'medium': 0.65,
            'low': 0.50
        }

    def get_image(self) -> Optional[bytes]:
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
            self.logger.error(f"Error during image capture: {str(e)}", exc_info=True)
            self.update_status(f"Error during image capture: {str(e)}", is_network=True)
            return None

    def analyze_image(self, image_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Send image to AI server for analysis and process results
        """
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
            
            # Print raw response for debugging
            print("\nRaw API Response:")
            print(f"Status Code: {response.status_code}")
            print("Response Headers:", dict(response.headers))
            try:
                print("Response JSON:", json.dumps(response.json(), indent=2))
            except:
                print("Raw Response Text:", response.text)
            
            if response.status_code == 200:
                result = response.json()
                processed_results = self._process_predictions(result)
                self.last_predictions = processed_results
                return processed_results
                
            self.update_status(f"Server returned error: {response.status_code}", is_network=True)
            print(f"Error response content: {response.text}")
            return None
                
        except Exception as e:
            self.logger.error(f"Analysis failed: {str(e)}", exc_info=True)
            self.update_status(f"Analysis failed: {str(e)}", is_network=True)
            return None

    def _process_predictions(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Process and validate prediction results"""
        try:
            predictions = result.get('predictions', [])
            metadata = result.get('metadata', {})
            
            if not predictions:
                return {
                    'predictions': [],
                    'metadata': metadata,
                    'summary': self._summarize_predictions([]),
                    'timestamp': datetime.now().isoformat()
                }
            
            # Process each prediction
            processed_preds = []
            for i, pred in enumerate(predictions):
                try:
                    confidence = pred.get('confidence', 0)
                    
                    # Skip low confidence predictions
                    if confidence < self.CONFIDENCE_THRESHOLDS['low']:
                        continue
                    
                    # Get bbox from the prediction
                    bbox = pred.get('bbox', [])
                    if not bbox or len(bbox) != 4:
                        print(f"Warning: Invalid bbox in prediction {i}: {bbox}")
                        continue
                    
                    # Ensure bbox coordinates are valid
                    bbox = [max(0, min(1, coord)) for coord in bbox]
                    
                    # Determine confidence level
                    confidence_level = self._get_confidence_level(confidence)
                    
                    processed_pred = {
                        'class_name': pred.get('class_name', 'unknown'),
                        'confidence': confidence,
                        'confidence_level': confidence_level,
                        'bbox': bbox,
                        'detection_id': pred.get('detection_id', f'det_{i}'),
                        'metadata': {
                            'area': self._calculate_bbox_area(bbox),
                            'center': self._calculate_bbox_center(bbox),
                            'severity': self._estimate_severity(confidence, bbox)
                        }
                    }
                    print(f"Processed prediction {i}:", processed_pred)
                    processed_preds.append(processed_pred)
                    
                except Exception as e:
                    print(f"Error processing prediction {i}: {e}")
                    continue
            
            # Sort predictions by confidence
            processed_preds.sort(key=lambda x: x['confidence'], reverse=True)
            
            processed_results = {
                'predictions': processed_preds,
                'metadata': {
                    **metadata,
                    'processing_time': metadata.get('processing_time', 0),
                    'model_version': metadata.get('model_version', 'unknown'),
                    'timestamp': datetime.now().isoformat()
                },
                'summary': self._summarize_predictions(processed_preds)
            }
            
            print("\nFinal processed results:")
            print(json.dumps(processed_results, indent=2))
            
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
        if not bbox or len(bbox) != 4:
            return 'unknown'
            
        area = self._calculate_bbox_area(bbox)
        
        # Severity matrix based on confidence and size
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
        """
        Create comprehensive summary of predictions
        """
        if not predictions:
            return {
                'count': 0,
                'class_counts': {},
                'severity_counts': {},
                'average_confidence': 0.0,
                'total_area': 0.0
            }
            
        # Count by class and severity
        class_counts = {}
        severity_counts = {}
        total_area = 0.0
        
        for pred in predictions:
            # Class counts
            class_name = pred.get('class_name', 'unknown')
            class_counts[class_name] = class_counts.get(class_name, 0) + 1
            
            # Severity counts
            severity = pred.get('metadata', {}).get('severity', 'unknown')
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            # Accumulate area
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

    def process_piece(self) -> tuple[bool, Optional[Dict[str, Any]]]:
        """
        Complete piece processing pipeline
        
        Returns:
            Tuple of (success: bool, results: Optional[Dict])
            where results contains the full prediction data if successful
        """
        # Get image
        image_data = self.get_image()
        if not image_data:
            return False, None
        
        # Analyze image
        results = self.analyze_image(image_data)
        return bool(results), results