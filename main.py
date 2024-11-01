from flask import Flask, request, jsonify
import os
import logging
from datetime import datetime
import threading
from werkzeug.utils import secure_filename
from pathlib import Path
import time
import atexit
import signal

# Local imports
from inferences.model import process_image
from config import UPLOAD_FOLDER, ALLOWED_EXTENSIONS
from status_monitor import StatusMonitor
from prediction_logger import prediction_logger

# Initialize Flask app
app = Flask(__name__)

# Initialize components
status_monitor = StatusMonitor()

# Ensure the upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Configure logging
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    filename=str(log_dir / 'app.log'),
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def allowed_file(filename):
    """Check if the file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def cleanup():
    """Cleanup function for graceful shutdown"""
    logger.info("Performing cleanup...")
    status_monitor.stop()

def cleanup_old_files():
    """Clean up old files in the upload directory"""
    try:
        current_time = datetime.now()
        for file_path in Path(UPLOAD_FOLDER).glob('*'):
            if file_path.is_file():
                file_age = current_time - datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_age.total_seconds() > 3600:  # Remove files older than 1 hour
                    file_path.unlink()
                    logger.info(f"Cleaned up old file: {file_path}")
    except Exception as e:
        logger.error(f"Error cleaning up old files: {str(e)}")

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/stats', methods=['GET'])
def get_stats():
    """Endpoint to get recent prediction statistics"""
    try:
        stats = prediction_logger.get_recent_stats()
        return jsonify({
            "success": True,
            "stats": stats,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Failed to retrieve statistics"
        }), 500

@app.route('/detect-imperfection', methods=['POST'])
def detect_imperfection():
    """Main endpoint for wood imperfection detection"""
    start_time = time.time()
    
    # Validate request
    if 'image' not in request.files:
        status_monitor.update_status("Request received with no image", "error")
        logger.warning("No image part in the request")
        return jsonify({
            "success": False,
            "error": "No image part"
        }), 400

    file = request.files['image']
    
    if file.filename == '':
        status_monitor.update_status("Empty file received", "error")
        logger.warning("No file selected for uploading")
        return jsonify({
            "success": False,
            "error": "No selected file"
        }), 400
    
    if file and allowed_file(file.filename):
        try:
            # Generate secure filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            secure_fname = secure_filename(file.filename)
            filename = f"{timestamp}_{secure_fname}"
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            
            # Save the file
            file.save(file_path)
            status_monitor.update_status(f"Saved file: {filename}", "info")
            logger.info(f"File saved at {file_path}")
            
            try:
                # Process the image
                status_monitor.update_status(f"Processing {filename}...", "info")
                result = process_image(file_path)
                
                # Calculate processing time
                processing_time = time.time() - start_time
                
                # Log prediction results
                prediction_logger.log_prediction(result, filename, processing_time)
                
                # Schedule file cleanup
                def cleanup_file():
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            logger.info(f"Cleaned up file: {file_path}")
                    except Exception as e:
                        logger.error(f"Failed to cleanup file {file_path}: {str(e)}")
                
                threading.Timer(3600, cleanup_file).start()
                
                # Update status and return results
                num_predictions = len(result.get('predictions', []))
                status_monitor.update_status(
                    f"Successfully processed {filename} - Found {num_predictions} imperfections",
                    "success"
                )
                
                return jsonify({
                    "success": True,
                    "data": result,
                    "processing_time": processing_time,
                    "timestamp": datetime.now().isoformat()
                }), 200
                
            except Exception as e:
                error_msg = f"Error processing {filename}: {str(e)}"
                status_monitor.update_status(error_msg, "error")
                logger.error(error_msg, exc_info=True)
                
                # Attempt to clean up failed file
                try:
                    os.remove(file_path)
                except Exception:
                    pass
                    
                return jsonify({
                    "success": False,
                    "error": "Failed to process image",
                    "detail": str(e)
                }), 500
                
        except Exception as e:
            error_msg = f"Error handling file upload: {str(e)}"
            status_monitor.update_status(error_msg, "error")
            logger.error(error_msg, exc_info=True)
            return jsonify({
                "success": False,
                "error": "Failed to handle file upload",
                "detail": str(e)
            }), 500
    else:
        status_monitor.update_status(f"Rejected invalid file: {file.filename}", "warning")
        logger.warning(f"File {file.filename} is not allowed")
        return jsonify({
            "success": False,
            "error": "Invalid file type",
            "allowed_extensions": list(ALLOWED_EXTENSIONS)
        }), 400

def start_cleanup_scheduler():
    """Start the periodic cleanup of old files"""
    def cleanup_schedule():
        while True:
            cleanup_old_files()
            threading.Event().wait(3600)  # Run every hour
    
    cleanup_thread = threading.Thread(target=cleanup_schedule, daemon=True)
    cleanup_thread.start()

def handle_shutdown(signum, frame):
    """Handler for shutdown signals"""
    logger.info(f"Received shutdown signal {signum}")
    cleanup()
    # Raise KeyboardInterrupt to stop the Flask server
    raise KeyboardInterrupt

if __name__ == '__main__':
    try:
        # Register signal handlers
        signal.signal(signal.SIGTERM, handle_shutdown)
        signal.signal(signal.SIGINT, handle_shutdown)
        
        # Register cleanup on normal exit
        atexit.register(cleanup)
        
        # Start the status monitor
        logger.info("Starting status monitor...")
        status_monitor.start()
        
        # Start cleanup scheduler
        logger.info("Starting cleanup scheduler...")
        start_cleanup_scheduler()
        
        # Log startup
        logger.info("Starting Flask application...")
        logger.info(f"Upload folder: {UPLOAD_FOLDER}")
        logger.info(f"Allowed extensions: {ALLOWED_EXTENSIONS}")
        
        # Run the Flask app
        app.run(host='0.0.0.0', port=5000)
        
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}", exc_info=True)
        raise
    finally:
        cleanup()