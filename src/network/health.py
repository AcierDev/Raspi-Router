# src/network/health.py
import subprocess
import socket
from datetime import datetime
from typing import Tuple, Optional
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def ping_host(host: str) -> Tuple[bool, Optional[float]]:
    """
    Check if host responds to ping using system ping command.
    
    Args:
        host: The hostname or IP to ping
        
    Returns:
        Tuple of (success boolean, ping time in ms if successful)
    """
    try:
        logger.debug(f"Executing ping command for host: {host}")
        result = subprocess.run(
            ['ping', '-c', '1', '-W', '1', host],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        logger.debug(f"Ping return code: {result.returncode}")
        logger.debug(f"Ping stdout: {result.stdout}")
        logger.debug(f"Ping stderr: {result.stderr}")
        
        if result.returncode == 0:
            output = result.stdout
            if 'time=' in output:
                try:
                    time_str = output.split('time=')[1].split()[0].replace('ms', '')
                    ping_time = float(time_str)
                    logger.debug(f"Successful ping with time: {ping_time}ms")
                    return True, ping_time
                except Exception as e:
                    logger.error(f"Error parsing ping time: {e}")
                    return True, None
            logger.debug("Successful ping but no time found in output")
            return True, None
            
        logger.warning(f"Ping failed with return code {result.returncode}")
        return False, None
    except Exception as e:
        logger.error(f"Error executing ping command: {type(e).__name__}: {str(e)}")
        logger.exception("Full traceback:")
        return False, None

def check_internet(timeout: int = 2) -> bool:
    """
    Check internet connectivity using Google DNS.
    
    Args:
        timeout: Connection timeout in seconds
        
    Returns:
        bool indicating if internet is accessible
    """
    try:
        logger.debug("Checking internet connectivity")
        socket.create_connection(("8.8.8.8", 53), timeout=timeout)
        logger.debug("Internet connection successful")
        return True
    except OSError as e:
        logger.error(f"Internet check error: {e}")
        return False