import os
import logging
from app import create_app, socketio  # ✅ Import socketio from app (Socket.IO instance)
from config import LOG_LEVEL, LOG_FORMAT, HOST, PORT

# Enhanced Logging Configuration with File Handler (Rotating)
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)  # Ensure logs directory exists
log_file = os.path.join(log_dir, "medmatchint.log")

# Configure Logging with Console and File Handlers
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, "INFO"),
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),              # Console Logging
        logging.FileHandler(log_file, mode="a")  # Log file (auto-created)
    ]
)

logger = logging.getLogger(__name__)

# Create the Flask application
app = create_app()

if __name__ == '__main__':
    logger.info("🚀 Starting MedMatchINT Application with Socket.IO...")
    
    # ✅ Run the application with Socket.IO (this replaces app.run)
    socketio.run(app, host=HOST, port=PORT, debug=True)
