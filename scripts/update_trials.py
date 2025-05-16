#scripts/update_trials.py

'''
import os
import sys
import json
import logging
import argparse
from flask import Flask
from datetime import datetime

# Aggiungi la directory principale al path per l'importazione dei moduli
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import db, ClinicalTrial
from scripts.trials_manager import (
    update_trials, fetch_and_save_trial_by_id, fetch_trial_by_nct_id, search_trial_by_other_id
)
from scripts.database_utils import load_trials_from_json, save_trials_to_json, import_trials_to_db

# Configurazione logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_app():
    """
    Crea e configura l'app Flask per l'aggiornamento dei trial.
    
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

def update_specific_trial(app, trial_id, save_to_db=True, save_to_json=True):
    """
    Aggiorna un trial clinico specifico nel database e/o nel file JSON.
    
    Args:
        app: Istanza dell'app Flask
        trial_id: ID del trial da aggiornare (NCT, EudraCT, Protocollo)
        save_to_db: Se True, salva il trial nel database
        save_to_json: Se True, aggiorna il file JSON
        
    Returns:
        bool: True se l'aggiornamento è riuscito, False altrimenti
    """
    try:
        with app.app_context():
            trial_data = fetch_and_save_trial_by_id(
                trial_id, 
                save_to_db=save_to_db, 
                save_to_json=save_to_json
            )
            
        if trial_data:
            logger.info(f"Trial {trial_id} aggiornato con successo.")
            return True
        else:
            logger.warning(f"Impossibile aggiornare il trial {trial_id}.")
            return False
    except Exception as e:
        logger.error(f"Errore nell'aggiornamento del trial {trial_id}: {str(e)}")
        return False

def update_trials_batch(app, search_terms=None, max_trials=100, save_to_db=True, save_to_json=True):
    """
    Aggiorna un batch di trial clinici nel database e/o nel file JSON.
    
    Args:
        app: Istanza dell'app Flask
        search_terms: Lista di termini di ricerca (es. ["lung cancer", "NSCLC"])
        max_trials: Numero massimo di trial da recuperare per termine di ricerca
        save_to_db: Se True, salva i trial nel database
        save_to_json: Se True, aggiorna il file JSON
        
    Returns:
        bool: True se l'aggiornamento è riuscito, False altrimenti
    """
    try:
        # Termini di ricerca predefiniti se non specificati
        if not search_terms:
            search_terms = [
                "lung cancer", "NSCLC", "breast cancer", "colorectal cancer",
                "prostate cancer", "melanoma", "ovarian cancer", "pancreatic cancer",
                "gastric cancer", "liver cancer", "renal cell carcinoma"
            ]
        
        with app.app_context():
            success = update_trials(
                search_terms=search_terms,
                max_trials=max_trials
            )
            
        if success:
            logger.info("Batch di trial aggiornato con successo.")
        else:
            logger.warning("Errore nell'aggiornamento del batch di trial.")
            
        return success
    except Exception as e:
        logger.error(f"Errore nell'aggiornamento del batch di trial: {str(e)}")
        return False

def main():
    """
    Funzione principale per l'aggiornamento automatico dei trial clinici.
    Gestisce gli argomenti da linea di comando e coordina le operazioni di aggiornamento.
    """
    # Configura gli argomenti da linea di comando
    parser = argparse.ArgumentParser(description='Aggiornamento dei trial clinici MedMatchINT')
    parser.add_argument('--trial-id', type=str, help='ID del trial specifico da aggiornare (NCT, EudraCT, Protocollo)')
    parser.add_argument('--terms', type=str, nargs='+', help='Termini di ricerca per l\'aggiornamento batch')
    parser.add_argument('--max', type=int, default=100, help='Numero massimo di trial da recuperare per termine di ricerca')
    parser.add_argument('--json-only', action='store_true', help='Aggiorna solo il file JSON (salta il database)')
    parser.add_argument('--db-only', action='store_true', help='Aggiorna solo il database (salta il file JSON)')
    
    args = parser.parse_args()
    
    # Imposta i flag di salvataggio in base agli argomenti
    save_to_db = not args.json_only
    save_to_json = not args.db_only
    
    if args.json_only and args.db_only:
        logger.error("Errore: Non puoi specificare sia --json-only che --db-only.")
        return 1
    
    # Crea l'app Flask
    app = create_app()
    
    # Modalità di aggiornamento: trial specifico o batch
    if args.trial_id:
        logger.info(f"Aggiornamento del trial specifico: {args.trial_id}")
        if update_specific_trial(app, args.trial_id, save_to_db=save_to_db, save_to_json=save_to_json):
            logger.info(f"Trial {args.trial_id} aggiornato con successo.")
        else:
            logger.error(f"Errore nell'aggiornamento del trial {args.trial_id}.")
            return 1
    else:
        logger.info("Avvio dell'aggiornamento batch dei trial clinici...")
        if update_trials_batch(app, search_terms=args.terms, max_trials=args.max, save_to_db=save_to_db, save_to_json=save_to_json):
            logger.info("Aggiornamento batch completato con successo.")
        else:
            logger.error("Errore nell'aggiornamento batch dei trial.")
            return 1
    
    logger.info("Processo di aggiornamento completato.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
    
    
'''