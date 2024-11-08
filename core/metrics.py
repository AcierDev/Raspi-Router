from datetime import datetime
from typing import Dict, Any, Optional

class MetricsManager:
    def __init__(self):
        self.metrics = {
            'processed_count': 0,
            'error_count': 0,
            'start_time': datetime.now(),
            'last_process_time': None,
            'total_errors': 0
        }
        self.last_error = None
        self.last_successful_process = None
        self.results_history = []
        self.MAX_HISTORY = 100

    def update_metrics(self, success: bool = True, error: Optional[str] = None,
                      processing_time: Optional[float] = None) -> None:
        if success:
            self.metrics['processed_count'] += 1
            self.last_successful_process = datetime.now()
        else:
            self.metrics['error_count'] += 1
            self.last_error = error
            self.metrics['total_errors'] += 1
        
        if processing_time is not None:
            self.metrics['last_process_time'] = processing_time

    def add_to_history(self, result: Dict[str, Any]) -> None:
        self.results_history.append(result)
        if len(self.results_history) > self.MAX_HISTORY:
            self.results_history.pop(0)