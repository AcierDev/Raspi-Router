# src/imaging/cache.py
from datetime import datetime
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class ImageCache:
    """LRU cache for processed images with size and time limits"""
    
    def __init__(self, max_size_mb: int = 100, max_age_seconds: int = 3600):
        self.max_size = max_size_mb * 1024 * 1024  # Convert to bytes
        self.max_age = max_age_seconds
        self.cache: Dict[str, Tuple[bytes, datetime, int]] = {}
        self.current_size = 0

    def _clean_expired(self):
        """Remove expired entries from cache"""
        current_time = datetime.now()
        expired_keys = [
            key for key, (_, timestamp, _) in self.cache.items()
            if (current_time - timestamp).total_seconds() > self.max_age
        ]
        for key in expired_keys:
            self._remove_entry(key)

    def _remove_entry(self, key: str):
        """Remove a single entry from cache"""
        if key in self.cache:
            _, _, size = self.cache[key]
            self.current_size -= size
            del self.cache[key]

    def _make_space(self, needed_size: int):
        """Remove oldest entries until there's enough space"""
        entries = sorted(self.cache.items(), key=lambda x: x[1][1])  # Sort by timestamp
        while self.current_size + needed_size > self.max_size and entries:
            key, _ = entries.pop(0)
            self._remove_entry(key)

    def get(self, key: str) -> Optional[bytes]:
        """Get an item from cache if it exists and isn't expired"""
        self._clean_expired()
        if key in self.cache:
            data, timestamp, _ = self.cache[key]
            if (datetime.now() - timestamp).total_seconds() <= self.max_age:
                return data
            self._remove_entry(key)
        return None

    def put(self, key: str, data: bytes):
        """Add an item to cache, managing size limits"""
        self._clean_expired()
        size = len(data)
        if size > self.max_size:
            return  # Skip if single item is too large
        
        self._make_space(size)
        if key in self.cache:
            self._remove_entry(key)
        
        self.cache[key] = (data, datetime.now(), size)
        self.current_size += size