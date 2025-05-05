"""
Configurazione centralizzata per l'applicazione MedMatchINT.

Questo modulo gestisce la configurazione dell'applicazione, caricando valori
dalle variabili d'ambiente con fallback a valori predefiniti sicuri.
"""

import os
import logging
from pathlib import Path

# Directory di base del progetto
BASE_DIR = Path(__file__).resolve().parent

# Configurazione dell'applicazione
APP_NAME = os.environ.get('APP_NAME', 'MedMatchINT')
APP_DESCRIPTION = os.environ.get('APP_DESCRIPTION', 'Matching di trial clinici oncologici per l\'Istituto Nazionale dei Tumori')
VERSION = os.environ.get('VERSION', '1.1.0')

# Configurazione del server
HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', 5000))
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't', 'yes')

# Configurazione del database
DATABASE_URL = os.environ.get('DATABASE_URL')
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Gestione dei file
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))  # 10 MB predefinito

# Sicurezza
SECRET_KEY = os.environ.get('SESSION_SECRET', 'dev_key_please_change')
CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')

# Configurazione LLM
LLAMA_CPP_PATH = os.environ.get('LLAMA_CPP_PATH', '')
LLM_MODEL_PATH = os.environ.get('LLM_MODEL_PATH', '')
LLM_CONTEXT_SIZE = int(os.environ.get('LLM_CONTEXT_SIZE', 4096))
LLM_TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', 0.7))
LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', 2048))
LLM_TIMEOUT = int(os.environ.get('LLM_TIMEOUT', 60))  # timeout in secondi
LLM_EXTRA_PARAMS = os.environ.get('LLM_EXTRA_PARAMS', '')

# Configurazione logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG')
LOG_FORMAT = os.environ.get('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Impostazioni per API esterne
CLINICALTRIALS_API_BASE = os.environ.get('CLINICALTRIALS_API_BASE', 'https://clinicaltrials.gov/api/v2')
API_REQUEST_TIMEOUT = int(os.environ.get('API_REQUEST_TIMEOUT', 30))  # secondi

# Impostazioni business logic
INT_LOCATION_ID = os.environ.get('INT_LOCATION_ID', 'Milano, Lombardy, Italy')
MIN_KEYWORD_MATCH_SCORE = float(os.environ.get('MIN_KEYWORD_MATCH_SCORE', 0.6))
MAX_TRIALS_TO_EVALUATE = int(os.environ.get('MAX_TRIALS_TO_EVALUATE', 20))

class Config:
    """Classe base di configurazione."""
    DEBUG = False
    TESTING = False
    SECRET_KEY = SECRET_KEY
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = SQLALCHEMY_TRACK_MODIFICATIONS
    SQLALCHEMY_ENGINE_OPTIONS = SQLALCHEMY_ENGINE_OPTIONS
    UPLOAD_FOLDER = UPLOAD_FOLDER
    MAX_CONTENT_LENGTH = MAX_CONTENT_LENGTH


class ProductionConfig(Config):
    """Configurazione per l'ambiente di produzione."""
    pass


class DevelopmentConfig(Config):
    """Configurazione per l'ambiente di sviluppo."""
    DEBUG = True


class TestingConfig(Config):
    """Configurazione per l'ambiente di test."""
    TESTING = True
    DEBUG = True
    SECRET_KEY = "test_key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


def get_config():
    """Restituisce la classe di configurazione attiva."""
    env = os.environ.get("FLASK_ENV", "development")
    
    if env == "production":
        return ProductionConfig
    elif env == "testing":
        return TestingConfig
    else:
        return DevelopmentConfig