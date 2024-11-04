# config/settings.py

# Hardware Configuration
# ---------------------
# GPIO Pin Assignments
SOLENOID_PIN = 14
SENSOR_PIN = 20
NEW_SENSOR_PIN = 21

# Timing Configuration
SENSOR2_WAIT_TIME = 0.5    # seconds


# Network Configuration
# -------------------
# Endpoints
IMAGE_URL = "http://192.168.1.164:1821"
INFERENCE_URL = "http://192.168.1.210:5000/detect-imperfection"

# Network Timing
NETWORK_CHECK_INTERVAL = 5  # seconds

# Network Timeouts (in seconds)
NETWORK_TIMEOUTS = {
    'connect': 5,    # Time to establish connection
    'read': 30,      # Time to receive data
}

# Transfer Settings
DOWNLOAD_CHUNK_SIZE = 8192  # bytes


# Display Configuration
# -------------------
# UI Update Settings
UI_REFRESH_RATE = 0.05     # seconds

# Logging Settings
MAX_LOG_MESSAGES = 15      # Maximum number of messages to store
VISIBLE_LOG_MESSAGES = 8   # Number of messages to show in UI

##############

MAX_RETRIES = 3          # Number of retry attempts
RETRY_DELAY = 0.5        # 500ms between retries
HEALTH_CHECK_INTERVAL = 5.0  

MAX_HISTORY = 10