# scripts/db_init.py

import os
import sys
import logging
from flask import Flask
import argparse

# Add the main directory to the path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models import db, ClinicalTrial
from scripts.database_utils import init_database, load_trials_from_json, import_trials_to_db
from app import create_app  # Use the main app with proper configuration

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='Database Initialization')
    parser.add_argument('--drop', action='store_true', help='Drop existing tables before creating.')
    parser.add_argument('--json-file', type=str, default='trials_int.json', help='JSON file with trial data.')
    args = parser.parse_args()

    # Initialize Flask app using create_app (from app/__init__.py)
    app = create_app()
    

    with app.app_context():
        if args.drop:
            logger.info("🔧 Dropping existing database tables...")
            db.drop_all()
            logger.info("✅ Dropped existing tables.")

        logger.info("✅ Creating database tables...")
        db.create_all()
        logger.info("✅ Database initialized successfully.")

        # Load and import trials if JSON file is provided
        if args.json_file:
            logger.info(f"🔧 Loading trials from {args.json_file}...")
            trials = load_trials_from_json(args.json_file)
            if trials:
                import_trials_to_db(trials)
                logger.info(f"✅ Imported {len(trials)} trials into the database.")
            else:
                logger.warning(f"❌ No trials found in {args.json_file}.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
