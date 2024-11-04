from datetime import datetime
from typing import Optional, List, Any
from config import MAX_LOG_MESSAGES, VISIBLE_LOG_MESSAGES

class StatusManager:
    """Manages UI status messages and states"""
    
    def __init__(self):
        self.messages = []
        self.current_status = {
            'state': 'normal',
            'alert': None,
            'last_inference': None,
            'last_confidence': None,
            'system_status': 'Running'
        }

    def add_message(self, message: str, is_alert: bool = False, 
                   is_network: bool = False) -> None:
        """Add a new status message to the log"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        prefix = "ALERT: " if is_alert else "NETWORK: " if is_network else ""
        self.messages.append(f"[{timestamp}] {prefix}{message}")
        
        # Maintain maximum message count
        if len(self.messages) > MAX_LOG_MESSAGES:
            self.messages.pop(0)

    def update_state(self, new_state: str, alert_message: Optional[str] = None) -> None:
        """Update the current system state"""
        self.current_status['state'] = new_state
        if alert_message is not None:
            self.current_status['alert'] = alert_message
            if alert_message:
                self.add_message(alert_message, is_alert=True)

    def update_inference(self, timestamp: Optional[datetime], 
                        confidence: Optional[float]) -> None:
        """Update inference-related status"""
        if timestamp:
            self.current_status['last_inference'] = timestamp.strftime("%H:%M:%S")
        self.current_status['last_confidence'] = confidence

    def get_visible_messages(self) -> List[str]:
        """Get the most recent messages for display"""
        return self.messages[-VISIBLE_LOG_MESSAGES:]

    def format_message(self, message: str, max_length: Optional[int] = None) -> str:
        """Format a status message for display"""
        if max_length and len(message) > max_length:
            return message[:max_length-3] + '...'
        return message

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

    def get_sensor_status_text(self, gpio_controller: Any) -> List[tuple]:
        """Format sensor status text"""
        return [
            ("Sensor 1", gpio_controller.read_sensor1()),
            ("Sensor 2", gpio_controller.read_sensor2()),
            ("Solenoid", gpio_controller.get_solenoid_state())
        ]

    def clear_alert(self) -> None:
        """Clear the current alert"""
        self.current_status['alert'] = None