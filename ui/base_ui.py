# ui/base_ui.py

from datetime import datetime
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
        self.current_image = None
        self.image_timestamp = None

    def update_status_message(self, message, is_alert=False, is_network=False):
        """Add a new status message to the log"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        prefix = "ALERT: " if is_alert else "NETWORK: " if is_network else ""
        self.status_messages.append(f"[{timestamp}] {prefix}{message}")
        
        # Maintain maximum message count
        if len(self.status_messages) > MAX_LOG_MESSAGES:
            self.status_messages.pop(0)

    def get_network_status_text(self, network_status, service):
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

    def get_sensor_status_text(self, gpio_controller):
        """Format sensor status text"""
        return [
            ("Sensor 1", gpio_controller.read_sensor1()),
            ("Sensor 2", gpio_controller.read_sensor2()),
            ("Solenoid", gpio_controller.get_solenoid_state())
        ]

    def format_status_message(self, message, max_length=None):
        """Format a status message for display"""
        if max_length and len(message) > max_length:
            return message[:max_length-3] + '...'
        return message

    def get_visible_messages(self):
        """Get the most recent messages for display"""
        return self.status_messages[-VISIBLE_LOG_MESSAGES:]

    def update_image(self, image_data):
        """Update the current image and timestamp"""
        self.current_image = image_data
        self.image_timestamp = datetime.now() if image_data else None
        self.update_status_message("Camera image updated" if image_data else "Camera image cleared")

    def clear_image(self):
        """Clear the current image"""
        self.current_image = None
        self.image_timestamp = None
        self.update_status_message("Camera view cleared")

    def cleanup(self):
        """Clean up resources - to be implemented by subclasses"""
        pass

    def draw(self, *args, **kwargs):
        """Draw the UI - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement draw()")