"""
Script di inizializzazione del database per MedMatchINT.
Questo script carica i clinical trials da trials_int.json nel database PostgreSQL.

Utilizzo: python scripts/db_init.py
"""

import os
import sys
import json
import logging
from flask import Flask
import argparse
from datetime import datetime

# Aggiungi la directory principale al path per l'importazione dei moduli
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import db, ClinicalTrial
from scripts.database_utils import init_database, load_trials_from_json, import_trials_to_db

# Configurazione logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_app():
    """
    Crea e configura l'app Flask per l'inizializzazione del DB.
    
    Returns:
        Flask: Un'istanza configurata dell'app Flask
    """
    app = Flask(__name__)
    
    # Configurazione del database
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        logger.error("Variabile d'ambiente DATABASE_URL non impostata!")
        sys.exit(1)
        
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
    }
    
    # Inizializza il database con l'app
    db.init_app(app)
    
    return app

def init_db_schema(app, drop_existing=False):
    """
    Inizializza lo schema del database creando le tabelle necessarie.
    
    Args:
        app: Istanza dell'app Flask
        drop_existing: Se True, elimina le tabelle esistenti prima di ricrearle
    
    Returns:
        bool: True se l'operazione è riuscita, False altrimenti
    """
    try:
        with app.app_context():
            if drop_existing:
                logger.info("Eliminazione delle tabelle esistenti...")
                db.drop_all()
                logger.info("Tabelle esistenti eliminate con successo.")
            
            logger.info("Creazione delle tabelle...")
            db.create_all()
            logger.info("Tabelle create con successo.")
            return True
    except Exception as e:
        logger.error(f"Errore nell'inizializzazione dello schema del database: {str(e)}")
        return False

def populate_db(app, json_file='trials_int.json'):
    """
    Popola il database con i dati dal file JSON dei trial clinici.
    
    Args:
        app: Istanza dell'app Flask
        json_file: Percorso al file JSON contenente i dati dei trial
        
    Returns:
        bool: True se l'operazione è riuscita, False altrimenti
    """
    try:
        # Carica i trial dal file JSON
        trials = load_trials_from_json(json_file)
        
        if not trials:
            logger.warning(f"Nessun trial caricato dal file {json_file}.")
            return False
        
        logger.info(f"Caricati {len(trials)} trial dal file JSON.")
        
        # Importa i trial nel database
        with app.app_context():
            success = import_trials_to_db(trials)
            
        if success:
            logger.info("Trial importati con successo nel database.")
        else:
            logger.error("Errore nell'importazione dei trial nel database.")
            
        return success
    except Exception as e:
        logger.error(f"Errore nella popolazione del database: {str(e)}")
        return False

def main():
    """
    Funzione principale per l'inizializzazione del database.
    Gestisce gli argomenti da linea di comando e coordina le operazioni di inizializzazione.
    """
    # Configura gli argomenti da linea di comando
    parser = argparse.ArgumentParser(description='Inizializzazione del database MedMatchINT')
    parser.add_argument('--drop', action='store_true', help='Elimina le tabelle esistenti prima di crearle')
    parser.add_argument('--json-file', type=str, default='trials_int.json', help='Percorso al file JSON dei trial (default: trials_int.json)')
    parser.add_argument('--skip-populate', action='store_true', help='Salta la popolazione del database')
    
    args = parser.parse_args()
    
    # Crea l'app Flask
    app = create_app()
    
    # Inizializza lo schema del database
    logger.info("Inizializzazione dello schema del database...")
    if init_db_schema(app, drop_existing=args.drop):
        logger.info("Schema del database inizializzato con successo.")
    else:
        logger.error("Errore nell'inizializzazione dello schema del database.")
        return 1
    
    # Popola il database con i dati dei trial
    if not args.skip_populate:
        logger.info("Popolazione del database con i dati dei trial...")
        if populate_db(app, json_file=args.json_file):
            logger.info("Database popolato con successo.")
        else:
            logger.warning("Errore nella popolazione del database.")
            return 1
    else:
        logger.info("Fase di popolazione del database saltata.")
    
    logger.info("Inizializzazione del database completata con successo.")
    return 0

if __name__ == "__main__":
    sys.exit(main())