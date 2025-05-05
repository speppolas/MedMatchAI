#!/usr/bin/env python3
"""
Script per recuperare i clinical trials attivi presso l'Istituto Nazionale dei Tumori (INT)
da ClinicalTrials.gov e salvarli in formato JSON per l'utilizzo nell'applicazione MedMatchINT.

Questo script utilizza l'API pubblica di ClinicalTrials.gov per ottenere i trial clinici
attivi all'INT, elabora i dati e li salva in un formato compatibile con l'applicazione.
"""

import json
import logging
import re
import sys
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import requests
from models import db, ClinicalTrial

# Configurazione del logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Costanti
CLINICALTRIALS_API_URL = "https://clinicaltrials.gov/api/v2/studies"
INT_ORGANIZATION_TERMS = [
    "Istituto Nazionale dei Tumori",
    "Fondazione IRCCS Istituto Nazionale dei Tumori",
    "INT Milano",
    "INT Milan",
    "Fondazione IRCCS - Istituto Nazionale dei Tumori",
    "Istituto Nazionale Tumori Milano",
    "National Cancer Institute Milan",
    "National Cancer Institute, Milan"
]
MAX_RESULTS_PER_REQUEST = 1000  # Limite massimo consentito dall'API

def fetch_trials_from_api(offset: int = 0) -> Dict[str, Any]:
    """
    Recupera i trial clinici da ClinicalTrials.gov utilizzando l'API ufficiale v2.
    
    Args:
        offset: Posizione di partenza per la paginazione
        
    Returns:
        Dict: Risposta JSON dall'API
    """
    # Nella versione v2 dell'API, dobbiamo utilizzare un formato di query diverso
    # Utilizziamo sia i termini dell'organizzazione che la città (Milano/Milan)
    
    # Parametri per la nuova API v2
    params = {
        "format": "json",
        "pageSize": 100,  # Numero di risultati per pagina (max 100 per l'API v2)
        "pageToken": str(offset) if offset > 0 else None,
        "query.term": '"Istituto Nazionale dei Tumori" AND (Milan OR Milano)',
        "query.field": ["LocationFacility", "LocationCity"],
        "countTotal": "true",
        "filter.recruitment": ["RECRUITING", "NOT_YET_RECRUITING", "ACTIVE_NOT_RECRUITING"],
        "filter.country": ["IT"],  # Italia
    }
    
    # Rimuovi i parametri None
    params = {k: v for k, v in params.items() if v is not None}
    
    logger.info(f"Richiesta all'API v2 di ClinicalTrials.gov con offset {offset}")
    logger.info(f"Parametri: {params}")
    
    try:
        response = requests.get(CLINICALTRIALS_API_URL, params=params)
        response.raise_for_status()  # Solleva un'eccezione per risposte HTTP non riuscite
        result = response.json()
        
        # Converti il risultato della v2 nel formato che si aspetta il resto del codice
        adapted_result = {
            "StudyFieldsResponse": {
                "NStudiesFound": result.get("totalCount", 0),
                "StudyFields": []
            }
        }
        
        # Adatta ogni studio al formato precedente
        for study in result.get("studies", []):
            adapted_study = {
                "NCTId": [study.get("protocolSection", {}).get("identificationModule", {}).get("nctId", "")],
                "BriefTitle": [study.get("protocolSection", {}).get("identificationModule", {}).get("briefTitle", "")],
                "OfficialTitle": [study.get("protocolSection", {}).get("identificationModule", {}).get("officialTitle", "")],
                "Phase": [study.get("protocolSection", {}).get("designModule", {}).get("phases", [""])[0] if study.get("protocolSection", {}).get("designModule", {}).get("phases") else ""],
                "BriefSummary": [study.get("protocolSection", {}).get("descriptionModule", {}).get("briefSummary", "")],
                "DetailedDescription": [study.get("protocolSection", {}).get("descriptionModule", {}).get("detailedDescription", "")],
                "EligibilityCriteria": [study.get("protocolSection", {}).get("eligibilityModule", {}).get("eligibilityCriteria", "")],
                "OverallStatus": [study.get("protocolSection", {}).get("statusModule", {}).get("overallStatus", "")],
                "LocationFacility": [],
                "LocationCity": [],
                "Gender": [study.get("protocolSection", {}).get("eligibilityModule", {}).get("sex", "")],
                "MinimumAge": [study.get("protocolSection", {}).get("eligibilityModule", {}).get("minimumAge", "")],
                "MaximumAge": [study.get("protocolSection", {}).get("eligibilityModule", {}).get("maximumAge", "")],
            }
            
            # Gestisci la lista di locations
            locations = study.get("protocolSection", {}).get("contactsLocationsModule", {}).get("locations", [])
            for location in locations:
                facility = location.get("facility", "")
                city = location.get("city", "")
                adapted_study["LocationFacility"].append(facility)
                adapted_study["LocationCity"].append(city)
            
            adapted_result["StudyFieldsResponse"]["StudyFields"].append(adapted_study)
        
        return adapted_result
    except requests.exceptions.RequestException as e:
        logger.error(f"Errore nella richiesta all'API: {str(e)}")
        raise

def extract_inclusion_exclusion_criteria(criteria_text: str) -> tuple:
    """
    Estrae i criteri di inclusione ed esclusione dal testo completo dei criteri di idoneità.
    
    Args:
        criteria_text: Testo completo dei criteri di idoneità
        
    Returns:
        tuple: (criteri di inclusione, criteri di esclusione)
    """
    # Normalizza gli a capo
    criteria_text = criteria_text.replace("\r\n", "\n").replace("\r", "\n")
    
    # Pattern comuni per identificare le sezioni di inclusione/esclusione
    inclusion_patterns = [
        r"Inclusion Criteria:[\s\n]*(.+?)(?:Exclusion Criteria:|$)",
        r"INCLUSION CRITERIA:[\s\n]*(.+?)(?:EXCLUSION CRITERIA:|$)",
        r"Criteri di inclusione:[\s\n]*(.+?)(?:Criteri di esclusione:|$)",
        r"CRITERI DI INCLUSIONE:[\s\n]*(.+?)(?:CRITERI DI ESCLUSIONE:|$)"
    ]
    
    exclusion_patterns = [
        r"Exclusion Criteria:[\s\n]*(.+?)(?:$)",
        r"EXCLUSION CRITERIA:[\s\n]*(.+?)(?:$)",
        r"Criteri di esclusione:[\s\n]*(.+?)(?:$)",
        r"CRITERI DI ESCLUSIONE:[\s\n]*(.+?)(?:$)"
    ]
    
    inclusion_text = ""
    exclusion_text = ""
    
    # Cerca i criteri di inclusione
    for pattern in inclusion_patterns:
        match = re.search(pattern, criteria_text, re.DOTALL | re.IGNORECASE)
        if match:
            inclusion_text = match.group(1).strip()
            break
    
    # Cerca i criteri di esclusione
    for pattern in exclusion_patterns:
        match = re.search(pattern, criteria_text, re.DOTALL | re.IGNORECASE)
        if match:
            exclusion_text = match.group(1).strip()
            break
    
    # Se non sono stati trovati criteri specifici, utilizza tutto il testo come criterio di inclusione
    if not inclusion_text and not exclusion_text:
        inclusion_text = criteria_text.strip()
    
    # Elabora i criteri e li trasforma in un formato strutturato
    inclusion_criteria = process_criteria(inclusion_text, "inclusion")
    exclusion_criteria = process_criteria(exclusion_text, "exclusion")
    
    return inclusion_criteria, exclusion_criteria

def process_criteria(criteria_text: str, criteria_type: str) -> List[Dict[str, str]]:
    """
    Elabora il testo dei criteri e lo trasforma in un formato strutturato.
    
    Args:
        criteria_text: Testo dei criteri
        criteria_type: Tipo di criteri ('inclusion' o 'exclusion')
        
    Returns:
        List: Lista di criteri elaborati in formato dizionario
    """
    if not criteria_text:
        return []
    
    # Divide il testo in criteri separati
    # Cerca pattern comuni come elenchi puntati, numerati o separati da nuove righe
    criteria_list = []
    
    # Rimuovi numerazione e punti elenco comuni
    lines = criteria_text.split("\n")
    processed_lines = []
    
    for line in lines:
        # Rimuovi la numerazione/punteggiatura all'inizio della riga (es. "1.", "- ", "• ")
        line = re.sub(r'^\s*(\d+[\.\)]\s*|\-\s*|\•\s*|\*\s*)', '', line).strip()
        if line:
            processed_lines.append(line)
    
    # Se ci sono righe separate, considerale come criteri separati
    if len(processed_lines) > 1:
        for line in processed_lines:
            if line.strip():
                criteria_list.append({
                    "text": line.strip(),
                    "type": identify_criterion_type(line, criteria_type)
                })
    else:
        # Se è un singolo blocco di testo, consideralo come un unico criterio
        criteria_list.append({
            "text": criteria_text.strip(),
            "type": criteria_type  # Tipo generico
        })
    
    return criteria_list

def identify_criterion_type(text: str, default_type: str) -> str:
    """
    Identifica il tipo specifico di criterio basato sul testo.
    
    Args:
        text: Testo del criterio
        default_type: Tipo predefinito ('inclusion' o 'exclusion')
        
    Returns:
        str: Tipo specifico del criterio
    """
    text_lower = text.lower()
    
    # Verifica i pattern comuni nei criteri
    if re.search(r'\bage\b|\byears old\b|\byears of age\b', text_lower):
        return "age"
    elif re.search(r'\b(?:male|female|gender|sex)\b', text_lower):
        return "gender"
    elif re.search(r'\becog\b|\bperformance status\b|\bps\b', text_lower):
        return "performance"
    elif re.search(r'\bstage\b', text_lower):
        return "stage"
    elif re.search(r'\bmutation\b|\baltered\b|\bexpression\b|\bpositive\b|\bnegative\b', text_lower):
        return "mutation"
    elif re.search(r'\bprior\b|\bprevious\b|\btreatment\b|\btherapy\b|\bsurgery\b|\bradiation\b|\bchemotherapy\b', text_lower):
        return "treatment"
    elif re.search(r'\bmetasta\w+\b', text_lower):
        return "metastasis"
    elif re.search(r'\bcancer\b|\btumor\b|\bcarcinoma\b|\bsarcoma\b|\bleukemia\b|\blymphoma\b|\bmelanoma\b|\bglioma\b|\bblastoma\b', text_lower):
        return "diagnosis"
    
    # Se non viene trovato un tipo specifico, restituisci il tipo predefinito
    return default_type

def process_trial_data(trial_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Elabora i dati di un trial clinico nel formato richiesto dall'applicazione.
    
    Args:
        trial_data: Dati grezzi del trial da ClinicalTrials.gov
        
    Returns:
        Dict: Dati del trial elaborati
    """
    # Estrai l'ID del trial
    nct_id = trial_data.get("NCTId", [""])[0]
    
    # Estrai il titolo (preferibilmente quello ufficiale)
    title = (
        trial_data.get("OfficialTitle", [""])[0] or 
        trial_data.get("BriefTitle", [""])[0]
    )
    
    # Estrai la fase
    phase_raw = trial_data.get("Phase", [""])[0]
    if phase_raw == "N/A" or not phase_raw:
        phase = "Not Applicable"
    else:
        phase = phase_raw
    
    # Estrai la descrizione
    description = (
        trial_data.get("DetailedDescription", [""])[0] or 
        trial_data.get("BriefSummary", [""])[0]
    )
    
    # Estrai i criteri di idoneità
    eligibility_criteria = trial_data.get("EligibilityCriteria", [""])[0]
    inclusion_criteria, exclusion_criteria = extract_inclusion_exclusion_criteria(eligibility_criteria)
    
    # Crea il dizionario del trial elaborato
    processed_trial = {
        "id": nct_id,
        "title": title,
        "phase": phase,
        "description": description,
        "inclusion_criteria": inclusion_criteria,
        "exclusion_criteria": exclusion_criteria,
        "status": trial_data.get("OverallStatus", [""])[0],
        "start_date": trial_data.get("StartDate", [""])[0],
        "completion_date": trial_data.get("CompletionDate", [""])[0],
        "sponsor": trial_data.get("LeadSponsorName", [""])[0],
        "last_updated": trial_data.get("LastUpdateSubmitDate", [""])[0],
        "locations": trial_data.get("LocationFacility", []),
        "min_age": trial_data.get("MinimumAge", [""])[0],
        "max_age": trial_data.get("MaximumAge", [""])[0],
        "gender": trial_data.get("Gender", [""])[0],
    }
    
    return processed_trial

def fetch_all_int_trials() -> List[Dict[str, Any]]:
    """
    Recupera tutti i trial clinici attivi all'INT da ClinicalTrials.gov.
    Gestisce la paginazione per recuperare tutti i risultati disponibili.
    
    Returns:
        List: Lista di trial clinici elaborati
    """
    all_trials = []
    next_page_token = None  # Per l'API v2 usiamo i page token invece degli offset
    total_trials = None
    
    # Tentiamo di recuperare i dati dall'API
    try:
        # L'API v2 utilizza un sistema di paginazione diverso
        while True:
            # Recupera un batch di trial (nella prima chiamata next_page_token è None)
            response_data = fetch_trials_from_api(next_page_token)
            
            # Estrai informazioni sulla paginazione
            if total_trials is None:
                total_trials = int(response_data.get("StudyFieldsResponse", {}).get("NStudiesFound", "0"))
                logger.info(f"Trovati {total_trials} trial clinici attivi all'INT")
            
            # Estrai i dati dei trial
            studies = response_data.get("StudyFieldsResponse", {}).get("StudyFields", [])
            
            if not studies:
                logger.info("Nessun altro trial trovato")
                break
            
            # Elabora ogni trial
            for study in studies:
                processed_trial = process_trial_data(study)
                
                # Assicuriamoci che il trial sia associato all'INT e a Milano
                is_int_trial = False
                is_milan_location = False
                
                # Verifica la città (Milano/Milan)
                cities = study.get("LocationCity", [])
                for city in cities:
                    if isinstance(city, str) and city.lower() in ["milan", "milano"]:
                        is_milan_location = True
                        break
                
                # Verifica l'istituto
                facilities = study.get("LocationFacility", [])
                for facility in facilities:
                    if isinstance(facility, str) and any(term.lower() in facility.lower() for term in INT_ORGANIZATION_TERMS):
                        is_int_trial = True
                        break
                
                # Se è verificato che il trial è dell'INT a Milano, aggiungilo
                if is_int_trial and is_milan_location:
                    # Aggiungi informazioni aggiuntive se disponibili
                    if "ConditionName" in study:
                        processed_trial["conditions"] = study.get("ConditionName", [])
                    
                    if "InterventionName" in study:
                        processed_trial["interventions"] = study.get("InterventionName", [])
                    
                    all_trials.append(processed_trial)
            
            # Ottieni il token per la pagina successiva
            next_page_token = response_data.get("nextPageToken")
            
            # Se non ci sono altre pagine, esci dal ciclo
            if not next_page_token:
                break
            
            # Pausa per evitare di sovraccaricare l'API
            time.sleep(1)
        
        logger.info(f"Recuperati {len(all_trials)} trial clinici attivi all'INT")
        
        # Se non abbiamo trovato trial, probabile che ci sia un problema con l'API
        if len(all_trials) == 0:
            logger.warning("Nessun trial trovato. Potrebbe esserci un problema con la query o con l'API.")
            # Proviamo una query più semplice come backup
            logger.info("Tentativo con una query più semplice...")
            return fallback_int_trials_fetch()
            
        return all_trials
        
    except Exception as e:
        logger.error(f"Errore durante il recupero dei trial: {str(e)}")
        logger.info("Tentativo con una query più semplice...")
        return fallback_int_trials_fetch()


def fallback_int_trials_fetch() -> List[Dict[str, Any]]:
    """
    Metodo di fallback che utilizza una query più semplice per recuperare i trial con l'API v2.
    Viene utilizzato in caso di errore con la query principale.
    
    Returns:
        List: Lista di trial clinici elaborati
    """
    all_trials = []
    
    try:
        # Parametri di base per una query più semplice con l'API v2
        params = {
            "format": "json",
            "pageSize": 50,
            "query.term": "Istituto Nazionale Tumori Milano",
            "countTotal": "true",
            "filter.country": ["IT"],  # Italia
        }
        
        logger.info("Eseguendo query di fallback con API v2...")
        
        response = requests.get(CLINICALTRIALS_API_URL, params=params)
        response.raise_for_status()
        
        result = response.json()
        
        # Adatta ed elabora ogni studio
        for study in result.get("studies", []):
            # Verifica se il trial è effettivamente in Milano
            locations = study.get("protocolSection", {}).get("contactsLocationsModule", {}).get("locations", [])
            is_milan = False
            
            for loc in locations:
                if loc.get("city", "").lower() in ["milan", "milano"]:
                    is_milan = True
                    break
            
            if not is_milan:
                continue  # Salta i trial che non sono a Milano
            
            adapted_study = {
                "NCTId": [study.get("protocolSection", {}).get("identificationModule", {}).get("nctId", "")],
                "BriefTitle": [study.get("protocolSection", {}).get("identificationModule", {}).get("briefTitle", "")],
                "OfficialTitle": [study.get("protocolSection", {}).get("identificationModule", {}).get("officialTitle", "")],
                "Phase": [study.get("protocolSection", {}).get("designModule", {}).get("phases", [""])[0] if study.get("protocolSection", {}).get("designModule", {}).get("phases") else ""],
                "BriefSummary": [study.get("protocolSection", {}).get("descriptionModule", {}).get("briefSummary", "")],
                "DetailedDescription": [study.get("protocolSection", {}).get("descriptionModule", {}).get("detailedDescription", "")],
                "EligibilityCriteria": [study.get("protocolSection", {}).get("eligibilityModule", {}).get("eligibilityCriteria", "")],
                "OverallStatus": [study.get("protocolSection", {}).get("statusModule", {}).get("overallStatus", "")]
            }
            
            processed_trial = process_trial_data(adapted_study)
            all_trials.append(processed_trial)
        
        logger.info(f"Recuperati {len(all_trials)} trial clinici con la query di fallback")
        return all_trials
    
    except Exception as e:
        logger.error(f"Anche la query di fallback ha fallito: {str(e)}")
        return []

def save_trials_to_json(trials: List[Dict[str, Any]], output_file: str = "trials_int.json") -> None:
    """
    Salva i trial clinici in un file JSON.
    
    Args:
        trials: Lista di trial clinici da salvare
        output_file: Percorso del file di output
    """
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(trials, f, ensure_ascii=False, indent=2)
        logger.info(f"Salvati {len(trials)} trial clinici nel file {output_file}")
    except Exception as e:
        logger.error(f"Errore nel salvataggio del file JSON: {str(e)}")
        raise

def save_trials_to_database(trials: List[Dict[str, Any]], app) -> None:
    """
    Salva i trial clinici nel database.
    
    Args:
        trials: Lista di trial clinici da salvare
        app: Istanza dell'applicazione Flask
    """
    with app.app_context():
        # Ottieni gli ID dei trial già presenti
        existing_ids = {trial.id for trial in ClinicalTrial.query.all()}
        
        added_count = 0
        updated_count = 0
        
        for trial_data in trials:
            trial_id = trial_data["id"]
            
            # Verifica se il trial esiste già
            if trial_id in existing_ids:
                # Aggiorna il trial esistente
                trial = ClinicalTrial.query.get(trial_id)
                trial.title = trial_data["title"]
                trial.phase = trial_data["phase"]
                trial.description = trial_data["description"]
                trial.inclusion_criteria = trial_data["inclusion_criteria"]
                trial.exclusion_criteria = trial_data["exclusion_criteria"]
                updated_count += 1
            else:
                # Crea un nuovo trial
                trial = ClinicalTrial(
                    id=trial_id,
                    title=trial_data["title"],
                    phase=trial_data["phase"],
                    description=trial_data["description"],
                    inclusion_criteria=trial_data["inclusion_criteria"],
                    exclusion_criteria=trial_data["exclusion_criteria"]
                )
                db.session.add(trial)
                added_count += 1
        
        # Salva le modifiche nel database
        db.session.commit()
        
        logger.info(f"Database aggiornato: {added_count} trial aggiunti, {updated_count} trial aggiornati")

def run_update(app=None, json_output=True, db_update=True):
    """
    Esegue l'aggiornamento completo dei trial clinici.
    
    Args:
        app: Istanza dell'applicazione Flask (necessaria per l'aggiornamento del database)
        json_output: Se True, salva i trial in un file JSON
        db_update: Se True, aggiorna il database
    """
    try:
        # Recupera i trial
        logger.info("Avvio del recupero dei trial clinici attivi all'INT...")
        trials = fetch_all_int_trials()
        
        # Salva in JSON se richiesto
        if json_output:
            save_trials_to_json(trials)
        
        # Aggiorna il database se richiesto
        if db_update and app:
            save_trials_to_database(trials, app)
        
        logger.info("Aggiornamento dei trial completato con successo")
        return trials
    except Exception as e:
        logger.error(f"Errore durante l'aggiornamento dei trial: {str(e)}")
        raise

if __name__ == "__main__":
    # Se eseguito direttamente, aggiorna solo il file JSON
    try:
        run_update(app=None, json_output=True, db_update=False)
    except Exception as e:
        logger.error(f"Errore nell'esecuzione dello script: {str(e)}")
        sys.exit(1)