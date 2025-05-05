"""
Script per correggere la struttura del database MedMatchINT.
Questo script aggiunge le colonne mancanti nella tabella clinical_trials.
"""

import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

logging.basicConfig(level=logging.INFO)

def create_app():
    """Crea e configura l'app Flask per l'inizializzazione del DB"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    return app

def fix_database_structure():
    """
    Corregge la struttura del database aggiungendo le colonne mancanti nella tabella clinical_trials.
    Questo viene fatto usando direttamente le query SQL tramite psycopg2.
    """
    try:
        # Connessione al database
        conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Lista delle colonne mancanti da aggiungere
        missing_columns = [
            ("status", "VARCHAR(50)"),
            ("start_date", "VARCHAR(50)"),
            ("completion_date", "VARCHAR(50)"),
            ("sponsor", "VARCHAR(200)"),
            ("last_updated", "VARCHAR(50)"),
            ("locations", "JSONB DEFAULT '[]'::jsonb"),
            ("min_age", "VARCHAR(50)"),
            ("max_age", "VARCHAR(50)"),
            ("gender", "VARCHAR(50)"),
            ("org_study_id", "VARCHAR(100)"),
            ("secondary_ids", "JSONB DEFAULT '[]'::jsonb")
        ]
        
        # Aggiungi ogni colonna mancante
        for column_name, column_type in missing_columns:
            # Verifica se la colonna esiste già
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'clinical_trials' AND column_name = %s",
                (column_name,)
            )
            if not cursor.fetchone():
                # Se la colonna non esiste, aggiungila
                sql = f"ALTER TABLE clinical_trials ADD COLUMN IF NOT EXISTS {column_name} {column_type}"
                cursor.execute(sql)
                logging.info(f"Aggiunta colonna {column_name} alla tabella clinical_trials")
            else:
                logging.info(f"La colonna {column_name} esiste già nella tabella clinical_trials")
        
        # Chiudi la connessione
        cursor.close()
        conn.close()
        
        logging.info("Struttura del database aggiornata con successo")
        return True
    except Exception as e:
        logging.error(f"Errore durante l'aggiornamento della struttura del database: {str(e)}")
        return False

def run_fix():
    """Esegue la correzione della struttura del database."""
    try:
        # Crea l'applicazione Flask
        app = create_app()
        
        # Esegui la correzione della struttura del database
        result = fix_database_structure()
        
        # Carica i trial dal database aggiornato
        if result:
            logging.info("Correzione del database completata con successo.")
            return True
        else:
            logging.error("Correzione del database fallita.")
            return False
    except Exception as e:
        logging.error(f"Errore durante l'esecuzione dello script: {str(e)}")
        return False

if __name__ == "__main__":
    run_fix()