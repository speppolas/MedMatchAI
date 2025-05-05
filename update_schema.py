"""
Script per aggiornare lo schema del database MedMatchINT.
Aggiunge i campi org_study_id e secondary_ids alla tabella clinical_trials.
"""

import logging
import os
from flask import Flask
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import JSONB
from models import db, ClinicalTrial

# Configurazione del logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def create_app():
    """Crea e configura l'app Flask per l'aggiornamento dello schema."""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    db.init_app(app)
    return app

def update_schema(app):
    """
    Aggiorna lo schema del database per aggiungere i nuovi campi
    org_study_id e secondary_ids alla tabella clinical_trials.
    """
    with app.app_context():
        try:
            connection = db.engine.connect()
            
            # Verifica se i campi esistono già
            from sqlalchemy.sql import text
            columns_query = text("SELECT column_name FROM information_schema.columns WHERE table_name='clinical_trials'")
            result = connection.execute(columns_query)
            existing_columns = [row[0] for row in result]
            
            # Tutti i campi che potrebbero mancare
            missing_columns = {
                'org_study_id': 'VARCHAR(100)',
                'secondary_ids': 'JSONB DEFAULT \'[]\'::jsonb',
                'status': 'VARCHAR(50)',
                'start_date': 'VARCHAR(50)',
                'completion_date': 'VARCHAR(50)',
                'sponsor': 'VARCHAR(200)',
                'last_updated': 'VARCHAR(50)',
                'locations': 'JSONB DEFAULT \'[]\'::jsonb',
                'min_age': 'VARCHAR(50)',
                'max_age': 'VARCHAR(50)',
                'gender': 'VARCHAR(50)'
            }
            
            # Aggiungi i campi mancanti
            for column, column_type in missing_columns.items():
                if column not in existing_columns:
                    logger.info(f"Aggiunta colonna {column}...")
                    connection.execute(text(f"ALTER TABLE clinical_trials ADD COLUMN {column} {column_type}"))
            
            logger.info("Schema del database aggiornato con successo.")
            
        except Exception as e:
            logger.error(f"Errore nell'aggiornamento dello schema: {str(e)}")
            raise
        finally:
            connection.close()

def run_update():
    """Esegue l'aggiornamento dello schema."""
    try:
        app = create_app()
        update_schema(app)
        logger.info("Aggiornamento schema completato.")
    except Exception as e:
        logger.error(f"Errore nell'aggiornamento dello schema: {str(e)}")
        raise

if __name__ == "__main__":
    run_update()