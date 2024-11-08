import json
from datetime import datetime
from typing import Dict, Any, Optional

class StateManager:
    @staticmethod
    def save_state(metrics: Dict[str, Any], last_error: Optional[str] = None) -> None:
        try:
            end_time = datetime.now()
            start_time = metrics.get('start_time', end_time)
            run_time = (end_time - start_time).total_seconds()
            
            final_state = {
                'metrics': {
                    'processed_count': metrics.get('processed_count', 0),
                    'error_count': metrics.get('error_count', 0),
                    'total_errors': metrics.get('total_errors', 0),
                    'run_time_seconds': run_time,
                    'average_process_time': metrics.get('last_process_time', 0),
                },
                'last_run': end_time.isoformat(),
                'last_error': last_error
            }
            
            with open('system_state.json', 'w') as f:
                json.dump(final_state, f, indent=2)
                
        except Exception as e:
            print(f"Failed to save system state: {e}")