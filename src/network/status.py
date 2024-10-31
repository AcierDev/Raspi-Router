# src/network/status.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any

@dataclass
class ServiceStatus:
    """Represents the current status of a monitored service"""
    status: str = "Unknown"
    last_check: Optional[datetime] = None
    last_success: Optional[datetime] = None
    ping_time: Optional[float] = None
    ip: Optional[str] = None
    error_count: int = 0
    additional_info: Dict[str, Any] = None

    def __post_init__(self):
        if self.additional_info is None:
            self.additional_info = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the service status with a default fallback"""
        if hasattr(self, key):
            return getattr(self, key)
        return self.additional_info.get(key, default)

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access to status attributes"""
        if hasattr(self, key):
            return getattr(self, key)
        if key in self.additional_info:
            return self.additional_info[key]
        raise KeyError(key)

    def update(self, **kwargs):
        """Update service status fields"""
        for key, value in kwargs.items():
            if hasattr(self, key) and key != 'additional_info':
                setattr(self, key, value)
            else:
                if self.additional_info is None:
                    self.additional_info = {}
                self.additional_info[key] = value

    def __setitem__(self, key: str, value: Any):
        """Allow dictionary-style setting of attributes"""
        if hasattr(self, key) and key != 'additional_info':
            setattr(self, key, value)
        else:
            if self.additional_info is None:
                self.additional_info = {}
            self.additional_info[key] = value