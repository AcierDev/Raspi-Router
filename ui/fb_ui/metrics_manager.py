# ui/fb_ui/metrics_manager.py
from datetime import datetime, timedelta
import time

class MetricsManager:
    def __init__(self):
        # Protected metrics dictionary
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

    @property
    def metrics(self):
        """Public access to metrics dictionary"""
        return self._metrics

    @property
    def processing_stats(self):
        """Public access to processing stats dictionary"""
        return self._processing_stats

    def _update_processing_stats(self, processing_time):
        """Update processing time statistics"""
        self._metrics['processing_times'].append(processing_time)
        self._metrics['last_process_time'] = processing_time
        
        self._processing_stats['min_time'] = min(self._processing_stats['min_time'], processing_time)
        self._processing_stats['max_time'] = max(self._processing_stats['max_time'], processing_time)
        self._processing_stats['total_time'] += processing_time
        self._processing_stats['count'] += 1
        
        if len(self._metrics['processing_times']) > self.MAX_HISTORY:
            self._metrics['processing_times'].pop(0)

    def _update_results_stats(self, results, current_time, processing_time):
        """Update processing results statistics"""
        self._metrics['processed_count'] += 1
        
        if 'predictions' in results:
            for pred in results['predictions']:
                defect_type = pred['class_name']
                self._metrics['defect_counts'][defect_type] = \
                    self._metrics['defect_counts'].get(defect_type, 0) + 1
        
        self._metrics['detection_history'].append({
            'timestamp': current_time,
            'count': len(results.get('predictions', [])),
            'types': [p['class_name'] for p in results.get('predictions', [])],
            'processing_time': processing_time
        })
        
        if len(self._metrics['detection_history']) > self.MAX_HISTORY:
            self._metrics['detection_history'].pop(0)

    def _update_time_based_stats(self, hour_key, day_key, results, processing_time):
        """Update time-based statistics"""
        for period_key, period_stats in [
            (hour_key, self._metrics['hourly_counts']),
            (day_key, self._metrics['daily_counts'])
        ]:
            if period_key not in period_stats:
                period_stats[period_key] = {
                    'total': 0,
                    'defects': 0,
                    'processing_times': [],
                    'by_type': {}
                }
            
            stats = period_stats[period_key]
            stats['total'] += 1
            stats['defects'] += len(results.get('predictions', []))
            if processing_time:
                stats['processing_times'].append(processing_time)

    def update_metrics(self, results=None, error=None, processing_time=None):
        """Update system metrics based on processing results"""
        current_time = datetime.now()
        hour_key = current_time.strftime('%Y-%m-%d %H:00')
        day_key = current_time.strftime('%Y-%m-%d')
        
        if processing_time is None and self._metrics['current_processing_start'] is not None:
            processing_time = time.time() - self._metrics['current_processing_start']
        
        if processing_time is not None:
            self._update_processing_stats(processing_time)
        
        if results:
            self._update_results_stats(results, current_time, processing_time)
            self._update_time_based_stats(hour_key, day_key, results, processing_time)
        
        if error:
            self._metrics['error_count'] += 1
        
        self._metrics['current_processing_start'] = None