import os
import logging
import pdfminer
from flask import Flask, Blueprint, jsonify, request, render_template
from pathlib import Path
from dotenv import load_dotenv
from flask_migrate import Migrate

# Load .env file (always loaded before anything else)
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

# Set PDFMiner logging level to WARNING
pdfminer_logger = logging.getLogger("pdfminer")
pdfminer_logger.setLevel(logging.WARNING)

# Import configurations and database
from models import db, ClinicalTrial
from config import get_config

# Initialize logging with the loaded configuration
config_class = get_config()
logging.basicConfig(
    level=getattr(logging, config_class.LOG_LEVEL, "INFO"),
    format=config_class.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),  
        logging.FileHandler("logs/medmatchint.log")
    ]
)
logger = logging.getLogger(__name__)

# Import routes Blueprint
from app.api.routes import bp as api_bp

def create_app(config_class=None):
    logger.info("🔧 Creating MedMatchINT Application")
    
    app = Flask(
        __name__, 
        static_folder="static", 
        template_folder="templates"  # Ensure you have a templates/ directory with your HTML files
    )
    
    # Load configuration
    if config_class is None:
        config_class = get_config()
    
    app.config.from_object(config_class)
    
    # Set default UPLOAD_FOLDER if not specified
    upload_dir = app.config.get("UPLOAD_FOLDER", Path(__file__).resolve().parent.parent / "uploads")
    app.config["UPLOAD_FOLDER"] = str(upload_dir)
    
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
        logger.info(f"✅ Created upload directory: {upload_dir}")
    
    # Initialize extensions
    db.init_app(app)
    
    # Initialize Flask-Migrate (Database Migrations)
    migrate = Migrate(app, db)
    
    # Register API Blueprint without /api prefix
    app.register_blueprint(api_bp)
    
    # Serve your HTML interface on the root URL
    @app.route("/")
    def home():
        return render_template("index.html")  # Ensure you have templates/index.html

    # Middleware to clean all JSON responses (Automatic Response Cleaning)
    @app.after_request
    def clean_llm_response(response):
        if response.content_type == 'application/json':
            try:
                data = response.get_json()
                if isinstance(data, dict):
                    unwanted_keys = [
                        'context', 'total_duration', 
                        'prompt_eval_duration', 'eval_count', 
                        'eval_duration'
                    ]
                    for key in unwanted_keys:
                        data.pop(key, None)
                    response.data = jsonify(data).data
            except Exception as e:
                logger.error(f"Error during response cleaning: {str(e)}")
        return response

    # Ensure database schema is initialized (Now using Flask-Migrate)
    with app.app_context():
        logger.info("✅ Verifying database schema with migrations.")
        try:
            from flask_migrate import upgrade
            upgrade()  # Automatically apply migrations on start
            logger.info("✅ Database schema verified and upgraded successfully.")
        except Exception as e:
            logger.error(f"❌ Error during database migration: {str(e)}")
    
    logger.info("✅ MedMatchINT Application Initialized Successfully")
    return app
