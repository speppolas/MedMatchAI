#!/usr/bin/env python3
"""
Script di aggiornamento dei clinical trials per MedMatchINT.
Questo script aggiorna sia il file JSON che il database con i nuovi trial.
"""

import logging
import os
import sys
from datetime import datetime
from flask import Flask
from fetch_trials import run_update
from models import db, ClinicalTrial

# Configurazione del logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    """Crea e configura l'app Flask per l'aggiornamento del DB"""
    app = Flask(__name__)
    
    # Configurazione Flask e SQLAlchemy
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    
    # Inizializzazione di SQLAlchemy
    db.init_app(app)
    
    return app

def update_trials():
    """Aggiorna i trial clinici sia nel file JSON che nel database."""
    try:
        # Crea l'app Flask
        app = create_app()
        
        # Controlla se il database è accessibile
        with app.app_context():
            logger.info("Verifico connessione al database...")
            db.engine.connect()
            logger.info("Connessione al database riuscita.")
        
        # Timestamp per il file di log
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"== Avvio aggiornamento trial clinici: {timestamp} ==")
        
        # Esegui l'aggiornamento
        trials = run_update(app=app, json_output=True, db_update=True)
        
        logger.info(f"Aggiornamento completato: {len(trials)} trial processati.")
        return True
    except Exception as e:
        logger.error(f"Errore durante l'aggiornamento: {str(e)}")
        return False

if __name__ == "__main__":
    # Se eseguito come script, aggiorna i trial
    success = update_trials()
    sys.exit(0 if success else 1)