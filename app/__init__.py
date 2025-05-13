import os
import logging
import pdfminer
from flask import Flask, Blueprint
from pathlib import Path
from dotenv import load_dotenv

# Load .env file (always loaded before anything else)
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

# ✅ Impostazione variabili CUDA per sicurezza
os.environ['GGML_CUDA'] = 'yes'
os.environ['GGML_CUDA_FORCE_MMQ'] = 'yes'
os.environ['GGML_CUDA_FORCE_CUBLAS'] = 'yes'
os.environ['CUDA_HOME'] = '/usr/local/cuda-12.8'
os.environ['PATH'] = f"{os.environ['CUDA_HOME']}/bin:{os.environ.get('PATH', '')}"
os.environ['LD_LIBRARY_PATH'] = f"{os.environ['CUDA_HOME']}/lib64:{os.environ.get('LD_LIBRARY_PATH', '')}"

print("CUDA Configuration:")
print(f"GGML_CUDA: {os.environ.get('GGML_CUDA')}")
print(f"GGML_CUDA_FORCE_MMQ: {os.environ.get('GGML_CUDA_FORCE_MMQ')}")
print(f"GGML_CUDA_FORCE_CUBLAS: {os.environ.get('GGML_CUDA_FORCE_CUBLAS')}")


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

# Main Blueprint
bp = Blueprint("main", __name__)

# Import routes after the blueprint to avoid circular imports
from app import routes

def create_app(config_class=None):
    logger.info("🔧 Creating MedMatchINT Application")
    
    app = Flask(
        __name__, 
        static_folder="static", 
        template_folder="templates"
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
    
    # Register Blueprint
    app.register_blueprint(bp)
    
    # Ensure database schema is initialized
    with app.app_context():
        db.create_all()
        logger.info("✅ Database schema verified/created successfully.")
    
    logger.info("✅ MedMatchINT Application Initialized Successfully")
    return app
