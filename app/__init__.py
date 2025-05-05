import os
import logging
from flask import Flask, Blueprint
from models import db, ClinicalTrial
from config import (
    LOG_LEVEL, LOG_FORMAT, UPLOAD_FOLDER, MAX_CONTENT_LENGTH,
    SECRET_KEY, DATABASE_URL, SQLALCHEMY_TRACK_MODIFICATIONS,
    SQLALCHEMY_ENGINE_OPTIONS, get_config
)

# Configure logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# Create the Blueprint
bp = Blueprint('main', __name__)

# Import routes after blueprint is created to avoid circular imports
from app import routes

def create_app(config_class=None):
    """
    Crea e configura l'app Flask
    
    Args:
        config_class: Classe di configurazione opzionale
                     (se None, usa la configurazione dall'ambiente)
                     
    Returns:
        Flask: App Flask configurata
    """
    logger.info("Creazione dell'app MedMatchINT")
    
    app = Flask(__name__, 
                static_folder="../static", 
                template_folder="../templates")
    
    # Carica la configurazione
    if config_class is None:
        config_class = get_config()
    app.config.from_object(config_class)
    
    # Assicurati che alcuni valori critici siano impostati
    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
        
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = SECRET_KEY
        
    # Configura la cartella per gli upload temporanei
    if not app.config.get('UPLOAD_FOLDER'):
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), UPLOAD_FOLDER)
        app.config['UPLOAD_FOLDER'] = upload_dir
        
        # Crea la directory se non esiste
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
            logger.info(f"Creata directory per gli upload: {upload_dir}")
    
    # Impostazioni aggiuntive
    if not app.config.get('MAX_CONTENT_LENGTH'):
        app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
    
    if not app.config.get('SQLALCHEMY_TRACK_MODIFICATIONS'):
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
        
    if not app.config.get('SQLALCHEMY_ENGINE_OPTIONS'):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = SQLALCHEMY_ENGINE_OPTIONS
    
    # Inizializzazione delle estensioni
    db.init_app(app)
    
    # Registro del blueprint
    app.register_blueprint(bp)
    
    # Creazione delle tabelle se non esistenti
    with app.app_context():
        db.create_all()
        logger.info("Schema del database verificato/creato")
    
    logger.info("Applicazione MedMatchINT inizializzata con successo")
    return app
