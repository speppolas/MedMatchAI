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
CLINICALTRIALS_API_URL = "https://clinicaltrials.gov/api/query/study_fields"
INT_ORGANIZATION_TERMS = [
    "Istituto Nazionale dei Tumori",
    "Fondazione IRCCS Istituto Nazionale dei Tumori",
    "INT Milano",
    "INT Milan"
]
MAX_RESULTS_PER_REQUEST = 1000  # Limite massimo consentito dall'API

def fetch_trials_from_api(offset: int = 0) -> Dict[str, Any]:
    """
    Recupera i trial clinici da ClinicalTrials.gov utilizzando l'API ufficiale.
    
    Args:
        offset: Posizione di partenza per la paginazione
        
    Returns:
        Dict: Risposta JSON dall'API
    """
    # Crea la lista di termini per l'organizzazione separati da OR
    org_query = " OR ".join([f'"{term}"' for term in INT_ORGANIZATION_TERMS])
    
    # Parametri della richiesta
    params = {
        "fmt": "json",
        "min_rnk": offset + 1,
        "max_rnk": offset + MAX_RESULTS_PER_REQUEST,
        "expr": f'({org_query}) AND AREA[RecruitmentStatus]EXPAND[Term]RANGE[active,not yet active]',
        "fields": ",".join([
            "NCTId", "BriefTitle", "OfficialTitle", "BriefSummary", "DetailedDescription",
            "Phase", "StudyType", "OverallStatus", "StartDate", "PrimaryCompletionDate",
            "CompletionDate", "StudyFirstSubmitDate", "LastUpdateSubmitDate",
            "EligibilityCriteria", "HealthyVolunteers", "Gender", "MinimumAge", "MaximumAge",
            "LeadSponsorName", "CollaboratorName", "LocationFacility", "LocationCity",
            "LeadSponsorClass", "CollaboratorClass"
        ])
    }
    
    logger.info(f"Richiesta all'API di ClinicalTrials.gov con offset {offset}")
    
    try:
        response = requests.get(CLINICALTRIALS_API_URL, params=params)
        response.raise_for_status()  # Solleva un'eccezione per risposte HTTP non riuscite
        return response.json()
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
    offset = 0
    total_trials = None
    
    while True:
        # Recupera un batch di trial
        response_data = fetch_trials_from_api(offset)
        
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
            
            # Verifica che il trial sia associato all'INT
            is_int_trial = False
            for location in study.get("LocationFacility", []):
                if any(term.lower() in location.lower() for term in INT_ORGANIZATION_TERMS):
                    is_int_trial = True
                    break
            
            # Aggiungi solo i trial associati all'INT
            if is_int_trial:
                all_trials.append(processed_trial)
        
        # Aggiorna l'offset per la prossima richiesta
        offset += len(studies)
        
        # Verifica se abbiamo recuperato tutti i trial
        if offset >= total_trials:
            break
        
        # Pausa per evitare di sovraccaricare l'API
        time.sleep(1)
    
    logger.info(f"Recuperati {len(all_trials)} trial clinici attivi all'INT")
    return all_trials

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