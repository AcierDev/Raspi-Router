# src/ui/layout.py
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class Layout:
    """Stores UI layout dimensions"""
    ui_width: int
    image_width: int
    header_height: int
    section_padding: int
    content_padding: int
    status_height: int
    network_height: int
    sensor_height: int
    alert_height: int
    log_height: int

class LayoutManager:
    """Handles UI layout calculations and management"""
    
    @staticmethod
    def calculate_layout(screen_width: int, screen_height: int) -> Layout:
        """Calculate UI layout dimensions based on screen size"""
        return Layout(
            ui_width=screen_width // 2,
            image_width=screen_width // 2,
            header_height=30,
            section_padding=10,
            content_padding=5,
            status_height=50,
            network_height=180,
            sensor_height=100,
            alert_height=60,
            log_height=170
        )
