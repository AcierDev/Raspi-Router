from PIL import ImageDraw
from typing import Dict, Any, Tuple, List
from datetime import timedelta

class SectionRenderer:
    """Handles rendering of different UI sections"""
    
    def __init__(self, drawing_utils):
        self.drawing = drawing_utils

    def render_metrics_section(self, drawer: ImageDraw, metrics: Dict[str, Any], x: int, y: int, width: int) -> int:
        """Render metrics section with dynamic spacing"""
        current_y = self.drawing.draw_section(drawer, "System Metrics", "", x, y, width, self._calculate_metrics_height())
        initial_y = current_y

        def draw_metric(text: str, color: Tuple[int, int, int] = (255, 255, 255)) -> None:
            nonlocal current_y
            drawer.text((x + 10, current_y), text, font=self.drawing.font, fill=color)
            current_y += self.drawing.LINE_HEIGHT

        # Draw metrics
        self._draw_uptime(metrics, draw_metric)
        self._draw_processing_stats(metrics, draw_metric)
        self._draw_defect_stats(metrics, draw_metric)
        self._draw_error_rate(metrics, draw_metric)

        return current_y

    def render_network_section(self, drawer: ImageDraw, network_status: Any, x: int, y: int, width: int) -> int:
        """Render network status section"""
        current_y = self.drawing.draw_section(drawer, "Network Status", "", x, y, width, self._calculate_network_height(network_status))
        self.drawing.draw_network_status(drawer, network_status, x + 10, current_y)
        return current_y + self._calculate_network_height(network_status)

    def render_sensor_section(self, drawer: ImageDraw, gpio_controller: Any, x: int, y: int, width: int) -> int:
        """Render sensor status section"""
        sensor_height = self._calculate_sensor_height()
        current_y = self.drawing.draw_section(drawer, "Sensor Status", "", x, y, width, sensor_height)
        
        sensor_states = [
            ("Sensor 1", gpio_controller.read_sensor1()),
            ("Sensor 2", gpio_controller.read_sensor2()),
            ("Solenoid", gpio_controller.get_solenoid_state())
        ]
        
        self.drawing.draw_sensor_status(drawer, sensor_states, x + 10, current_y)
        return current_y + sensor_height

    def render_alert_section(self, drawer: ImageDraw, alert: str, x: int, y: int, width: int) -> int:
        """Render alert section if there is an alert"""
        if not alert:
            return y
            
        alert_height = self._calculate_alert_height()
        current_y = self.drawing.draw_section(drawer, "Alert", "", x, y, width, alert_height, highlight=True)
        
        drawer.text((x + 10, current_y), alert, font=self.drawing.font, fill=(255, 0, 0))
        return current_y + alert_height

    def render_log_section(self, drawer: ImageDraw, messages: List[str], x: int, y: int, width: int, height: int) -> int:
        """Render system log section"""
        current_y = self.drawing.draw_section(drawer, "System Log", "", x, y, width, height)
        self.drawing.draw_log_messages(drawer, messages, x + 10, current_y, width - 20)
        return current_y + height

    # Height Calculation Methods
    def _calculate_metrics_height(self) -> int:
        """Calculate required height for metrics section"""
        return (self.drawing.SECTION_PADDING * 2 +
                self.drawing.TITLE_HEIGHT +
                (9 * self.drawing.LINE_HEIGHT) +
                30 +  # Extra spacing for sections
                self.drawing.LINE_HEIGHT +  # "Defect Types:" header
                (3 * self.drawing.SMALL_LINE_HEIGHT))  # Minimum 3 defect type lines

    def _calculate_network_height(self, network_status: Any) -> int:
        """Calculate required height for network section"""
        height = self.drawing.SECTION_PADDING * 2 + self.drawing.TITLE_HEIGHT
        height += sum(self._calculate_network_service_height(info) for service, info in network_status.status.items())
        return height

    def _calculate_network_service_height(self, info: Dict[str, Any]) -> int:
        """Calculate the height required for each network service's details"""
        height = self.drawing.LINE_HEIGHT
        if info.get('ip'): height += self.drawing.SMALL_LINE_HEIGHT
        if info.get('ping_time'): height += self.drawing.SMALL_LINE_HEIGHT
        if info.get('last_success'): height += self.drawing.SMALL_LINE_HEIGHT
        return height + 5

    def _calculate_sensor_height(self) -> int:
        """Calculate required height for sensor section"""
        return (self.drawing.SECTION_PADDING * 2 +
                self.drawing.TITLE_HEIGHT +
                (3 * self.drawing.LINE_HEIGHT))

    def _calculate_alert_height(self) -> int:
        """Calculate height for alert section"""
        return (self.drawing.SECTION_PADDING * 2 +
                self.drawing.TITLE_HEIGHT +
                self.drawing.LINE_HEIGHT)

    def calculate_total_height(self, metrics: Dict[str, Any], network_status: Any, has_alert: bool, messages: List[str]) -> int:
        """Calculate total height needed for all sections dynamically based on content"""
        height = (
            self._calculate_metrics_height() +
            self.drawing.SECTION_GAP +
            self._calculate_network_height(network_status) +
            self.drawing.SECTION_GAP +
            self._calculate_sensor_height() +
            (self._calculate_alert_height() + self.drawing.SECTION_GAP if has_alert else 0) +
            self._calculate_log_height(messages)  # Pass messages to log height calculation
        )
        return height



    # Helper Methods for Metrics Rendering
    def _draw_uptime(self, metrics: Dict[str, Any], draw_metric) -> None:
        uptime = metrics['metrics'].get('uptime', timedelta())
        draw_metric(f"Uptime: {str(uptime).split('.')[0]}")

    def _draw_processing_stats(self, metrics: Dict[str, Any], draw_metric) -> None:
        stats = metrics['processing_stats']
        total_processed = metrics['metrics']['processed_count']
        
        draw_metric(f"Total Processed: {total_processed}")
        if stats['count'] > 0:
            last_time = metrics['metrics'].get('last_process_time')
            last_color = ((255, 165, 0) if last_time > stats['total_time'] / stats['count'] * 1.5 else (255, 255, 255))
            draw_metric(f"Last Process: {last_time:.2f}s", last_color)
            draw_metric(f"Avg Process: {stats['total_time'] / stats['count']:.2f}s")
            draw_metric(f"Min Process: {stats['min_time']:.2f}s", (0, 255, 0))
            draw_metric(f"Max Process: {stats['max_time']:.2f}s", (255, 0, 0))

    def _draw_defect_stats(self, metrics: Dict[str, Any], draw_metric) -> None:
        total_defects = sum(metrics['metrics']['defect_counts'].values())
        avg_defects = total_defects / max(1, metrics['metrics']['processed_count'])
        draw_metric(f"Total Defects: {total_defects}")
        draw_metric(f"Avg Defects/Item: {avg_defects:.2f}")

    def _draw_error_rate(self, metrics: Dict[str, Any], draw_metric) -> None:
        error_rate = (metrics['metrics']['error_count'] / max(1, metrics['metrics']['processed_count'])) * 100
        draw_metric(f"Errors: {metrics['metrics']['error_count']} ({error_rate:.1f}%)", (255, 0, 0))

    def _calculate_log_height(self, messages: List[str]) -> int:
        """Calculate required height for log section based on the number of messages."""
        lines_needed = len(messages)
        return (
            self.drawing.SECTION_PADDING * 2 +
            self.drawing.TITLE_HEIGHT +
            (lines_needed * self.drawing.LINE_HEIGHT)
        )