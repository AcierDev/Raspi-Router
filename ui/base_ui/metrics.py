from datetime import datetime
from typing import Dict, Any, List, Optional

class UIMetrics:
    """Handles tracking and computation of UI metrics"""
    
    def __init__(self):
        self._metrics = {
            'start_time': datetime.now(),
            'processed_count': 0,
            'defect_counts': {},
            'processing_times': [],
            'current_processing_start': None,
            'error_count': 0,
            'last_process_time': None,
            'detection_history': [],
            'hourly_counts': {},
            'daily_counts': {},
        }
        
        self._processing_stats = {
            'min_time': float('inf'),
            'max_time': 0,
            'total_time': 0,
            'count': 0
        }
        
        self.MAX_HISTORY = 100

    def __getitem__(self, key):
        """Allow dictionary-style access to metrics"""
        return self._metrics[key]

    def __setitem__(self, key, value):
        """Allow dictionary-style setting of metrics"""
        self._metrics[key] = value

    def start_processing(self) -> None:
        """Mark the start of processing for timing purposes"""
        self._metrics['current_processing_start'] = datetime.now().timestamp()

    @property
    def metrics(self):
        """Get all metrics"""
        return self._metrics

    @property
    def processing_stats(self):
        """Get processing statistics"""
        return self._processing_stats

    def update(self, results=None, error=None, processing_time=None) -> None:
        """Update metrics based on processing results"""
        current_time = datetime.now()
        hour_key = current_time.strftime('%Y-%m-%d %H:00')
        day_key = current_time.strftime('%Y-%m-%d')

        if processing_time is not None:
            self._update_processing_times(processing_time)

        if results:
            self._update_results_metrics(results, hour_key, day_key, processing_time)

        if error:
            self._metrics['error_count'] += 1

        self._metrics['current_processing_start'] = None

    def _update_processing_times(self, processing_time: float) -> None:
        """Update processing time statistics"""
        self._metrics['processing_times'].append(processing_time)
        self._metrics['last_process_time'] = processing_time
        
        self._processing_stats['min_time'] = min(
            self._processing_stats['min_time'], 
            processing_time
        )
        self._processing_stats['max_time'] = max(
            self._processing_stats['max_time'], 
            processing_time
        )
        self._processing_stats['total_time'] += processing_time
        self._processing_stats['count'] += 1
        
        if len(self._metrics['processing_times']) > self.MAX_HISTORY:
            self._metrics['processing_times'].pop(0)

    def _update_results_metrics(self, results: Dict, hour_key: str, 
                              day_key: str, processing_time: float) -> None:
        """Update metrics related to detection results"""
        self._metrics['processed_count'] += 1
        
        if 'predictions' in results:
            for pred in results['predictions']:
                defect_type = pred['class_name']
                self._metrics['defect_counts'][defect_type] = \
                    self._metrics['defect_counts'].get(defect_type, 0) + 1
        
        self._metrics['detection_history'].append({
            'timestamp': datetime.now(),
            'count': len(results.get('predictions', [])),
            'types': [p['class_name'] for p in results.get('predictions', [])],
            'processing_time': processing_time
        })
        
        if len(self._metrics['detection_history']) > self.MAX_HISTORY:
            self._metrics['detection_history'].pop(0)
            
        self._update_time_based_counts(hour_key, day_key, results, processing_time)

    def _update_time_based_counts(self, hour_key: str, day_key: str, 
                                results: Dict, processing_time: float) -> None:
        """Update hourly and daily statistics"""
        # Initialize hour stats if needed
        if hour_key not in self._metrics['hourly_counts']:
            self._metrics['hourly_counts'][hour_key] = {
                'total': 0,
                'defects': 0,
                'processing_times': [],
                'by_type': {}
            }
        
        # Initialize day stats if needed
        if day_key not in self._metrics['daily_counts']:
            self._metrics['daily_counts'][day_key] = {
                'total': 0,
                'defects': 0,
                'processing_times': [],
                'by_type': {}
            }
        
        # Update hourly stats
        hour_stats = self._metrics['hourly_counts'][hour_key]
        hour_stats['total'] += 1
        hour_stats['defects'] += len(results.get('predictions', []))
        if processing_time:
            hour_stats['processing_times'].append(processing_time)
        
        # Update daily stats
        day_stats = self._metrics['daily_counts'][day_key]
        day_stats['total'] += 1
        day_stats['defects'] += len(results.get('predictions', []))
        if processing_time:
            day_stats['processing_times'].append(processing_time)