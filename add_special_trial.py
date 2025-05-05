"""
Script per aggiungere manualmente il trial D5087C00001 (HUDSON) al database.
"""

import os
import logging
import json
from flask import Flask
from models import db, ClinicalTrial

logging.basicConfig(level=logging.INFO)

def create_app():
    """Crea e configura l'app Flask per l'inizializzazione del DB"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app

def add_special_trial(app):
    """
    Aggiunge manualmente il trial D5087C00001 (HUDSON) al database.
    """
    with app.app_context():
        try:
            # Verifica se il trial esiste già
            existing_trial = ClinicalTrial.query.filter(
                (ClinicalTrial.org_study_id == "D5087C00001") | 
                (ClinicalTrial.id == "NCT03334617")
            ).first()
            
            if existing_trial:
                logging.info(f"Il trial D5087C00001 (NCT03334617) esiste già nel database come {existing_trial.id}")
                return True
            
            # Dati del trial HUDSON (D5087C00001 / NCT03334617)
            hudson_trial = {
                "id": "NCT03334617",
                "title": "HUDSON - Targeting Molecular Aberrations in Non-Small Cell Lung Cancer (NSCLC) After Anti-PD-(L)1 Therapy",
                "phase": "PHASE2",
                "description": "This is a phase 2, open-label, multi-center, multi-drug umbrella study designed to evaluate the efficacy, safety, and tolerability of the study drugs as monotherapy, or in combination, in participants with metastatic non-small cell lung cancer (NSCLC) determined to harbor molecular aberrations and previously treated with anti-PD-1 or anti-PD-L1 therapy. The study consists of drug specific treatment modules where participants are assigned to a treatment module based on the molecular aberration identified in their tumor.",
                "inclusion_criteria": [
                    {
                        "text": "Histologically or cytologically documented metastatic non-small cell lung cancer (Stage IV according to the 8th edition of the Tumor-Node-Metastasis (TNM) staging criteria)",
                        "type": "diagnosis"
                    },
                    {
                        "text": "Prior anti-programmed cell death-1 (anti-PD-1) or anti-programmed cell death-ligand 1 (anti-PD-L1) antibody therapy",
                        "type": "treatment"
                    },
                    {
                        "text": "Eastern Cooperative Oncology Group (ECOG) performance status 0-1",
                        "type": "performance"
                    },
                    {
                        "text": "Age 18 years or older at the time of screening",
                        "type": "age"
                    },
                    {
                        "text": "Adequate organ and marrow function",
                        "type": "lab_values"
                    },
                    {
                        "text": "Molecular aberration in tumor tissue or in circulating tumor DNA that meets criteria for enrollment to a specific module",
                        "type": "mutation"
                    }
                ],
                "exclusion_criteria": [
                    {
                        "text": "Prior therapy with a treatment specific to the assigned module",
                        "type": "treatment"
                    },
                    {
                        "text": "Symptomatic or unstable brain metastases or leptomeningeal disease",
                        "type": "metastasis"
                    },
                    {
                        "text": "Any unresolved toxicities from prior therapy greater than CTCAE Grade 1",
                        "type": "exclusion"
                    },
                    {
                        "text": "Pregnancy or breastfeeding",
                        "type": "gender"
                    },
                    {
                        "text": "Known hypersensitivity to any of the excipients of the study drug",
                        "type": "exclusion"
                    }
                ],
                "status": "Recruiting",
                "start_date": "2018-02-13",
                "completion_date": "2025-06-30",
                "sponsor": "AstraZeneca",
                "last_updated": "2024-02-02",
                "locations": [
                    {
                        "name": "Istituto Nazionale dei Tumori",
                        "city": "Milano",
                        "country": "Italy"
                    }
                ],
                "min_age": "18 Years",
                "max_age": "N/A",
                "gender": "All",
                "org_study_id": "D5087C00001",
                "secondary_ids": [
                    {
                        "type": "Protocol ID",
                        "id": "D5087C00001"
                    },
                    {
                        "type": "EudraCT Number",
                        "id": "2017-000930-33"
                    }
                ]
            }
            
            # Aggiungi il trial al database
            new_trial = ClinicalTrial(
                id=hudson_trial["id"],
                title=hudson_trial["title"],
                phase=hudson_trial["phase"],
                description=hudson_trial["description"],
                inclusion_criteria=hudson_trial["inclusion_criteria"],
                exclusion_criteria=hudson_trial["exclusion_criteria"],
                status=hudson_trial["status"],
                start_date=hudson_trial["start_date"],
                completion_date=hudson_trial["completion_date"],
                sponsor=hudson_trial["sponsor"],
                last_updated=hudson_trial["last_updated"],
                locations=hudson_trial["locations"],
                min_age=hudson_trial["min_age"],
                max_age=hudson_trial["max_age"],
                gender=hudson_trial["gender"],
                org_study_id=hudson_trial["org_study_id"],
                secondary_ids=hudson_trial["secondary_ids"]
            )
            
            db.session.add(new_trial)
            db.session.commit()
            
            logging.info(f"Trial D5087C00001 (NCT03334617) aggiunto con successo al database")
            
            # Aggiorna anche il file JSON per avere coerenza
            try:
                with open('trials_int.json', 'r') as f:
                    trials = json.load(f)
                
                # Verifica se il trial esiste già nel file JSON
                exists = False
                for t in trials:
                    if t.get('id') == hudson_trial['id'] or t.get('org_study_id') == hudson_trial['org_study_id']:
                        exists = True
                        break
                
                if not exists:
                    trials.append(hudson_trial)
                    
                    with open('trials_int.json', 'w') as f:
                        json.dump(trials, f, indent=2)
                        
                    logging.info(f"Trial D5087C00001 (NCT03334617) aggiunto anche al file JSON")
                else:
                    logging.info(f"Il trial D5087C00001 esiste già nel file JSON")
            except Exception as e:
                logging.error(f"Errore nell'aggiornamento del file JSON: {str(e)}")
            
            return True
        except Exception as e:
            logging.error(f"Errore durante l'aggiunta del trial speciale D5087C00001: {str(e)}")
            return False

if __name__ == "__main__":
    try:
        app = create_app()
        add_special_trial(app)
    except Exception as e:
        logging.error(f"Errore durante l'esecuzione dello script: {str(e)}")