# GPIO Configuration
SOLENOID_PIN = 14
SENSOR_PIN = 20
NEW_SENSOR_PIN = 21

# Network Configuration
IMAGE_URL = "http://192.168.1.164:1821"
INFERENCE_URL = "http://192.168.1.210:5000/detect-imperfection"

# Timing Configuration
NETWORK_CHECK_INTERVAL = 5  # seconds
SENSOR2_WAIT_TIME = 0.5    # seconds
UI_REFRESH_RATE = 0.05     # seconds

# Display Configuration
MAX_LOG_MESSAGES = 15
VISIBLE_LOG_MESSAGES = 8

# Network Timeouts (in seconds)
NETWORK_TIMEOUTS = {
    'connect': 5,    # Time to establish connection
    'read': 30,      # Time to receive data
}

# Chunk size for streaming downloads (in bytes)
DOWNLOAD_CHUNK_SIZE = 8192