from .settings import (
    # Hardware Configuration
    SOLENOID_PIN, SENSOR_PIN, NEW_SENSOR_PIN,
    
    # Timing Configuration
    SENSOR2_WAIT_TIME,
    
    # Network Configuration
    IMAGE_URL, INFERENCE_URL,
    NETWORK_CHECK_INTERVAL,
    NETWORK_TIMEOUTS,
    DOWNLOAD_CHUNK_SIZE,
    
    # Display Configuration
    UI_REFRESH_RATE,
    MAX_LOG_MESSAGES,
    VISIBLE_LOG_MESSAGES,
    
    # Other Configuration
    MAX_RETRIES,
    RETRY_DELAY,
    HEALTH_CHECK_INTERVAL,
    MAX_HISTORY
)