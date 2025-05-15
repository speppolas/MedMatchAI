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
LLM_CONTEXT_SIZE = int(os.getenv('LLM_CONTEXT_SIZE', 8192))
# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# LLM Configuration
OLLAMA_SERVER_URL = os.getenv('OLLAMA_SERVER_URL')

# Database
# Database Configuration
SQLALCHEMY_DATABASE_URI = os.getenv(
    'SQLALCHEMY_DATABASE_URI', 
    'postgresql://postgres:your_secure_password@localhost/medmatchint'
)
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
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')

class ProductionConfig(Config):
    DEBUG = False
    LOG_LEVEL = 'INFO'

class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'

class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SECRET_KEY = "test_key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    LOG_LEVEL = 'DEBUG'

def get_config():
    env = os.getenv("FLASK_ENV", "development").lower()

    if env == "production":
        return ProductionConfig
    elif env == "testing":
        return TestingConfig
    else:
        return DevelopmentConfig
