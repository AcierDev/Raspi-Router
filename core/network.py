# core/network.py

import socket
import requests
from datetime import datetime, timedelta
from urllib.parse import urlparse
import subprocess
from typing import Optional, Dict, Any, Callable
from config import (
    NETWORK_TIMEOUTS, 
    IMAGE_URL, 
    INFERENCE_URL,
    HEALTH_CHECK_INTERVAL
)

class NetworkManager:
    def __init__(self, health_check_callback: Optional[Callable] = None):
        self.health_check_callback = health_check_callback
        self.status = {
            'internet': {
                'status': 'Unknown',
                'last_check': None,
                'last_success': None,
                'error_count': 0
            },
            'camera': {
                'status': 'Unknown',
                'last_check': None,
                'last_success': None,
                'ping_time': None,
                'ip': None,
                'error_count': 0
            },
            'ai_server': {
                'status': 'Unknown',
                'last_check': None,
                'last_success': None,
                'ping_time': None,
                'ip': None,
                'error_count': 0
            }
        }
        
        # Connection history
        self.connection_history = []
        self.MAX_HISTORY = 100
        
        # Initialize IPs
        self._init_endpoints()

    def _init_endpoints(self):
        """Initialize endpoint information"""
        try:
            # Extract camera IP
            camera_host = self.extract_ip_from_url(IMAGE_URL)
            if camera_host:
                self.status['camera']['ip'] = camera_host
            
            # Extract AI server IP
            ai_host = self.extract_ip_from_url(INFERENCE_URL)
            if ai_host:
                self.status['ai_server']['ip'] = ai_host
                
        except Exception as e:
            print(f"Error initializing endpoints: {e}")

    def ping_host(self, host: str) -> tuple[bool, Optional[float]]:
        """Check if host responds to ping"""
        try:
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '1', host],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            if result.returncode == 0:
                if 'time=' in result.stdout:
                    try:
                        time_str = result.stdout.split('time=')[1].split()[0].replace('ms', '')
                        return True, float(time_str)
                    except:
                        return True, None
                return True, None
            return False, None
            
        except Exception as e:
            print(f"Ping error: {e}")
            return False, None

    def check_internet(self) -> bool:
        """Check internet connectivity using Google DNS"""
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=NETWORK_TIMEOUTS['connect'])
            self.status['internet']['status'] = 'Connected'
            self.status['internet']['last_success'] = datetime.now()
            self.status['internet']['error_count'] = 0
            return True
            
        except OSError as e:
            print(f"Internet check error: {e}")
            self.status['internet']['status'] = 'Disconnected'
            self.status['internet']['error_count'] += 1
            return False
            
        finally:
            self.status['internet']['last_check'] = datetime.now()
            self._update_history('internet')
            self._notify_health_check()

    def check_camera(self) -> bool:
        """Check camera connectivity"""
        result = self._check_endpoint('camera', IMAGE_URL)
        self._notify_health_check()
        return result

    def check_ai_server(self) -> bool:
        """Check AI server connectivity"""
        result = self._check_endpoint('ai_server', INFERENCE_URL)
        self._notify_health_check()
        return result

    def _check_endpoint(self, endpoint: str, url: str) -> bool:
        """Generic endpoint checking logic"""
        host = self.extract_ip_from_url(url)
        if not host:
            self.status[endpoint]['status'] = 'Invalid URL'
            self.status[endpoint]['last_check'] = datetime.now()
            self.status[endpoint]['error_count'] += 1
            return False

        self.status[endpoint]['ip'] = host
        is_pingable, ping_time = self.ping_host(host)
        
        if is_pingable:
            self.status[endpoint]['status'] = 'Connected'
            self.status[endpoint]['ping_time'] = f"{ping_time:.1f}ms" if ping_time else "Unknown"
            self.status[endpoint]['last_success'] = datetime.now()
            self.status[endpoint]['error_count'] = 0
            return True
        else:
            self.status[endpoint]['status'] = 'Disconnected'
            self.status[endpoint]['ping_time'] = None
            self.status[endpoint]['error_count'] += 1
            return False
        
        self._update_history(endpoint)

    def _update_history(self, endpoint: str):
        """Update connection history"""
        current_status = self.status[endpoint].copy()
        current_status['timestamp'] = datetime.now()
        
        self.connection_history.append({
            'endpoint': endpoint,
            'status': current_status
        })
        
        # Trim history if needed
        while len(self.connection_history) > self.MAX_HISTORY:
            self.connection_history.pop(0)

    def _notify_health_check(self):
        """Notify health check callback if available"""
        if self.health_check_callback:
            self.health_check_callback(self.status)

    def extract_ip_from_url(self, url: str) -> Optional[str]:
        """Extract IP address or hostname from URL"""
        try:
            parsed = urlparse(url)
            return parsed.hostname
        except Exception as e:
            print(f"URL parsing error: {e}")
            return None

    def format_last_success(self, last_success: Optional[datetime]) -> str:
        """Format the last successful connection time"""
        if not last_success:
            return "Never"
        
        delta = datetime.now() - last_success
        if delta < timedelta(minutes=1):
            return f"{delta.seconds}s ago"
        elif delta < timedelta(hours=1):
            return f"{delta.seconds//60}m ago"
        else:
            return f"{delta.seconds//3600}h ago"

    def check_all(self) -> Dict[str, Any]:
        """Check all network connections"""
        self.check_internet()
        self.check_camera()
        self.check_ai_server()
        return self.status

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        stats = {}
        for endpoint in ['internet', 'camera', 'ai_server']:
            endpoint_stats = {
                'uptime': self._calculate_uptime(endpoint),
                'error_rate': self._calculate_error_rate(endpoint),
                'average_ping': self._calculate_average_ping(endpoint)
            }
            stats[endpoint] = endpoint_stats
        return stats

    def _calculate_uptime(self, endpoint: str) -> float:
        """Calculate uptime percentage for endpoint"""
        history = [h for h in self.connection_history 
                  if h['endpoint'] == endpoint]
        if not history:
            return 0.0
        
        connected_count = sum(
            1 for h in history 
            if h['status']['status'] == 'Connected'
        )
        return (connected_count / len(history)) * 100

    def _calculate_error_rate(self, endpoint: str) -> float:
        """Calculate error rate for endpoint"""
        history = [h for h in self.connection_history 
                  if h['endpoint'] == endpoint]
        if not history:
            return 0.0
        
        error_count = sum(h['status']['error_count'] for h in history)
        return (error_count / len(history)) if history else 0.0

    def _calculate_average_ping(self, endpoint: str) -> Optional[float]:
        """Calculate average ping time for endpoint"""
        history = [h for h in self.connection_history 
                  if h['endpoint'] == endpoint 
                  and h['status'].get('ping_time')]
        if not history:
            return None
        
        ping_times = []
        for h in history:
            try:
                ping_str = h['status']['ping_time']
                if ping_str and 'ms' in ping_str:
                    ping_times.append(float(ping_str.replace('ms', '')))
            except:
                continue
        
        return sum(ping_times) / len(ping_times) if ping_times else None