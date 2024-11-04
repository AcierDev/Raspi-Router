from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from .metrics import UIMetrics
from .status import StatusManager
from .drawing import DrawingUtils

class BaseUI:
    def __init__(self):
        self.metrics = UIMetrics()
        self.status = StatusManager()
        self.drawing = DrawingUtils()
        
        # Image and detection related attributes
        self.current_image = None
        self.image_timestamp = None
        self.current_predictions = None
        
        # Standard colors for different defect types
        self.defect_colors = {
            'knot': (255, 99, 71),     # Tomato red
            'edge': (65, 105, 225),    # Royal blue
            'corner': (50, 205, 50),   # Lime green
            'damage': (255, 0, 0),     # Red
            'side': (147, 112, 219),   # Medium purple
            'default': (255, 165, 0)   # Orange (for unknown types)
        }

    def update_status_message(self, message: str, is_alert: bool = False, is_network: bool = False) -> None:
        """Legacy method to maintain compatibility - redirects to StatusManager"""
        self.status.add_message(message, is_alert, is_network)

    def update_metrics(self, results=None, error=None, processing_time=None) -> None:
        """Update system metrics with processing results"""
        if results or error or processing_time:
            self.metrics.update(
                results=results,
                error=error,
                processing_time=processing_time
            )
            
            # Update status based on results
            if error:
                self.status.add_message(f"Processing error: {error}", is_alert=True)
            elif results:
                # Update based on successful results
                if 'summary' in results:
                    count = results['summary'].get('count', 0)
                    if count > 0:
                        best_pred = results['summary'].get('best_prediction', {})
                        confidence = best_pred.get('confidence', 0)
                        class_name = best_pred.get('class_name', 'unknown')
                        self.status.add_message(
                            f"Processed successfully - Found {count} defects - Best: {class_name} ({confidence:.1%})"
                        )
                    else:
                        self.status.add_message("Processed successfully - No defects found")

    def update_image(self, image_data: bytes) -> None:
        """Update the current image and timestamp"""
        self.current_image = image_data
        self.image_timestamp = datetime.now() if image_data else None
        self.status.add_message("Camera image updated" if image_data else "Camera image cleared")

    def update_predictions(self, predictions: Optional[Dict[str, Any]]) -> None:
        """Update current predictions and process detection results"""
        self.current_predictions = predictions
        if predictions:
            summary = predictions.get('summary', {})
            count = summary.get('count', 0)
            
            if count > 0:
                best_pred = summary.get('best_prediction', {})
                confidence = best_pred.get('confidence', 0)
                class_name = best_pred.get('class_name', 'unknown')
                
                self.status.update_inference(datetime.now(), confidence)
                self.status.add_message(
                    f"Detected {count} defects - Best: {class_name} ({confidence:.1%})"
                )
            else:
                self.status.add_message("No defects detected")
                self.status.update_inference(None, 0.0)
        else:
            self.status.update_inference(None, None)

    def start_processing(self) -> None:
        """Start timing for processing"""
        self.metrics.start_processing()

    def cleanup(self) -> None:
        """Clean up resources - to be implemented by subclasses"""
        pass

    def draw(self, *args, **kwargs) -> None:
        """Draw the UI - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement draw()")