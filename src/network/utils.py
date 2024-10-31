# src/network/utils.py
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlparse

def format_time_ago(timestamp: datetime) -> str:
    """Format a timestamp as a human-readable time ago string"""
    if not timestamp:
        return "Never"
    
    delta = datetime.now() - timestamp
    
    if delta < timedelta(minutes=1):
        return f"{delta.seconds}s ago"
    elif delta < timedelta(hours=1):
        minutes = delta.seconds // 60
        return f"{minutes}m ago"
    elif delta < timedelta(days=1):
        hours = delta.seconds // 3600
        return f"{hours}h ago"
    else:
        return f"{delta.days}d ago"

def parse_service_url(url: str) -> tuple[str, Optional[str]]:
    """Parse a service URL into hostname and path"""
    try:
        parsed = urlparse(url)
        return parsed.hostname or "", parsed.path or None
    except Exception:
        return "", None