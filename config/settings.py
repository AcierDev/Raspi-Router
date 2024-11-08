# config/settings.py
import os
from dotenv import load_dotenv

load_dotenv()

# Hardware Configuration
# ---------------------
# GPIO Pin Assignments
SOLENOID_PIN = 14
SENSOR_PIN = 20
NEW_SENSOR_PIN = 21
AI_TOGGLE_PIN = 16
EJECTION_PIN=15


# Timing Configuration
SENSOR2_WAIT_TIME = 0.5    # seconds

# Ensure environment variables are set
ROBOFLOW_API_KEY = os.getenv('ROBOFLOW_API_KEY')
ROBOFLOW_MODEL_ID = os.getenv('ROBOFLOW_MODEL_ID')

if not ROBOFLOW_API_KEY or not ROBOFLOW_MODEL_ID:
    raise ValueError(
        "Missing Roboflow credentials. Please set ROBOFLOW_API_KEY and "
        "ROBOFLOW_MODEL_ID environment variables."
    )


# Network Configuration
# -------------------
# Endpoints
IMAGE_URL = "http://192.168.1.164:1821"
INFERENCE_URL = "http://192.168.1.210:5000/detect-imperfection"

# Network Timing
NETWORK_CHECK_INTERVAL = 5  # seconds

# Network Timeouts (in seconds)
NETWORK_TIMEOUTS = {
    'connect': 10,    # Time to establish connection
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

# Ejection control settings
EJECTION_THRESHOLDS = {
    'confidence_min': 0.01,
    'area_max': 0.0001,
    'critical_count': 0,
    'major_count': 0,
    'total_defects': 1
}

SOLENOID_SETTINGS = {
    'DELAY_MS': 500,
    'START_DELAY_MS': 300,
    'EJECTION_TIME_MS': 500,
    'POST_EJECTION_DELAY_MS': 500
}