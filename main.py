# main.py
import logging
from app import create_app
from config import LOG_LEVEL, LOG_FORMAT

# Ensure the logs/ directory exists
import os
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/medmatchint.log", mode="a", encoding="utf-8")
    ]
)

# Set root logger to capture all logs
logger = logging.getLogger()
logger.setLevel(logging.INFO)

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
