"""
Script di inizializzazione del database per MedMatchINT.
Questo script carica i clinical trials da trials_int.json nel database PostgreSQL.
"""

import os
import json
import logging
from flask import Flask
from models import db, ClinicalTrial

# Configura logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    """Crea e configura l'app Flask per l'inizializzazione del DB"""
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

def load_trials_from_json(json_file='trials_int.json'):
    """Carica i trials da un file JSON."""
    try:
        with open(json_file, 'r') as f:
            trials = json.load(f)
        logger.info(f"Caricati {len(trials)} trials da {json_file}")
        return trials
    except Exception as e:
        logger.error(f"Errore nel caricamento dei trials da {json_file}: {str(e)}")
        return []

def import_trials_to_db(app, trials):
    """Importa i trials nel database."""
    with app.app_context():
        # Crea le tabelle se non esistono
        db.create_all()
        
        # Controlla se ci sono già trials nel DB
        existing_count = ClinicalTrial.query.count()
        if existing_count > 0:
            logger.info(f"Trovati {existing_count} trials esistenti nel database")
            choice = input("Vuoi eliminare i trials esistenti prima dell'importazione? (s/n): ")
            if choice.lower() == 's':
                db.session.query(ClinicalTrial).delete()
                db.session.commit()
                logger.info("Trials esistenti eliminati")
            else:
                logger.info("Mantenuti i trials esistenti")
        
        # Importa i trials
        count = 0
        for trial in trials:
            # Verifica se il trial esiste già
            existing = ClinicalTrial.query.filter_by(id=trial['id']).first()
            if existing:
                logger.info(f"Trial {trial['id']} già presente, aggiornamento...")
                existing.title = trial['title']
                existing.phase = trial['phase']
                existing.description = trial['description']
                existing.inclusion_criteria = trial['inclusion_criteria']
                existing.exclusion_criteria = trial['exclusion_criteria']
            else:
                # Crea un nuovo trial
                new_trial = ClinicalTrial(
                    id=trial['id'],
                    title=trial['title'],
                    phase=trial['phase'],
                    description=trial['description'],
                    inclusion_criteria=trial['inclusion_criteria'],
                    exclusion_criteria=trial['exclusion_criteria']
                )
                db.session.add(new_trial)
                count += 1
        
        # Commit delle modifiche
        db.session.commit()
        logger.info(f"Importati {count} nuovi trials nel database")

if __name__ == "__main__":
    app = create_app()
    trials = load_trials_from_json()
    if trials:
        import_trials_to_db(app, trials)
        logger.info("Importazione completata con successo")
    else:
        logger.error("Nessun trial da importare, operazione annullata")