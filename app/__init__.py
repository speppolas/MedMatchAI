import os
import logging
from flask import Flask

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create the Flask application
app = Flask(__name__, 
            static_folder="../static", 
            template_folder="../templates")

# Set the secret key
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")

# Import routes after app is created to avoid circular imports
from app import routes
