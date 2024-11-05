# config/__init__.py
from .settings import *

__all__ = [
    # Hardware
    'SOLENOID_PIN',
    'SENSOR_PIN',
    'NEW_SENSOR_PIN',
    'SENSOR2_WAIT_TIME',
    # Network
    'IMAGE_URL',
    'INFERENCE_URL',
    'NETWORK_CHECK_INTERVAL',
    'NETWORK_TIMEOUTS',
    'DOWNLOAD_CHUNK_SIZE',
    # Display
    'UI_REFRESH_RATE',
    'MAX_LOG_MESSAGES',
    'VISIBLE_LOG_MESSAGES',
    'AI_TOGGLE_PIN'
]