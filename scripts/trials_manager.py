# scripts/trials_manager.py
import os
import sys
import logging
import requests
from dotenv import load_dotenv
from flask import Flask
# Set the correct path for the project
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
from models import db, ClinicalTrial
from scripts.database_utils import save_trials_to_json, import_trials_to_db
from sqlalchemy import inspect


# Initialize Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load Environment Variables
load_dotenv()  

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    engine = db.engine
    inspector = inspect(engine)  # Utilizza l'ispettore per verificare le tabelle
    if 'clinical_trials' not in inspector.get_table_names():
        db.create_all()
        logger.info("✅ Table 'clinical_trials' created.")
    else:
        logger.info("✅ Table 'clinical_trials' already exists. Skipping creation.")

# Essential Trial IDs
ESSENTIAL_TRIAL_IDS = [
    "NCT04613596", "NCT05224141", "NCT05261399", "NCT05298423",
    "NCT06312137", "NCT06305754", "NCT05920356", "NCT06074588",
    "NCT05609968", "NCT05703997", "NCT06422143", "NCT05676931",
    "NCT06452277", "NCT06170788", "NCT06077760", "NCT06119581",
    "NCT06117774"
]

def fetch_trials_from_clinicaltrials_gov(nct_ids, max_retries=3):
    trials = []

    for nct_id in nct_ids:
        retries = 0
        while retries < max_retries:
            try:
                # Corrected API V2 URL
                api_url = f"https://clinicaltrials.gov/api/v2/studies/{nct_id}?fields=protocolSection"
                response = requests.get(api_url)
                logger.info(f"🔧 Fetching {nct_id} from {api_url}")

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"🔧 Raw API Response for {nct_id}: {data}")

                    if 'protocolSection' in data:
                        trial_data = process_study_data_v2(data)
                        if trial_data:
                            trials.append(trial_data)
                            logger.info(f"✅ Trial {nct_id} fetched and processed.")
                    else:
                        logger.warning(f"❌ No 'protocolSection' found for {nct_id}")
                    break
                else:
                    logger.error(f"❌ Error fetching trial {nct_id}: {response.status_code} - Retrying...")

            except Exception as e:
                logger.error(f"❌ Error fetching trial {nct_id}: {str(e)} - Retrying...")

            retries += 1

    logger.info(f"✅ Fetched {len(trials)} out of {len(nct_ids)} trials.")
    return trials


def process_study_data_v2(study):
    try:
        protocol = study.get('protocolSection', {})
        identification = protocol.get('identificationModule', {})
        status = protocol.get('statusModule', {})
        eligibility = protocol.get('eligibilityModule', {})
        design = protocol.get('designModule', {})

        trial = {
            "id": identification.get('nctId', 'Unknown'),
            "title": identification.get('officialTitle', 'Unknown Title'),
            "phase": ', '.join(design.get('phases', [])) or "Unknown",
            "description": identification.get('briefSummary', 'No description provided.'),
            "inclusion_criteria": eligibility.get('eligibilityCriteria', '').split("\n"),
            "exclusion_criteria": eligibility.get('eligibilityCriteria', '').split("\n"),
            "gender": eligibility.get('gender', 'All'),
            "min_age": eligibility.get('minimumAge', 'Not specified'),
            "max_age": eligibility.get('maximumAge', 'Not specified'),
            "status": status.get('overallStatus', 'Unknown'),
            "start_date": status.get('startDateStruct', {}).get('date', 'Unknown'),
            "completion_date": status.get('completionDateStruct', {}).get('date', 'Unknown'),
            "sponsor": identification.get('sponsor', 'Unknown'),
            "last_updated": status.get('lastUpdatePostDateStruct', {}).get('date', 'Unknown'),
        }

        if not trial["id"] or trial["id"] == 'Unknown':
            logger.error("❌ No NCT ID found for this trial. Skipping...")
            return None

        return trial
    except Exception as e:
        logger.error(f"❌ Error processing trial data: {str(e)}")
        return None


def save_and_import_trials(trials):
    """
    Saves the fetched trials to JSON and imports them into the database.
    """
    if not trials:
        logger.error("❌ No trials to save or import.")
        return
    
    save_trials_to_json(trials, "trials_int.json")
    logger.info("✅ Trials saved to JSON.")

    with app.app_context():
        import_trials_to_db(trials)
        logger.info("✅ Trials imported to database.")
        

if __name__ == "__main__":
    with app.app_context():
        logger.info("🚀 Fetching and Importing Essential Trials...")
        trials = fetch_trials_from_clinicaltrials_gov(ESSENTIAL_TRIAL_IDS)
        if trials:
            save_and_import_trials(trials)
            logger.info("✅ Database updated with essential trials.")
        else:
            logger.error("❌ No trials fetched. Database not updated.")