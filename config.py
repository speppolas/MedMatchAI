import os
import logging
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

# Server Configuration
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 5000))
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# LLM Configuration
LLAMA_CPP_PATH = os.getenv('LLAMA_CPP_PATH')
LLM_MODEL_PATH = os.getenv('LLM_MODEL_PATH')

# Database
SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI', 'sqlite:///instance/medmatchint.db')
SQLALCHEMY_TRACK_MODIFICATIONS = False

# In-memory processing only
MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

class Config:
    DEBUG = DEBUG
    TESTING = False
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev_secret_key_123')
    SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = SQLALCHEMY_TRACK_MODIFICATIONS
    UPLOAD_FOLDER = UPLOAD_FOLDER
    MAX_CONTENT_LENGTH = MAX_CONTENT_LENGTH

    LOG_FORMAT = LOG_FORMAT

# Sicurezza
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')

# Impostazioni per API esterne
    CLINICALTRIALS_API_BASE = os.getenv('CLINICALTRIALS_API_BASE', 'https://clinicaltrials.gov/api/v2')
    API_REQUEST_TIMEOUT = int(os.getenv('API_REQUEST_TIMEOUT', 30))  # secondi

# Impostazioni business logic
    INT_LOCATION_ID = os.getenv('INT_LOCATION_ID', 'Milano, Lombardy, Italy')
    MIN_KEYWORD_MATCH_SCORE = float(os.getenv('MIN_KEYWORD_MATCH_SCORE', 0.6))
    MAX_TRIALS_TO_EVALUATE = int(os.getenv('MAX_TRIALS_TO_EVALUATE', 20))

class ProductionConfig(Config):
    """Configurazione per l'ambiente di produzione."""
    DEBUG = False
    LOG_LEVEL = 'INFO'

class DevelopmentConfig(Config):
    """Configurazione per l'ambiente di sviluppo."""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'

class TestingConfig(Config):
    """Configurazione per l'ambiente di test."""
    TESTING = True
    DEBUG = True
    SECRET_KEY = "test_key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    LOG_LEVEL = 'DEBUG'

def get_config():
    """Restituisce la classe di configurazione attiva."""
    env = os.getenv("FLASK_ENV", "development").lower()

    if env == "production":
        return ProductionConfig
    elif env == "testing":
        return TestingConfig
    else:
        return DevelopmentConfig