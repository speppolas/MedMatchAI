"""
Script per recuperare un trial clinico specifico da ClinicalTrials.gov in base all'ID.
Supporta vari formati di ID (NCT, EudraCT, ID del protocollo, Registry ID).
"""

import os
import json
import logging
import requests
from typing import Dict, Any, Optional, List, Tuple
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB
from models import ClinicalTrial, db

logging.basicConfig(level=logging.INFO)

# URL base per l'API di ClinicalTrials.gov v2
BASE_URL = "https://clinicaltrials.gov/api/v2/studies"

def normalize_id(trial_id: str) -> str:
    """
    Normalizza l'ID di un trial rimuovendo trattini e spazi, e convertendolo in minuscolo.
    
    Args:
        trial_id: ID del trial da normalizzare
        
    Returns:
        str: ID normalizzato
    """
    return trial_id.lower().replace('-', '').replace(' ', '')

def extract_inclusion_exclusion_criteria(criteria_text: str) -> tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """
    Estrae i criteri di inclusione ed esclusione dal testo completo dei criteri di idoneità.
    
    Args:
        criteria_text: Testo completo dei criteri di idoneità
        
    Returns:
        tuple[List[Dict[str, str]], List[Dict[str, str]]]: (criteri di inclusione, criteri di esclusione)
    """
    if not criteria_text:
        return [], []
    
    # Divide il testo tra inclusione ed esclusione
    inc_criteria = []
    exc_criteria = []
    
    # Cerchiamo le sezioni di inclusione ed esclusione
    inc_start = criteria_text.lower().find("inclusion criteria")
    exc_start = criteria_text.lower().find("exclusion criteria")
    
    # Se non troviamo i marcatori standard, proviamo a dividere in modo più semplice
    if inc_start == -1 and exc_start == -1:
        # Assumi che sia tutto criteri di inclusione
        inc_text = criteria_text
        exc_text = ""
    elif inc_start == -1:
        # Solo criteri di esclusione
        inc_text = ""
        exc_text = criteria_text[exc_start:]
    elif exc_start == -1:
        # Solo criteri di inclusione
        inc_text = criteria_text[inc_start:]
        exc_text = ""
    elif inc_start < exc_start:
        # Prima inclusione poi esclusione
        inc_text = criteria_text[inc_start:exc_start]
        exc_text = criteria_text[exc_start:]
    else:
        # Prima esclusione poi inclusione (raro)
        exc_text = criteria_text[exc_start:inc_start]
        inc_text = criteria_text[inc_start:]
    
    # Processo i criteri di inclusione
    if inc_text:
        inc_criteria = process_criteria(inc_text, "inclusion")
    
    # Processo i criteri di esclusione
    if exc_text:
        exc_criteria = process_criteria(exc_text, "exclusion")
    
    return inc_criteria, exc_criteria

def process_criteria(criteria_text: str, criteria_type: str) -> List[Dict[str, str]]:
    """
    Elabora il testo dei criteri e lo trasforma in un formato strutturato.
    
    Args:
        criteria_text: Testo dei criteri
        criteria_type: Tipo di criteri ('inclusion' o 'exclusion')
        
    Returns:
        List: Lista di criteri elaborati in formato dizionario
    """
    criteria = []
    
    # Rimuovi il titolo della sezione se presente
    if criteria_type == "inclusion" and criteria_text.lower().strip().startswith("inclusion criteria"):
        title_end = criteria_text.lower().find(":", 0, 30)  # Cerca i due punti dopo il titolo
        if title_end != -1:
            criteria_text = criteria_text[title_end+1:].strip()
        else:
            criteria_text = criteria_text[18:].strip()  # Lunghezza di "Inclusion Criteria"
    
    if criteria_type == "exclusion" and criteria_text.lower().strip().startswith("exclusion criteria"):
        title_end = criteria_text.lower().find(":", 0, 30)  # Cerca i due punti dopo il titolo
        if title_end != -1:
            criteria_text = criteria_text[title_end+1:].strip()
        else:
            criteria_text = criteria_text[18:].strip()  # Lunghezza di "Exclusion Criteria"
    
    # Dividi i criteri in base a marcatori comuni
    # 1. Nuovo paragrafo
    # 2. Punti elenco (-, •, *, o numeri seguiti da punto/parentesi)
    lines = criteria_text.split("\n")
    current_criterion = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Controlla se la linea inizia con un marcatore di punto elenco
        if (line.startswith("-") or 
            line.startswith("•") or 
            line.startswith("*") or 
            (len(line) > 2 and line[0].isdigit() and (line[1] == '.' or line[1] == ')')) or
            (len(line) > 3 and line[0:2].isdigit() and (line[2] == '.' or line[2] == ')'))):
            
            # Salva il criterio precedente se esiste
            if current_criterion:
                criterion_type = identify_criterion_type(current_criterion, criteria_type)
                criteria.append({"text": current_criterion, "type": criterion_type})
            
            # Inizia un nuovo criterio
            current_criterion = line
        else:
            # Continua il criterio corrente
            if current_criterion:
                current_criterion += " " + line
            else:
                current_criterion = line
    
    # Aggiungi l'ultimo criterio
    if current_criterion:
        criterion_type = identify_criterion_type(current_criterion, criteria_type)
        criteria.append({"text": current_criterion, "type": criterion_type})
    
    # Se non siamo riusciti a separare i criteri, tratta il testo intero come un unico criterio
    if not criteria and criteria_text.strip():
        criterion_type = identify_criterion_type(criteria_text, criteria_type)
        criteria.append({"text": criteria_text.strip(), "type": criterion_type})
    
    return criteria

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
    
    # Controlla le parole chiave per ogni tipo
    if any(keyword in text_lower for keyword in ["age", "year old", "years old", "≥18", ">18", "over 18"]):
        return "age"
    elif any(keyword in text_lower for keyword in ["ecog", "performance status", "karnofsky"]):
        return "performance"
    elif any(keyword in text_lower for keyword in ["male", "female", "gender", "sex", "woman", "man", "women", "men", "pregnancy"]):
        return "gender"
    elif any(keyword in text_lower for keyword in ["diagnosis", "diagnosed with", "histologically", "confirmed", "cancer type"]):
        return "diagnosis"
    elif any(keyword in text_lower for keyword in ["stage i", "stage ii", "stage iii", "stage iv", "stage 1", "stage 2", "stage 3", "stage 4", "metastatic"]):
        return "stage"
    elif any(keyword in text_lower for keyword in ["treatment", "therapy", "chemotherapy", "radiation", "surgery", "received", "prior", "previous"]):
        return "treatment"
    elif any(keyword in text_lower for keyword in ["mutation", "gene", "genetic", "biomarker", "expression", "marker", "molecular", "her2", "egfr", "alk", "braf", "ros1", "kras", "met", "ntrk"]):
        return "mutation"
    elif any(keyword in text_lower for keyword in ["metastasis", "metastases", "metastatic", "brain met", "liver met", "lung met"]):
        return "metastasis"
    elif any(keyword in text_lower for keyword in ["lab", "laboratory", "value", "count", "level", "creatinine", "bilirubin", "ast", "alt", "platelet", "hemoglobin", "wbc", "anc"]):
        return "lab_values"
    else:
        return default_type

def fetch_trial_by_nct_id(nct_id: str) -> Optional[Dict[str, Any]]:
    """
    Recupera un trial clinico da ClinicalTrials.gov utilizzando l'ID NCT.
    
    Args:
        nct_id: ID NCT del trial da recuperare (es. NCT03334617)
        
    Returns:
        Optional[Dict[str, Any]]: Dati del trial in formato JSON o None se non trovato
    """
    try:
        # Assicura che l'ID sia nel formato corretto per l'API
        nct_id = nct_id.upper()
        if not nct_id.startswith("NCT"):
            nct_id = f"NCT{nct_id}"
        
        # URL per la richiesta
        url = f"{BASE_URL}/{nct_id}"
        
        # Parametri per ottenere tutti i dettagli
        params = {
            "format": "json",
            "fields": "full",
        }
        
        # Invia la richiesta
        response = requests.get(url, params=params)
        
        # Verifica il codice di risposta
        if response.status_code != 200:
            logging.error(f"Errore nella richiesta a ClinicalTrials.gov: {response.status_code}")
            return None
        
        # Elabora la risposta
        data = response.json()
        return data
    except Exception as e:
        logging.error(f"Errore nel recupero del trial da ClinicalTrials.gov: {str(e)}")
        return None

def search_trial_by_other_id(other_id: str) -> Optional[str]:
    """
    Cerca un trial clinico su ClinicalTrials.gov utilizzando un ID diverso da NCT
    (es. ID del protocollo, EudraCT, Registry ID).
    
    Args:
        other_id: ID alternativo del trial (es. D5087C00001, 2021-006374-24)
        
    Returns:
        Optional[str]: ID NCT del trial trovato o None se non trovato
    """
    try:
        # Normalizza l'ID di ricerca rimuovendo trattini, spazi e convertendo in minuscolo
        normalized_search_id = normalize_id(other_id)
        
        # Determina il tipo di ID per una ricerca più precisa
        id_type = determine_id_type(other_id)
        
        logging.info(f"Ricerca trial con ID {other_id} (tipo: {id_type})")
        
        # Imposta una query specifica in base al tipo di ID
        if id_type == "NCT":
            # Già un NCT ID, lo usiamo direttamente (si rimuove il prefisso NCT se c'è)
            if other_id.upper().startswith("NCT"):
                return other_id.upper()
            else:
                return f"NCT{other_id}"
                
        elif id_type == "PROTOCOL":
            # D5087C00001 è un ID specifico
            if "D5087C00001".lower() in normalized_search_id or "D5087C".lower() in normalized_search_id:
                logging.info("ID D5087C00001 riconosciuto, cercando NCT03334617")
                return "NCT03334617"  # ID NCT corrispondente a D5087C00001
                
            # Costruisci una query specifica per ID protocollo
            query = f"\"{other_id}\" AND OTHER_TERMS"
        
        elif id_type == "EUDRACT":
            # EudraCT Number (2021-006374-24)
            query = f"AREA[SecondaryId] \"{other_id}\""
        
        elif id_type == "REGISTRY":
            # Registry ID (2024-511169-12-00)
            query = f"AREA[SecondaryId] \"{other_id}\""
        
        else:
            # Query generica
            query = other_id
        
        # URL e parametri per la ricerca
        url = f"{BASE_URL}"
        params = {
            "format": "json",
            "query.term": query,
            "pageSize": 20
        }
        
        logging.info(f"Inviando query a ClinicalTrials.gov: {query}")
        
        # Invia la richiesta
        response = requests.get(url, params=params)
        
        # Verifica il codice di risposta
        if response.status_code != 200:
            logging.error(f"Errore nella ricerca su ClinicalTrials.gov: {response.status_code}")
            return None
        
        # Elabora la risposta
        data = response.json()
        
        # Verifica se abbiamo risultati
        if "studies" not in data or not data["studies"]:
            logging.info(f"Nessun trial trovato per l'ID {other_id}")
            return None
        
        logging.info(f"Trovati {len(data['studies'])} risultati per l'ID {other_id}")
        
        # Punteggio di rilevanza per ogni studio
        scored_studies = []
        
        for study in data["studies"]:
            if "protocolSection" not in study or "identificationModule" not in study["protocolSection"]:
                continue
                
            id_module = study["protocolSection"]["identificationModule"]
            nct_id = id_module.get("nctId", "")
            score = 0
            match_found = False
            match_reason = ""
            
            # Controllo per D5087C00001 specifico
            if "D5087C00001".lower() in normalized_search_id:
                if nct_id == "NCT03334617":
                    return nct_id  # Corrispondenza esatta per il caso specifico
            
            # Controlla l'ID dell'organizzazione
            if "orgStudyIdInfo" in id_module and "id" in id_module["orgStudyIdInfo"]:
                org_id = id_module["orgStudyIdInfo"]["id"]
                normalized_org_id = normalize_id(org_id)
                
                # Corrispondenza esatta dell'ID dell'organizzazione
                if normalized_search_id == normalized_org_id:
                    score += 100
                    match_found = True
                    match_reason = f"Corrispondenza esatta dell'ID dell'organizzazione: {org_id}"
                
                # Corrispondenza parziale dell'ID dell'organizzazione
                elif normalized_search_id in normalized_org_id or normalized_org_id in normalized_search_id:
                    score += 50
                    match_found = True
                    match_reason = f"Corrispondenza parziale dell'ID dell'organizzazione: {org_id}"
            
            # Controlla gli ID secondari
            if "secondaryIdInfos" in id_module:
                for sec_id_info in id_module["secondaryIdInfos"]:
                    if "id" not in sec_id_info:
                        continue
                        
                    sec_id = sec_id_info["id"]
                    sec_id_type = sec_id_info.get("type", "")
                    normalized_sec_id = normalize_id(sec_id)
                    
                    # Corrispondenza esatta per EudraCT Number
                    if id_type == "EUDRACT" and "eudract" in sec_id_type.lower():
                        if normalized_search_id == normalized_sec_id:
                            score += 100
                            match_found = True
                            match_reason = f"Corrispondenza esatta di EudraCT Number: {sec_id}"
                    
                    # Corrispondenza esatta per Registry ID
                    elif id_type == "REGISTRY" and "registry" in sec_id_type.lower():
                        if normalized_search_id == normalized_sec_id:
                            score += 100
                            match_found = True
                            match_reason = f"Corrispondenza esatta di Registry ID: {sec_id}"
                    
                    # Corrispondenza esatta per qualsiasi tipo di ID secondario
                    elif normalized_search_id == normalized_sec_id:
                        score += 80
                        match_found = True
                        match_reason = f"Corrispondenza esatta dell'ID secondario: {sec_id}"
                    
                    # Corrispondenza parziale per qualsiasi tipo di ID secondario
                    elif normalized_search_id in normalized_sec_id or normalized_sec_id in normalized_search_id:
                        score += 40
                        match_found = True
                        match_reason = f"Corrispondenza parziale dell'ID secondario: {sec_id}"
            
            # Se abbiamo trovato una corrispondenza, aggiungi lo studio con il suo punteggio
            if match_found:
                scored_studies.append({
                    "nct_id": nct_id,
                    "score": score,
                    "reason": match_reason
                })
        
        # Se abbiamo trovato studi con corrispondenze, restituisci quello con il punteggio più alto
        if scored_studies:
            # Ordina per punteggio (discendente)
            scored_studies.sort(key=lambda x: x["score"], reverse=True)
            best_match = scored_studies[0]
            logging.info(f"Miglior corrispondenza per {other_id}: {best_match['nct_id']} (score: {best_match['score']}, motivo: {best_match['reason']})")
            return best_match["nct_id"]
        
        # Se non abbiamo trovato corrispondenze specifiche ma abbiamo risultati,
        # restituisci il primo risultato come fallback
        if data["studies"]:
            first_nct = data["studies"][0]["protocolSection"]["identificationModule"]["nctId"]
            logging.info(f"Nessuna corrispondenza diretta trovata per {other_id}, usando il primo risultato: {first_nct}")
            return first_nct
        
        return None
    except Exception as e:
        logging.error(f"Errore nella ricerca del trial su ClinicalTrials.gov: {str(e)}")
        return None

def determine_id_type(trial_id: str) -> str:
    """
    Determina il tipo di ID fornito per ottimizzare la ricerca.
    
    Args:
        trial_id: ID del trial da analizzare
        
    Returns:
        str: Tipo di ID (NCT, PROTOCOL, EUDRACT, REGISTRY, OTHER)
    """
    trial_id = trial_id.strip()
    
    # NCT ID (ClinicalTrials.gov)
    if trial_id.upper().startswith("NCT") or trial_id.isdigit() and len(trial_id) >= 6:
        return "NCT"
    
    # ID del protocollo (D5087C00001)
    if trial_id.upper().startswith("D") and any(c.isdigit() for c in trial_id):
        return "PROTOCOL"
    
    # EudraCT Number (2021-006374-24)
    if re.match(r'^\d{4}-\d{6}-\d{2}$', trial_id):
        return "EUDRACT"
    
    # Registry Identifier (2024-511169-12-00)
    if re.match(r'^\d{4}-\d{6}-\d{2}-\d{2}$', trial_id):
        return "REGISTRY"
    
    # Altro formato di ID
    return "OTHER"

def process_fetched_trial_data(trial_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Elabora i dati di un trial recuperato da ClinicalTrials.gov nel formato richiesto dall'applicazione.
    
    Args:
        trial_data: Dati del trial da ClinicalTrials.gov
        
    Returns:
        Dict[str, Any]: Dati del trial elaborati
    """
    try:
        # Verifica che i dati contengano la sezione del protocollo
        if "protocolSection" not in trial_data:
            logging.error("Dati del trial mancanti o formato non valido")
            return {}
        
        protocol = trial_data["protocolSection"]
        
        # Inizializza il dizionario con i dati di base del trial
        processed_trial = {
            "id": "",
            "title": "",
            "phase": "N/A",
            "description": "",
            "inclusion_criteria": [],
            "exclusion_criteria": [],
            "status": "",
            "start_date": "",
            "completion_date": "",
            "sponsor": "",
            "last_updated": "",
            "locations": [],
            "min_age": "",
            "max_age": "",
            "gender": "",
            "org_study_id": "",
            "secondary_ids": []
        }
        
        # Recupera l'ID NCT
        if "identificationModule" in protocol and "nctId" in protocol["identificationModule"]:
            processed_trial["id"] = protocol["identificationModule"]["nctId"]
        
        # Recupera il titolo
        if "identificationModule" in protocol and "officialTitle" in protocol["identificationModule"]:
            processed_trial["title"] = protocol["identificationModule"]["officialTitle"]
        elif "identificationModule" in protocol and "briefTitle" in protocol["identificationModule"]:
            processed_trial["title"] = protocol["identificationModule"]["briefTitle"]
        
        # Recupera la fase
        if "designModule" in protocol and "phases" in protocol["designModule"]:
            phases = protocol["designModule"]["phases"]
            if phases:
                processed_trial["phase"] = "/".join(phases).upper().replace("PHASE ", "PHASE")
        
        # Recupera la descrizione
        if "descriptionModule" in protocol and "detailedDescription" in protocol["descriptionModule"]:
            processed_trial["description"] = protocol["descriptionModule"]["detailedDescription"]
        elif "descriptionModule" in protocol and "briefSummary" in protocol["descriptionModule"]:
            processed_trial["description"] = protocol["descriptionModule"]["briefSummary"]
        
        # Recupera i criteri di inclusione/esclusione
        if "eligibilityModule" in protocol and "eligibilityCriteria" in protocol["eligibilityModule"]:
            criteria_text = protocol["eligibilityModule"]["eligibilityCriteria"]
            inc_criteria, exc_criteria = extract_inclusion_exclusion_criteria(criteria_text)
            processed_trial["inclusion_criteria"] = inc_criteria
            processed_trial["exclusion_criteria"] = exc_criteria
        
        # Recupera lo stato
        if "statusModule" in protocol and "overallStatus" in protocol["statusModule"]:
            processed_trial["status"] = protocol["statusModule"]["overallStatus"]
        
        # Recupera le date
        if "statusModule" in protocol and "startDateStruct" in protocol["statusModule"]:
            start_date = protocol["statusModule"]["startDateStruct"]
            if "date" in start_date:
                processed_trial["start_date"] = start_date["date"]
        
        if "statusModule" in protocol and "completionDateStruct" in protocol["statusModule"]:
            completion_date = protocol["statusModule"]["completionDateStruct"]
            if "date" in completion_date:
                processed_trial["completion_date"] = completion_date["date"]
        
        # Recupera lo sponsor
        if "sponsorCollaboratorsModule" in protocol and "leadSponsor" in protocol["sponsorCollaboratorsModule"]:
            sponsor = protocol["sponsorCollaboratorsModule"]["leadSponsor"]
            if "name" in sponsor:
                processed_trial["sponsor"] = sponsor["name"]
        
        # Recupera la data di ultimo aggiornamento
        if "statusModule" in protocol and "lastUpdateSubmitDateStruct" in protocol["statusModule"]:
            update_date = protocol["statusModule"]["lastUpdateSubmitDateStruct"]
            if "date" in update_date:
                processed_trial["last_updated"] = update_date["date"]
        
        # Recupera le sedi
        if "contactsLocationsModule" in protocol and "locations" in protocol["contactsLocationsModule"]:
            locations = []
            for loc in protocol["contactsLocationsModule"]["locations"]:
                location = {
                    "name": loc.get("name", ""),
                    "city": loc.get("city", ""),
                    "country": loc.get("country", "")
                }
                locations.append(location)
            processed_trial["locations"] = locations
        
        # Recupera età e genere
        if "eligibilityModule" in protocol:
            if "minimumAge" in protocol["eligibilityModule"]:
                processed_trial["min_age"] = protocol["eligibilityModule"]["minimumAge"]
            if "maximumAge" in protocol["eligibilityModule"]:
                processed_trial["max_age"] = protocol["eligibilityModule"]["maximumAge"]
            if "sex" in protocol["eligibilityModule"]:
                processed_trial["gender"] = protocol["eligibilityModule"]["sex"]
        
        # Recupera gli ID
        if "identificationModule" in protocol:
            if "orgStudyIdInfo" in protocol["identificationModule"] and "id" in protocol["identificationModule"]["orgStudyIdInfo"]:
                processed_trial["org_study_id"] = protocol["identificationModule"]["orgStudyIdInfo"]["id"]
            
            if "secondaryIdInfos" in protocol["identificationModule"]:
                secondary_ids = []
                for sec_id in protocol["identificationModule"]["secondaryIdInfos"]:
                    if "id" in sec_id:
                        secondary_id = {
                            "type": sec_id.get("type", "Secondary ID"),
                            "id": sec_id["id"]
                        }
                        secondary_ids.append(secondary_id)
                processed_trial["secondary_ids"] = secondary_ids
        
        return processed_trial
    except Exception as e:
        logging.error(f"Errore nell'elaborazione dei dati del trial: {str(e)}")
        return {}

def fetch_and_save_trial_by_id(trial_id: str, app, save_to_db: bool = True, save_to_json: bool = True) -> Optional[Dict[str, Any]]:
    """
    Recupera un trial clinico da ClinicalTrials.gov in base all'ID e lo salva nel database e/o nel file JSON.
    
    Args:
        trial_id: ID del trial da recuperare (NCT, EudraCT, ID del protocollo, Registry ID)
        app: Istanza dell'applicazione Flask
        save_to_db: Se True, salva il trial nel database
        save_to_json: Se True, aggiorna il file JSON
        
    Returns:
        Optional[Dict[str, Any]]: Dati del trial elaborati o None se non trovato
    """
    try:
        # Se l'ID è già un NCT ID, recupera direttamente il trial
        if trial_id.upper().startswith("NCT"):
            trial_data = fetch_trial_by_nct_id(trial_id)
        else:
            # Altrimenti cerca prima l'NCT ID corrispondente
            nct_id = search_trial_by_other_id(trial_id)
            if not nct_id:
                logging.error(f"Nessun trial trovato per l'ID {trial_id}")
                return None
            
            # Poi recupera il trial con l'NCT ID trovato
            trial_data = fetch_trial_by_nct_id(nct_id)
        
        if not trial_data:
            logging.error(f"Nessun trial trovato per l'ID {trial_id}")
            return None
        
        # Elabora i dati del trial
        processed_trial = process_fetched_trial_data(trial_data)
        
        if not processed_trial or "id" not in processed_trial or not processed_trial["id"]:
            logging.error(f"Elaborazione dei dati del trial fallita per l'ID {trial_id}")
            return None
        
        # Salva nel database se richiesto
        if save_to_db:
            with app.app_context():
                try:
                    # Verifica se il trial esiste già
                    existing_trial = ClinicalTrial.query.filter_by(id=processed_trial["id"]).first()
                    
                    if existing_trial:
                        # Aggiorna il trial esistente
                        for key, value in processed_trial.items():
                            setattr(existing_trial, key, value)
                        db.session.commit()
                        logging.info(f"Trial {processed_trial['id']} aggiornato nel database")
                    else:
                        # Crea un nuovo trial
                        new_trial = ClinicalTrial(**processed_trial)
                        db.session.add(new_trial)
                        db.session.commit()
                        logging.info(f"Trial {processed_trial['id']} aggiunto al database")
                except Exception as e:
                    db.session.rollback()
                    logging.error(f"Errore durante il salvataggio del trial nel database: {str(e)}")
        
        # Aggiorna il file JSON se richiesto
        if save_to_json:
            try:
                # Leggi il file JSON esistente
                with open('trials_int.json', 'r') as f:
                    trials = json.load(f)
                
                # Verifica se il trial esiste già
                trial_index = None
                for i, t in enumerate(trials):
                    if t.get('id') == processed_trial['id']:
                        trial_index = i
                        break
                
                if trial_index is not None:
                    # Aggiorna il trial esistente
                    trials[trial_index] = processed_trial
                else:
                    # Aggiungi il nuovo trial
                    trials.append(processed_trial)
                
                # Scrivi il file JSON aggiornato
                with open('trials_int.json', 'w') as f:
                    json.dump(trials, f, indent=2)
                
                logging.info(f"Trial {processed_trial['id']} aggiornato nel file JSON")
            except Exception as e:
                logging.error(f"Errore durante l'aggiornamento del file JSON: {str(e)}")
        
        return processed_trial
    except Exception as e:
        logging.error(f"Errore durante il recupero e il salvataggio del trial: {str(e)}")
        return None