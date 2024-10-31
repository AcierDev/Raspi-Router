# src/imaging/analysis.py
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List

@dataclass
class ImageAnalysis:
    """Stores the results of image analysis"""
    confidence: float
    class_name: str
    timestamp: datetime
    processing_time: float
    additional_predictions: List[Dict[str, Any]]
    metadata: Dict[str, Any]