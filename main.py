import os
import logging
from app import create_app
from config import LOG_LEVEL, LOG_FORMAT, HOST, PORT

# Configure Logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, "INFO"),
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/medmatchint.log", mode="a")
    ]
)

logger = logging.getLogger(__name__)

# Create Flask application
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)