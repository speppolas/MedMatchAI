#!/usr/bin/env python3
"""
Script di test per verificare il corretto funzionamento della ricerca su ClinicalTrials.gov.
"""

import os
import sys
import logging
import json
from flask import Flask
from fetch_trial_by_id import search_trial_by_other_id, fetch_trial_by_nct_id, fetch_and_save_trial_by_id

# Configura il logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Crea un'app Flask temporanea per i test
def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    return app

def test_search_by_id(trial_id):
    """
    Testa la ricerca di un trial utilizzando un ID.
    
    Args:
        trial_id: ID del trial da cercare
    """
    logging.info(f"Test di ricerca per ID: {trial_id}")
    
    try:
        nct_id = search_trial_by_other_id(trial_id)
        
        if nct_id:
            logging.info(f"Trovato NCT ID: {nct_id}")
            return nct_id
        else:
            logging.error(f"Nessun NCT ID trovato per {trial_id}")
            return None
    except Exception as e:
        logging.error(f"Errore durante la ricerca: {str(e)}")
        return None

def test_fetch_by_nct_id(nct_id):
    """
    Testa il recupero dei dettagli di un trial utilizzando un NCT ID.
    
    Args:
        nct_id: NCT ID del trial da recuperare
    """
    logging.info(f"Test di recupero per NCT ID: {nct_id}")
    
    try:
        trial_data = fetch_trial_by_nct_id(nct_id)
        
        if trial_data:
            # Estrai informazioni essenziali per debug
            protocol = trial_data.get("protocolSection", {})
            id_module = protocol.get("identificationModule", {})
            org_id = id_module.get("orgStudyIdInfo", {}).get("id", "N/A")
            title = id_module.get("officialTitle", id_module.get("briefTitle", "N/A"))
            
            logging.info(f"Trial trovato: {nct_id}")
            logging.info(f"  Titolo: {title}")
            logging.info(f"  ID Organizzazione: {org_id}")
            
            # Verifica gli ID secondari
            secondary_ids = id_module.get("secondaryIdInfos", [])
            for sec_id in secondary_ids:
                if "id" in sec_id:
                    sec_id_type = sec_id.get("type", "N/A")
                    sec_id_value = sec_id.get("id", "N/A")
                    logging.info(f"  ID Secondario ({sec_id_type}): {sec_id_value}")
            
            return True
        else:
            logging.error(f"Nessun trial trovato per l'NCT ID {nct_id}")
            return False
    except Exception as e:
        logging.error(f"Errore durante il recupero: {str(e)}")
        return False

def test_fetch_and_save(trial_id, app):
    """
    Testa il recupero e salvataggio completo di un trial.
    
    Args:
        trial_id: ID del trial da recuperare
        app: Istanza dell'applicazione Flask
    """
    logging.info(f"Test di recupero e salvataggio per ID: {trial_id}")
    
    try:
        # Disabilita il salvataggio su database e JSON per questo test
        trial_data = fetch_and_save_trial_by_id(trial_id, app, save_to_db=False, save_to_json=False)
        
        if trial_data:
            logging.info(f"Trial recuperato con successo: {trial_data.get('id', 'N/A')}")
            logging.info(f"  Titolo: {trial_data.get('title', 'N/A')}")
            logging.info(f"  ID Organizzazione: {trial_data.get('org_study_id', 'N/A')}")
            
            # Controlla gli ID secondari
            for sec_id in trial_data.get('secondary_ids', []):
                if 'id' in sec_id:
                    sec_id_type = sec_id.get('type', 'N/A')
                    sec_id_value = sec_id.get('id', 'N/A')
                    logging.info(f"  ID Secondario ({sec_id_type}): {sec_id_value}")
            
            return True
        else:
            logging.error(f"Nessun trial recuperato per l'ID {trial_id}")
            return False
    except Exception as e:
        logging.error(f"Errore durante il recupero e salvataggio: {str(e)}")
        return False

def run_all_tests():
    """
    Esegue tutti i test con diversi tipi di ID.
    """
    # Crea l'app Flask per i test
    app = create_app()
    
    # Lista di ID da testare
    test_ids = [
        "D5087C00001",  # ID del protocollo
        "NCT03334617",  # NCT ID (dovrebbe corrispondere a D5087C00001)
        "2017-000930-33",  # EudraCT Number per il trial D5087C00001
        "NCT04396223",  # Un altro NCT ID di esempio
        "NCT04396223"   # Un altro NCT ID di esempio
    ]
    
    for test_id in test_ids:
        logging.info(f"\n{'='*50}\nTEST PER ID: {test_id}\n{'='*50}")
        
        # Test 1: Ricerca per ID
        nct_id = test_search_by_id(test_id)
        
        # Test 2: Se abbiamo trovato un NCT ID, recupera i dettagli
        if nct_id:
            test_fetch_by_nct_id(nct_id)
        
        # Test 3: Recupero e salvataggio completo
        test_fetch_and_save(test_id, app)
        
        logging.info(f"{'='*50}\nFINE TEST PER ID: {test_id}\n{'='*50}\n")

if __name__ == "__main__":
    run_all_tests()