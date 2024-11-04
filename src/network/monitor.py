# src/network/monitor.py
import asyncio
from datetime import datetime
from typing import Optional, Dict, Callable, Any
import logging
from urllib.parse import urlparse

from .status import ServiceStatus
from .health import ping_host, check_internet
from .utils import format_time_ago, parse_service_url

logger = logging.getLogger(__name__)

class NetworkMonitor:
    def __init__(self, status_callback: Optional[Callable] = None):
        self.status: Dict[str, ServiceStatus] = {
            'internet': ServiceStatus(additional_info={'check_count': 0}),
            'camera': ServiceStatus(additional_info={'failed_requests': 0}),
            'ai_server': ServiceStatus(additional_info={'failed_requests': 0})
        }
        self._status_callback = status_callback
        self._is_running = False
        self._monitoring_task = None
        logger.info("NetworkMonitor initialized")
        print('FOO')

    async def __aenter__(self):
        """Async context manager entry"""
        logger.info("Entering NetworkMonitor context")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        logger.info("Exiting NetworkMonitor context")
        self.stop_monitoring()
        if self._monitoring_task:
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

    async def _notify_status_update(self):
        """Notify status callback if configured"""
        if self._status_callback:
            try:
                if asyncio.iscoroutinefunction(self._status_callback):
                    await self._status_callback(self.status)
                else:
                    self._status_callback(self.status)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")

    async def check_internet(self) -> bool:
        """Check internet connectivity"""
        logger.info("Checking internet connectivity")
        status = self.status['internet']
        status.last_check = datetime.now()
        status.additional_info['check_count'] += 1

        if check_internet():
            logger.info("Internet check successful")
            status.update(
                status='Connected',
                last_success=datetime.now(),
                error_count=0
            )
            return True

        logger.info("Internet check failed")
        status.update(
            status='Disconnected',
            error_count=status.error_count + 1
        )
        return False

    async def check_service_health(self, url: str, service: str):
        """Check service connectivity using ping"""
        logger.info(f"Checking {service} health for URL: {url}")
        status = self.status[service]
        status.last_check = datetime.now()

        try:
            # Parse URL directly without using parse_service_url
            parsed = urlparse(url)
            hostname = parsed.hostname or parsed.path
            logger.info(f"Parsed hostname for {service}: {hostname}")
            
            if not hostname:
                logger.error(f"Invalid URL for {service}: {url}")
                status.update(
                    status='Invalid URL',
                    error_count=status.error_count + 1
                )
                return

            status.ip = hostname
            logger.info(f"Attempting to ping {hostname} for {service}")
            is_pingable, ping_time = ping_host(hostname)
            logger.info(f"Ping result for {service}: pingable={is_pingable}, time={ping_time}")

            if is_pingable:
                logger.info(f"{service} is reachable with ping time {ping_time}ms")
                status.update(
                    status='Connected',
                    last_success=datetime.now(),
                    ping_time=ping_time,
                    error_count=0
                )
                status.additional_info['failed_requests'] = 0
            else:
                logger.warning(f"{service} is not reachable")
                status.update(
                    status='Disconnected',
                    ping_time=None,
                    error_count=status.error_count + 1
                )
                status.additional_info['failed_requests'] += 1

        except Exception as e:
            logger.error(f"Error checking {service} health: {type(e).__name__}: {str(e)}")
            logger.exception("Full traceback:")
            status.update(
                status='Disconnected',
                error_count=status.error_count + 1
            )
            status.additional_info['failed_requests'] += 1

    async def check_all_services(self, camera_url: str, ai_server_url: str):
        """Check all services concurrently"""
        try:
            logger.info("Starting service checks")
            logger.info(f"Camera URL: {camera_url}")
            logger.info(f"AI Server URL: {ai_server_url}")
            
            await asyncio.gather(
                self.check_internet(),
                self.check_service_health(camera_url, 'camera'),
                self.check_service_health(ai_server_url, 'ai_server')
            )
            
            logger.info("Service check results:")
            for service, status in self.status.items():
                logger.info(f"{service}: status={status.status}, ping_time={status.ping_time}")
            
            await self._notify_status_update()
                
        except Exception as e:
            logger.error(f"Error during service checks: {e}")
            logger.exception("Full traceback:")

    async def start_monitoring(self, camera_url: str, ai_server_url: str, interval: float = 30):
        """Start continuous monitoring of all services"""
        if self._is_running:
            logger.info("Monitoring already running")
            return

        logger.info("Starting network monitoring")
        logger.info(f"Monitor interval: {interval} seconds")
        self._is_running = True
        
        while self._is_running:
            try:
                await self.check_all_services(camera_url, ai_server_url)
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)  # Shorter interval on error

    def stop_monitoring(self):
        """Stop the continuous monitoring"""
        logger.info("Stopping network monitoring")
        self._is_running = False

    def get_service_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get a summary of all service statuses"""
        return {
            name: {
                'status': service.status,
                'last_check': format_time_ago(service.last_check),
                'last_success': format_time_ago(service.last_success),
                'ping_time': f"{service.ping_time:.1f}ms" if service.ping_time else None,
                'error_count': service.error_count,
                'ip': service.ip,
                **service.additional_info
            }
            for name, service in self.status.items()
        }