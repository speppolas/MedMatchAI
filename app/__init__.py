import os
import logging
from flask import Flask, Blueprint
from models import db, ClinicalTrial

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create the Blueprint
bp = Blueprint('main', __name__)

# Import routes after blueprint is created to avoid circular imports
from app import routes

def create_app():
    """Crea e configura l'app Flask"""
    app = Flask(__name__, 
                static_folder="../static", 
                template_folder="../templates")
    
    # Configura la cartella per gli upload temporanei
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')
    # Limite di dimensione file (10MB)
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
    
    # Configurazione Flask e SQLAlchemy
    app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev_key_please_change')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    
    # Inizializzazione delle estensioni
    db.init_app(app)
    
    # Registro del blueprint
    app.register_blueprint(bp)
    
    # Creazione delle tabelle se non esistenti
    with app.app_context():
        db.create_all()
    
    return app
