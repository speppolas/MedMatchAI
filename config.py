import os
import logging
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

# Configurazione Server
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 5000))
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')

# LLM Configuration
LLM_MODEL_PATH = os.getenv('LLM_MODEL_PATH', './models/llama-2-7b-chat.Q4_K_M.gguf')
LLM_SERVER_PORT = int(os.getenv('LLM_SERVER_PORT', 8080))
LLM_CONTEXT_SIZE = int(os.getenv('LLM_CONTEXT_SIZE', 2048))
LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', 0.7))
LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', 512))

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Database
SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI', 'sqlite:///instance/medmatchint.db')
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Upload
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', str(BASE_DIR / 'uploads'))
MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))

# Sicurezza
SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev_secret_key_123')
CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')

# Impostazioni per API esterne
CLINICALTRIALS_API_BASE = os.getenv('CLINICALTRIALS_API_BASE', 'https://clinicaltrials.gov/api/v2')
API_REQUEST_TIMEOUT = int(os.getenv('API_REQUEST_TIMEOUT', 30))  # secondi

# Impostazioni business logic
INT_LOCATION_ID = os.getenv('INT_LOCATION_ID', 'Milano, Lombardy, Italy')
MIN_KEYWORD_MATCH_SCORE = float(os.getenv('MIN_KEYWORD_MATCH_SCORE', 0.6))
MAX_TRIALS_TO_EVALUATE = int(os.getenv('MAX_TRIALS_TO_EVALUATE', 20))

class Config:
    """Classe base di configurazione."""
    DEBUG = False
    TESTING = False
    SECRET_KEY = SECRET_KEY
    SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = SQLALCHEMY_TRACK_MODIFICATIONS
    UPLOAD_FOLDER = UPLOAD_FOLDER
    MAX_CONTENT_LENGTH = MAX_CONTENT_LENGTH
    LOG_FORMAT = LOG_FORMAT

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