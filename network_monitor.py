import socket
import requests
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse
import subprocess

class NetworkStatus:
    def __init__(self):
        self.status = {
            'internet': {
                'status': 'Unknown',
                'last_check': None,
                'last_success': None
            },
            'camera': {
                'status': 'Unknown',
                'last_check': None,
                'last_success': None,
                'ping_time': None,
                'ip': None
            },
            'ai_server': {
                'status': 'Unknown',
                'last_check': None,
                'last_success': None,
                'ping_time': None,
                'ip': None
            }
        }

    def ping_host(self, host):
        """Check if host responds to ping"""
        try:
            # Use ping with 1 packet and 1 second timeout
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '1', host],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True  # Use text output instead of bytes
            )
            
            if result.returncode == 0:
                # Extract ping time if available
                output = result.stdout
                if 'time=' in output:
                    try:
                        time_str = output.split('time=')[1].split()[0].replace('ms', '')
                        return True, float(time_str)
                    except:
                        return True, None
                return True, None
            return False, None
        except Exception as e:
            print(f"Ping error: {e}")
            return False, None

    def check_internet(self, timeout=2):
        """Check internet connectivity using Google DNS"""
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=timeout)
            self.status['internet']['status'] = 'Connected'
            self.status['internet']['last_success'] = datetime.now()
            return True
        except OSError as e:
            print(f"Internet check error: {e}")
            self.status['internet']['status'] = 'Disconnected'
            return False
        finally:
            self.status['internet']['last_check'] = datetime.now()

    def extract_ip_from_url(self, url):
        """Extract IP address or hostname from URL"""
        try:
            parsed = urlparse(url)
            return parsed.hostname
        except Exception as e:
            print(f"URL parsing error: {e}")
            return None

    def check_camera(self, url):
        """Check camera connectivity using simple ping"""
        host = self.extract_ip_from_url(url)
        if not host:
            self.status['camera']['status'] = 'Invalid URL'
            self.status['camera']['last_check'] = datetime.now()
            return False

        self.status['camera']['ip'] = host
        is_pingable, ping_time = self.ping_host(host)
        
        if is_pingable:
            self.status['camera']['status'] = 'Connected'
            self.status['camera']['ping_time'] = f"{ping_time:.1f}ms" if ping_time else "Unknown"
            self.status['camera']['last_success'] = datetime.now()
            return True
        else:
            self.status['camera']['status'] = 'Disconnected'
            self.status['camera']['ping_time'] = None
            return False
        
        self.status['camera']['last_check'] = datetime.now()

    def check_ai_server(self, url):
        """Check AI server connectivity using simple ping"""
        host = self.extract_ip_from_url(url)
        if not host:
            self.status['ai_server']['status'] = 'Invalid URL'
            self.status['ai_server']['last_check'] = datetime.now()
            return False

        self.status['ai_server']['ip'] = host
        is_pingable, ping_time = self.ping_host(host)
        
        if is_pingable:
            self.status['ai_server']['status'] = 'Connected'
            self.status['ai_server']['ping_time'] = f"{ping_time:.1f}ms" if ping_time else "Unknown"
            self.status['ai_server']['last_success'] = datetime.now()
            return True
        else:
            self.status['ai_server']['status'] = 'Disconnected'
            self.status['ai_server']['ping_time'] = None
            return False
        
        self.status['ai_server']['last_check'] = datetime.now()

    def format_last_success(self, last_success):
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