# src/system/state.py
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class SystemState:
    """Represents the current state of the inspection system"""
    piece_in_progress: bool = False
    waiting_for_sensor2: bool = False
    sensor2_check_time: Optional[float] = None
    processing_active: bool = False
    error_state: bool = False
    shutdown_requested: bool = False
    last_network_check: float = 0
