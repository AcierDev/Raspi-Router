# src/ui/state.py
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class UIState:
    """Represents the current UI state"""
    state: str = "normal"
    alert: Optional[str] = None
    last_inference: Optional[str] = None
    last_confidence: Optional[float] = None
    system_status: str = "Running"