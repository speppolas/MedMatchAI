"""
Configurazione centralizzata per l'applicazione MedMatchINT.

Questo modulo gestisce la configurazione dell'applicazione, caricando valori
dalle variabili d'ambiente con fallback a valori predefiniti sicuri.
"""

import os
from datetime import timedelta

# Configurazione dell'applicazione
APP_NAME = "MedMatchINT"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Sistema di abbinamento pazienti e trial clinici"

# Configurazione Flask
FLASK_ENV = os.environ.get("FLASK_ENV", "production")
FLASK_DEBUG = FLASK_ENV == "development"
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "default_insecure_key_do_not_use_in_production")

# Configurazione del Database
DATABASE_URL = os.environ.get("DATABASE_URL")
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Configurazione dei file di upload
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
PDF_AUTO_DELETE_TIMEOUT = int(os.environ.get("PDF_AUTO_DELETE_TIMEOUT", 30))  # In minuti
ALLOWED_EXTENSIONS = {"pdf"}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # Limite di 16 MB per gli upload

# Configurazione del sistema ibrido PostgreSQL + LLM
LLAMA_CPP_PATH = os.environ.get("LLAMA_CPP_PATH", "./llama.cpp")
LLM_MODEL_PATH = os.environ.get("LLM_MODEL_PATH", "./models/mistral-7b-instruct-v0.2.Q4_K_M.gguf")
LLM_CONTEXT_SIZE = int(os.environ.get("LLM_CONTEXT_SIZE", 4096))
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", 0.7))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", 2048))

# Configurazione Ollama (opzionale)
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mistral")

# Configurazione dell'API di ClinicalTrials.gov
CTGOV_API_BASE = "https://clinicaltrials.gov/api/query/study_fields"
CTGOV_FULL_STUDY_BASE = "https://clinicaltrials.gov/api/query/full_studies"
CTGOV_API_TIMEOUT = 60  # Timeout in secondi

# Configurazione del logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Configurazione per il deployment
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 5000))

# Impostazioni varie
TRIALS_JSON_FILE = os.environ.get("TRIALS_JSON_FILE", "trials_int.json")


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
    # Usa un database SQLite in memoria per i test
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


# Dizionario di configurazioni disponibili
config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig
}

# Configurazione attiva basata sull'ambiente
active_config = config_by_name.get(FLASK_ENV, ProductionConfig)


def get_config():
    """Restituisce la classe di configurazione attiva."""
    return active_config