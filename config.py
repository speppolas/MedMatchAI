"""
Configurazione centralizzata per l'applicazione MedMatchINT.

Questo modulo gestisce la configurazione dell'applicazione, caricando valori
dalle variabili d'ambiente con fallback a valori predefiniti sicuri.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Caricamento delle variabili d'ambiente dal file .env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

# Funzione per verificare variabili richieste
def get_required_env_var(var_name, default=None):
    value = os.getenv(var_name, default)
    if not value:
        raise ValueError(f"ERRORE: La variabile {var_name} non è impostata.")
    return value

# Configurazione dell'applicazione
APP_NAME = os.getenv('APP_NAME', 'MedMatchINT')
APP_DESCRIPTION = os.getenv('APP_DESCRIPTION', 'Matching di trial clinici oncologici per l\'Istituto Nazionale dei Tumori')
VERSION = os.getenv('VERSION', '1.1.0')

# Configurazione del server
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 5000))
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't', 'yes')

# Configurazione del database (unificato per SQLAlchemy)
SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI', 'sqlite:///medmatchint.db')

SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Gestione dei file
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', str(BASE_DIR / 'uploads'))
MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))  # 10 MB predefinito

# Sicurezza
SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev_secret_key_123')
CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')

# LLM Configuration
USE_OLLAMA_FALLBACK = os.getenv('USE_OLLAMA_FALLBACK', 'true').lower() == 'true'
LLAMA_CPP_PATH = os.getenv('LLAMA_CPP_PATH', '')
LLM_MODEL_PATH = os.getenv('LLM_MODEL_PATH', '')
LLM_CONTEXT_SIZE = int(os.getenv('LLM_CONTEXT_SIZE', 2048))
LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', 0.1))
LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', 512))
LLM_TIMEOUT = int(os.getenv('LLM_TIMEOUT', 10))  # timeout in secondi
LLM_EXTRA_PARAMS = os.getenv('LLM_EXTRA_PARAMS', '')

# Skip llama.cpp validation when using fallback
# Skip validation when using fallback
if not USE_OLLAMA_FALLBACK:
    if LLAMA_CPP_PATH and not Path(LLAMA_CPP_PATH).exists():
        logging.warning(f"Warning: llama.cpp path not found: {LLAMA_CPP_PATH}")
    if LLM_MODEL_PATH and not Path(LLM_MODEL_PATH).exists():
        logging.warning(f"Warning: LLM model path not found: {LLM_MODEL_PATH}")

# Configurazione logging (Globale)
LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG').upper()
LOG_FORMAT = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)

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
    SQLALCHEMY_ENGINE_OPTIONS = SQLALCHEMY_ENGINE_OPTIONS
    UPLOAD_FOLDER = UPLOAD_FOLDER
    MAX_CONTENT_LENGTH = MAX_CONTENT_LENGTH
    USE_OLLAMA_FALLBACK = USE_OLLAMA_FALLBACK
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