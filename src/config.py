# GPIO Configuration
SOLENOID_PIN = 14
SENSOR_PIN = 20
NEW_SENSOR_PIN = 21

# Network Configuration
IMAGE_URL = "http://192.168.1.164:1821"
INFERENCE_URL = "http://192.168.1.210:5000/detect-imperfection"
DNS_SERVERS = ['8.8.8.8', '1.1.1.1', '8.8.4.4']  # Missing from original

# Timing Configuration
NETWORK_CHECK_INTERVAL = 5  # seconds
SENSOR2_WAIT_TIME = 0.5    # seconds
UI_REFRESH_RATE = 0.05     # seconds
IMAGE_CAPTURE_TIMEOUT = 30  # seconds
ANALYSIS_TIMEOUT = 30      # seconds

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

# Cache Configuration
IMAGE_CACHE_SIZE_MB = 100
IMAGE_CACHE_MAX_AGE = 3600  # seconds

# AI Analysis Configuration
MIN_CONFIDENCE_THRESHOLD = 0.5

# Logging Configuration
LOG_LEVEL = "DEBUG"
LOG_FILE = "inspection_system.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Error Handling Configuration
MAX_RETRY_ATTEMPTS = 2
RETRY_DELAY = 0.5  # seconds
ERROR_RECOVERY_DELAY = 2  # seconds

# UI Configuration
FRAMEBUFFER_DEVICE = '/dev/fb0'
UI_FONT_SIZE = 14
UI_TITLE = "Automated Inspection System"
UI_COLORS = {
    'normal': (255, 255, 255),
    'alert': (255, 0, 0),
    'success': (0, 255, 0),
    'info': (0, 255, 255),
    'background': (0, 0, 0)
}