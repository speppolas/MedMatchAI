# scripts/database_utils.py
import json
import logging
from models import db, ClinicalTrial
from sqlalchemy.exc import IntegrityError
from flask import current_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database(drop_existing=False):
    """
    Initializes the database, optionally dropping existing tables.
    """
    try:
        with current_app.app_context():
            if drop_existing:
                logger.info("🔧 Dropping existing database tables...")
                db.drop_all()
            logger.info("✅ Creating database tables...")
            db.create_all()
            logger.info("✅ Database initialized successfully.")
        return True
    except Exception as e:
        logger.error(f"❌ Error initializing the database: {str(e)}")
        return False

def load_trials_from_json(json_file='trials_int.json'):
    """
    Loads clinical trials from a JSON file.
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            trials = json.load(f)
        logger.info(f"✅ Loaded {len(trials)} trials from {json_file}")
        return trials
    except Exception as e:
        logger.error(f"❌ Error loading trials from JSON: {str(e)}")
        return []


def save_trials_to_json(trials, json_file='trials_int.json'):
    """
    Saves clinical trials to a JSON file.

    Args:
        trials (list): List of trial dictionaries.
        json_file (str): Path to the JSON file.
    """
    try:
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(trials, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ Saved {len(trials)} trials to {json_file}")
    except Exception as e:
        logger.error(f"❌ Error saving trials to JSON: {str(e)}")


def import_trials_to_db(trials):
    """
    Imports clinical trials into the database.
    """
    try:
        logger.info("🔧 Importing clinical trials into the database...")
        with current_app.app_context():
            for trial_data in trials:
                existing_trial = ClinicalTrial.query.get(trial_data['id'])

                if existing_trial:
                    logger.info(f"🔄 Updating existing trial {existing_trial.id}...")
                    for key, value in trial_data.items():
                        setattr(existing_trial, key, value)
                else:
                    new_trial = ClinicalTrial(**trial_data)
                    db.session.add(new_trial)

            db.session.commit()
            logger.info(f"✅ Successfully imported {len(trials)} trials into the database.")
        return True
    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"❌ Integrity Error during import: {str(e)}")
        return False
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error importing trials into database: {str(e)}")
        return False
