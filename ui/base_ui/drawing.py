from PIL import ImageDraw, ImageFont
from typing import Tuple, Optional, Dict, Any, List
from datetime import datetime, timedelta

class DrawingUtils:
    """Utility class for UI drawing operations"""
    
    def __init__(self):
        # UI layout constants
        self.SECTION_PADDING = 10
        self.SECTION_GAP = 20
        self.LINE_HEIGHT = 20
        self.SMALL_LINE_HEIGHT = 15
        self.TITLE_HEIGHT = 22
        
        # Initialize fonts
        self.font = self._init_fonts()
        self.small_font = self._init_fonts(size=10)

    def _init_fonts(self, size: int = 14) -> ImageFont.FreeTypeFont:
        """Initialize fonts with fallbacks"""
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/TTF/DejaVuSansMono.ttf"
        ]
        
        for path in font_paths:
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
                
        return ImageFont.load_default()

    def draw_section(self, drawer: ImageDraw, title: str, x: int, y: int, 
                    width: int, height: int, highlight: bool = False) -> int:
        """Draw a section box with title"""
        # Draw section box
        drawer.rectangle(
            [x, y, x + width, y + height], 
            outline=(255, 255, 255)
        )
        
        # Draw title background
        title_bg_color = (255, 0, 0) if highlight else (0, 0, 255)
        drawer.rectangle(
            [x + 1, y + 1, x + width - 1, y + 20],
            fill=title_bg_color
        )
        
        # Draw title text
        drawer.text(
            (x + 5, y + 2),
            title,
            font=self.font,
            fill=(255, 255, 255)
        )
        
        return y + 22  # Return position below title

    def draw_metrics(self, drawer: ImageDraw, metrics: Dict[str, Any],
                    x: int, y: int, width: int) -> int:
        """Draw metrics section with dynamic spacing"""
        current_y = y
        
        def draw_metric(text: str, color: Tuple[int, int, int] = (255, 255, 255)) -> None:
            nonlocal current_y
            drawer.text(
                (x + 10, current_y),
                text,
                font=self.font,
                fill=color
            )
            current_y += self.LINE_HEIGHT
        
        # Draw uptime
        if 'start_time' in metrics:
            uptime = datetime.now() - metrics['start_time']
            draw_metric(f"Uptime: {str(uptime).split('.')[0]}")
        
        # Process counts
        processed = metrics.get('processed_count', 0)
        draw_metric(f"Total Processed: {processed}")
        
        # Processing times
        last_time = metrics.get('last_process_time')
        if last_time is not None:
            avg_time = metrics.get('average_process_time', 0)
            color = (255, 165, 0) if last_time > avg_time * 1.5 else (255, 255, 255)
            draw_metric(f"Last Process: {last_time:.2f}s", color)
            draw_metric(f"Avg Process: {avg_time:.2f}s")
        
        if 'min_process_time' in metrics:
            draw_metric(f"Min Process: {metrics['min_process_time']:.2f}s", (0, 255, 0))
        if 'max_process_time' in metrics:
            draw_metric(f"Max Process: {metrics['max_process_time']:.2f}s", (255, 0, 0))
        
        # Error stats
        error_count = metrics.get('error_count', 0)
        if processed > 0:
            error_rate = (error_count / processed) * 100
            draw_metric(f"Errors: {error_count} ({error_rate:.1f}%)", (255, 0, 0))
        
        return current_y

    def draw_network_status(self, drawer: ImageDraw, network_status: Dict[str, Any],
                          x: int, y: int) -> int:
        """Draw network status information"""
        current_y = y
        
        for service, info in network_status.items():
            # Draw service status
            color = (0, 255, 0) if info.get('status') == 'Connected' else (255, 0, 0)
            drawer.text(
                (x, current_y),
                f"{service.title()}: {info.get('status', 'Unknown')}",
                font=self.font,
                fill=color
            )
            current_y += self.LINE_HEIGHT
            
            # Draw additional info if available
            if service in ['camera', 'ai_server']:
                if info.get('ip'):
                    drawer.text(
                        (x + 20, current_y),
                        f"IP: {info['ip']}",
                        font=self.font,
                        fill=(255, 255, 255)
                    )
                    current_y += self.SMALL_LINE_HEIGHT
                
                if info.get('ping_time'):
                    drawer.text(
                        (x + 20, current_y),
                        f"Ping: {info['ping_time']}ms",
                        font=self.font,
                        fill=(255, 255, 255)
                    )
                    current_y += self.SMALL_LINE_HEIGHT
            
            current_y += 5  # Add spacing between services
        
        return current_y

    def draw_sensor_status(self, drawer: ImageDraw, sensor_states: List[Tuple[str, bool]],
                          x: int, y: int) -> int:
        """Draw sensor status indicators"""
        current_y = y
        
        for name, state in sensor_states:
            color = (0, 255, 0) if state else (255, 0, 0)
            status_text = 'Active' if state else 'Inactive'
            
            # Draw status indicator circle
            circle_x = x + 5
            circle_y = current_y + 7
            drawer.ellipse(
                [circle_x, circle_y, circle_x + 8, circle_y + 8],
                fill=color
            )
            
            # Draw label
            drawer.text(
                (x + 20, current_y),
                f"{name}: {status_text}",
                font=self.font,
                fill=(255, 255, 255)
            )
            
            current_y += self.LINE_HEIGHT
        
        return current_y

    def draw_log_messages(self, drawer: ImageDraw, messages: List[str],
                         x: int, y: int, max_width: int) -> int:
        """Draw log messages with proper formatting"""
        current_y = y
        
        for message in messages:
            # Determine message color
            color = (255, 0, 0) if 'ALERT:' in message else (
                    0, 255, 255) if 'NETWORK:' in message else (200, 200, 200)
            
            # Truncate message if needed
            max_chars = max_width // 8  # Approximate characters that fit
            display_message = (message[:max_chars] + '...') if len(message) > max_chars else message
            
            drawer.text(
                (x, current_y),
                display_message,
                font=self.font,
                fill=color
            )
            current_y += self.SMALL_LINE_HEIGHT
        
        return current_y

    def get_text_width(self, drawer: ImageDraw, text: str, 
                      font: Optional[ImageFont.FreeTypeFont] = None) -> int:
        """Get text width using specified or default font"""
        font = font or self.font
        if hasattr(drawer, 'textlength'):
            return int(drawer.textlength(text, font=font))
        else:
            bbox = drawer.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0]

    def draw_placeholder(self, drawer: ImageDraw, x: int, y: int,
                        width: int, height: int, text: str = "No Image") -> None:
        """Draw a placeholder box with text"""
        text_bbox = drawer.textbbox((0, 0), text, font=self.font)
        text_width = text_bbox[2] - text_bbox[0]
        text_x = x + (width - text_width) // 2
        text_y = y + height // 2 - 10
        
        drawer.text(
            (text_x, text_y),
            text,
            font=self.font,
            fill=(128, 128, 128)
        )

    def calculate_section_height(self, content_height: int) -> int:
        """Calculate total section height including padding"""
        return content_height + (self.SECTION_PADDING * 2) + self.TITLE_HEIGHT