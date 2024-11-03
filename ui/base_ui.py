# ui/base_ui.py

from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from config import MAX_LOG_MESSAGES, VISIBLE_LOG_MESSAGES

class BaseUI:
    """Base class for UI implementations"""
    
    def __init__(self):
        self.status_messages = []
        self.current_status = {
            'state': 'normal',
            'alert': None,
            'last_inference': None,
            'last_confidence': None,
            'system_status': 'Running'
        }
        
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
        """Add a new status message to the log"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        prefix = "ALERT: " if is_alert else "NETWORK: " if is_network else ""
        self.status_messages.append(f"[{timestamp}] {prefix}{message}")
        
        # Maintain maximum message count
        if len(self.status_messages) > MAX_LOG_MESSAGES:
            self.status_messages.pop(0)

    def get_network_status_text(self, network_status: Any, service: str) -> str:
        """Format network status text for a service"""
        info = network_status.status[service]
        status_text = f"{service.title()}: {info.get('status', 'Unknown')}"
        
        if service in ['camera', 'ai_server']:
            if info.get('ip'):
                status_text += f"\n  IP: {info['ip']}"
            if info.get('ping_time'):
                status_text += f"\n  Ping: {info['ping_time']}"
            if info.get('last_success'):
                last_success = network_status.format_last_success(info['last_success'])
                status_text += f"\n  Last: {last_success}"
        
        return status_text

    def get_sensor_status_text(self, gpio_controller: Any) -> List[Tuple[str, bool]]:
        """Format sensor status text"""
        return [
            ("Sensor 1", gpio_controller.read_sensor1()),
            ("Sensor 2", gpio_controller.read_sensor2()),
            ("Solenoid", gpio_controller.get_solenoid_state())
        ]

    def format_status_message(self, message: str, max_length: Optional[int] = None) -> str:
        """Format a status message for display"""
        if max_length and len(message) > max_length:
            return message[:max_length-3] + '...'
        return message

    def get_visible_messages(self) -> List[str]:
        """Get the most recent messages for display"""
        return self.status_messages[-VISIBLE_LOG_MESSAGES:]

    def update_image(self, image_data: bytes) -> None:
        """Update the current image and timestamp"""
        self.current_image = image_data
        self.image_timestamp = datetime.now() if image_data else None
        self.update_status_message("Camera image updated" if image_data else "Camera image cleared")

    def update_predictions(self, predictions: Optional[Dict[str, Any]]) -> None:
        """Update current predictions and process detection results"""
        try:
            self.current_predictions = predictions
            
            if predictions:
                # Update status with detection summary
                summary = predictions.get('summary', {})
                count = summary.get('count', 0)
                
                if count > 0:
                    best_pred = summary.get('best_prediction', {})
                    confidence = best_pred.get('confidence', 0)
                    class_name = best_pred.get('class_name', 'unknown')
                    
                    self.current_status['last_inference'] = datetime.now().strftime("%H:%M:%S")
                    self.current_status['last_confidence'] = confidence
                    
                    self.update_status_message(
                        f"Detected {count} defects - Best: {class_name} ({confidence:.1%})"
                    )
                else:
                    self.update_status_message("No defects detected")
                    self.current_status['last_confidence'] = 0.0
            else:
                self.current_status['last_confidence'] = None
                
        except Exception as e:
            self.update_status_message(f"Error processing predictions: {str(e)}", is_alert=True)

    def get_detection_color(self, class_name: str) -> Tuple[int, int, int]:
        """Get the color for a defect type"""
        return self.defect_colors.get(class_name.lower(), self.defect_colors['default'])

    def format_detection_label(self, class_name: str, confidence: float) -> str:
        """Format the label text for a detection"""
        return f"{class_name} {confidence:.1%}"

    def get_detection_summary(self) -> Dict[str, Any]:
        """Get a formatted summary of current detections"""
        if not self.current_predictions:
            return {'count': 0, 'types': {}}
            
        summary = self.current_predictions.get('summary', {})
        return {
            'count': summary.get('count', 0),
            'types': summary.get('class_counts', {}),
            'best_confidence': summary.get('best_prediction', {}).get('confidence', 0),
            'total_area': summary.get('total_area', 0)
        }

    def clear_image(self) -> None:
        """Clear the current image"""
        self.current_image = None
        self.image_timestamp = None
        self.current_predictions = None
        self.update_status_message("Camera view cleared")

    def cleanup(self) -> None:
        """Clean up resources - to be implemented by subclasses"""
        pass

    def draw(self, *args, **kwargs) -> None:
        """Draw the UI - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement draw()")