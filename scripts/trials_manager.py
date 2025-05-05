"""
Gestore dei trial clinici per MedMatchINT.

Questo modulo fornisce funzionalità per recuperare, aggiornare e gestire i trial clinici,
inclusi il recupero da ClinicalTrials.gov e la normalizzazione dei dati.
"""

import os
import sys
import json
import logging
import re
import requests
import time
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

# Aggiungi la directory principale al path per l'importazione dei moduli
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.database_utils import load_trials_from_json, save_trials_to_json, import_trials_to_db

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# URL di base per le API di ClinicalTrials.gov
CTGOV_API_BASE = "https://clinicaltrials.gov/api/query/study_fields"
CTGOV_FULL_STUDY_BASE = "https://clinicaltrials.gov/api/query/full_studies"

# Campi da recuperare dall'API
DEFAULT_FIELDS = [
    "NCTId", "BriefTitle", "OfficialTitle", "OverallStatus", "StartDate", 
    "PrimaryCompletionDate", "CompletionDate", "StudyType", "Phase", 
    "DesignInterventionModel", "DetailedDescription", "BriefSummary",
    "Condition", "ConditionMeshTerm", "ConditionBrowseLeafName",
    "EligibilityCriteria", "EligibilityGender", "MinimumAge", "MaximumAge",
    "HealthyVolunteers", "StudyPopulation", "StudyArm", "InterventionType",
    "InterventionName", "InterventionDescription", "PrimaryOutcomeMeasure",
    "SecondaryOutcomeMeasure", "OrgStudyId", "SecondaryId", 
    "LastUpdatePostDate", "LeadSponsorName", "CentralContactName",
    "CentralContactPhone", "CentralContactEMail"
]

def fetch_trial_by_nct_id(nct_id: str) -> Optional[Dict[str, Any]]:
    """
    Recupera un trial clinico da ClinicalTrials.gov utilizzando l'ID NCT.
    
    Args:
        nct_id: ID NCT del trial da recuperare (es. NCT03334617)
        
    Returns:
        Optional[Dict[str, Any]]: Dati del trial in formato JSON o None se non trovato
    """
    try:
        # Rimuovi spazi e normalizza l'ID
        nct_id = nct_id.strip()
        
        # Controlla se l'ID è nel formato corretto NCT seguito da numeri
        if not re.match(r'^NCT\d+$', nct_id):
            logger.warning(f"Formato ID NCT non valido: {nct_id}")
            return None
        
        # URL per lo studio completo in formato JSON
        url = f"{CTGOV_FULL_STUDY_BASE}?expr={nct_id}&fmt=json"
        
        # Effettua la richiesta HTTP
        response = requests.get(url, timeout=30)
        
        # Verifica lo status della risposta
        if response.status_code != 200:
            logger.warning(f"Errore nell'API di ClinicalTrials.gov: {response.status_code}, {response.text}")
            return None
        
        # Elabora la risposta JSON
        data = response.json()
        
        # Verifica se sono stati trovati studi
        studies_count = data.get('FullStudiesResponse', {}).get('NStudiesFound', 0)
        if studies_count == 0:
            logger.warning(f"Nessun trial trovato con ID: {nct_id}")
            return None
        
        # Ottieni lo studio completo
        full_studies = data.get('FullStudiesResponse', {}).get('FullStudies', [])
        if not full_studies:
            logger.warning(f"Nessun dettaglio trovato per il trial: {nct_id}")
            return None
        
        # Estrai i dati dello studio completo
        study_data = full_studies[0].get('Study', {})
        if not study_data:
            logger.warning(f"Dati di studio non validi per: {nct_id}")
            return None
        
        # Processa i dati nello studio per ottenere un formato compatibile con l'applicazione
        processed_data = process_fetched_trial_data(study_data)
        
        return processed_data
    except requests.RequestException as e:
        logger.error(f"Errore nella richiesta HTTP a ClinicalTrials.gov: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Errore nel recupero del trial {nct_id}: {str(e)}")
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
        # Normalizza l'ID per la ricerca
        normalized_id = other_id.strip().replace("-", "").replace(" ", "")
        
        # URL per la ricerca di ID secondari o ID dell'organizzazione
        # NOTA: Per rendere la ricerca più specifica, è consigliabile usare il formato dei campi
        url = f"{CTGOV_API_BASE}?expr={other_id}&fields=NCTId,OrgStudyId,SecondaryId&fmt=json"
        
        # Effettua la richiesta HTTP
        response = requests.get(url, timeout=30)
        
        # Verifica lo status della risposta
        if response.status_code != 200:
            logger.warning(f"Errore nell'API di ClinicalTrials.gov: {response.status_code}, {response.text}")
            return None
        
        # Elabora la risposta JSON
        data = response.json()
        
        # Verifica se sono stati trovati studi
        studies_count = data.get('StudyFieldsResponse', {}).get('NStudiesFound', 0)
        if studies_count == 0:
            logger.warning(f"Nessun trial trovato con ID: {other_id}")
            return None
        
        # Ottieni i dati degli studi
        studies = data.get('StudyFieldsResponse', {}).get('StudyFields', [])
        if not studies:
            logger.warning(f"Nessun dettaglio trovato per il trial con ID: {other_id}")
            return None
        
        # Cerca una corrispondenza tra gli ID degli studi
        for study in studies:
            # Controlla nell'ID dell'organizzazione
            org_ids = study.get('OrgStudyId', [])
            for org_id in org_ids:
                if other_id.lower() in org_id.lower() or normalized_id.lower() in org_id.lower().replace("-", "").replace(" ", ""):
                    nct_id = study.get('NCTId', [])
                    return nct_id[0] if nct_id else None
            
            # Controlla negli ID secondari
            secondary_ids = study.get('SecondaryId', [])
            for sec_id in secondary_ids:
                if other_id.lower() in sec_id.lower() or normalized_id.lower() in sec_id.lower().replace("-", "").replace(" ", ""):
                    nct_id = study.get('NCTId', [])
                    return nct_id[0] if nct_id else None
        
        return None
    except requests.RequestException as e:
        logger.error(f"Errore nella richiesta HTTP a ClinicalTrials.gov: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Errore nella ricerca del trial con ID {other_id}: {str(e)}")
        return None

def determine_id_type(trial_id: str) -> str:
    """
    Determina il tipo di ID fornito per ottimizzare la ricerca.
    
    Args:
        trial_id: ID del trial da analizzare
        
    Returns:
        str: Tipo di ID (NCT, PROTOCOL, EUDRACT, REGISTRY, OTHER)
    """
    # Rimuovi spazi e normalizza
    normalized_id = trial_id.strip()
    
    # Verifica se è un ID NCT
    if re.match(r'^NCT\d+$', normalized_id):
        return "NCT"
    
    # Verifica se è un ID di protocollo di sponsor (es. D5087C00001)
    if re.match(r'^[A-Z]\d+[A-Z]\d+$', normalized_id) or re.match(r'^[A-Z]\d+-\d+$', normalized_id):
        return "PROTOCOL"
    
    # Verifica se è un ID EudraCT (formato: YYYY-NNNNNN-CC)
    if re.match(r'^\d{4}-\d{6}-\d{2}$', normalized_id):
        return "EUDRACT"
    
    # Verifica se è un altro tipo di ID di registro (numeri/lettere con trattini)
    if re.match(r'^[\w\d]+-[\w\d]+$', normalized_id) and len(normalized_id) > 8:
        return "REGISTRY"
    
    # Altri tipi di ID
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
        # Estrai i dati identificativi
        identification = trial_data.get('ProtocolSection', {}).get('IdentificationModule', {})
        nct_id = identification.get('NCTId', '')
        org_study_id = identification.get('OrgStudyId', '')
        
        # Estrai i titoli
        title = identification.get('BriefTitle', '')
        official_title = identification.get('OfficialTitle', '')
        
        # Estrai lo stato
        status_data = trial_data.get('ProtocolSection', {}).get('StatusModule', {})
        status = status_data.get('OverallStatus', '')
        start_date = status_data.get('StartDate', '')
        completion_date = status_data.get('PrimaryCompletionDate', '')
        
        # Estrai la fase
        design_module = trial_data.get('ProtocolSection', {}).get('DesignModule', {})
        phase = design_module.get('PhaseList', {}).get('Phase', [])
        phase_text = '/'.join(phase) if isinstance(phase, list) else phase
        
        # Estrai la descrizione
        description_module = trial_data.get('ProtocolSection', {}).get('DescriptionModule', {})
        detailed_description = description_module.get('DetailedDescription', '')
        brief_summary = description_module.get('BriefSummary', '')
        
        # Estrai le condizioni
        condition_module = trial_data.get('ProtocolSection', {}).get('ConditionsModule', {})
        conditions = condition_module.get('ConditionList', {}).get('Condition', [])
        
        # Estrai i criteri di idoneità
        eligibility_module = trial_data.get('ProtocolSection', {}).get('EligibilityModule', {})
        eligibility_criteria = eligibility_module.get('EligibilityCriteria', '')
        gender = eligibility_module.get('Gender', '')
        min_age = eligibility_module.get('MinimumAge', '')
        max_age = eligibility_module.get('MaximumAge', '')
        
        # Estrai i dati di contatto
        contacts_module = trial_data.get('ProtocolSection', {}).get('ContactsLocationsModule', {})
        central_contacts = contacts_module.get('CentralContactList', {}).get('CentralContact', [])
        central_contact = central_contacts[0] if central_contacts else {}
        
        # Estrai gli sponsor
        sponsor_module = trial_data.get('ProtocolSection', {}).get('SponsorCollaboratorsModule', {})
        lead_sponsor = sponsor_module.get('LeadSponsor', {}).get('LeadSponsorName', '')
        
        # Estrai gli ID secondari
        ids_module = trial_data.get('ProtocolSection', {}).get('IdentificationModule', {})
        secondary_ids_raw = ids_module.get('SecondaryIdList', {}).get('SecondaryId', [])
        secondary_ids = []
        
        if not isinstance(secondary_ids_raw, list):
            secondary_ids_raw = [secondary_ids_raw]
            
        for sec_id in secondary_ids_raw:
            if isinstance(sec_id, dict) and 'SecondaryIdType' in sec_id and 'SecondaryIdDomain' in sec_id:
                secondary_ids.append({
                    'id': sec_id.get('SecondaryId', ''),
                    'type': sec_id.get('SecondaryIdType', ''),
                    'domain': sec_id.get('SecondaryIdDomain', '')
                })
            elif isinstance(sec_id, str):
                secondary_ids.append({
                    'id': sec_id,
                    'type': 'Other',
                    'domain': 'Other'
                })
        
        # Estrai e struttura i criteri di inclusione ed esclusione
        inclusion_criteria, exclusion_criteria = extract_inclusion_exclusion_criteria(eligibility_criteria)
        
        # Costruisci il dizionario finale
        trial_processed = {
            'id': nct_id,
            'org_study_id': org_study_id,
            'secondary_ids': secondary_ids,
            'title': title,
            'official_title': official_title,
            'status': status,
            'phase': phase_text,
            'start_date': start_date,
            'completion_date': completion_date,
            'description': detailed_description or brief_summary,
            'conditions': conditions if isinstance(conditions, list) else [conditions],
            'inclusion_criteria': inclusion_criteria,
            'exclusion_criteria': exclusion_criteria,
            'gender': gender,
            'min_age': min_age,
            'max_age': max_age,
            'sponsor': lead_sponsor,
            'contact_name': central_contact.get('CentralContactName', ''),
            'contact_email': central_contact.get('CentralContactEMail', ''),
            'contact_phone': central_contact.get('CentralContactPhone', ''),
            'last_update_submitted_date': status_data.get('LastUpdateSubmitDate', ''),
            'last_update_posted_date': status_data.get('LastUpdatePostDate', '')
        }
        
        # Special case for D5087C00001 / NCT05261399 (SAFFRON trial)
        # Questo è un fix specifico richiesto per associare correttamente il trial SAFFRON
        # Inserisci qui eventuali mappature speciali
        if org_study_id == "D5087C00001" or "D5087C00001" in str(secondary_ids):
            trial_processed['protocol_ids'] = ["D5087C00001", "HUDSON"]
            # Aggiungi altre informazioni specifiche se necessario
        
        return trial_processed
    except Exception as e:
        logger.error(f"Errore nell'elaborazione dei dati del trial: {str(e)}")
        return {}

def extract_inclusion_exclusion_criteria(criteria_text: str) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """
    Estrae i criteri di inclusione ed esclusione dal testo completo dei criteri di idoneità.
    
    Args:
        criteria_text: Testo completo dei criteri di idoneità
        
    Returns:
        Tuple[List[Dict[str, str]], List[Dict[str, str]]]: (criteri di inclusione, criteri di esclusione)
    """
    if not criteria_text:
        return [], []
    
    # Individua le sezioni di inclusione ed esclusione
    inclusion_section = ""
    exclusion_section = ""
    
    # Pattern comuni per identificare le sezioni
    inclusion_patterns = [
        r'(?i)inclusion criteria[:\s-]*\n*(.*?)(?=(?:\n\s*\n*exclusion criteria)|$)',
        r'(?i)criteria for eligibility[:\s-]*\n*(.*?)(?=(?:\n\s*\n*criteria for exclusion)|$)',
        r'(?i)subjects must[:\s-]*\n*(.*?)(?=(?:\n\s*\n*subjects must not)|$)'
    ]
    
    exclusion_patterns = [
        r'(?i)exclusion criteria[:\s-]*\n*(.*?)$',
        r'(?i)criteria for exclusion[:\s-]*\n*(.*?)$',
        r'(?i)subjects must not[:\s-]*\n*(.*?)$'
    ]
    
    # Cerca la sezione di inclusione
    for pattern in inclusion_patterns:
        match = re.search(pattern, criteria_text, re.DOTALL)
        if match:
            inclusion_section = match.group(1).strip()
            break
    
    # Cerca la sezione di esclusione
    for pattern in exclusion_patterns:
        match = re.search(pattern, criteria_text, re.DOTALL)
        if match:
            exclusion_section = match.group(1).strip()
            break
    
    # Se non sono state trovate sezioni, utilizza l'intero testo
    if not inclusion_section and not exclusion_section:
        # Prova a identificare in base ai punti elenco e alle parole chiave
        lines = criteria_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Cerca parole chiave che indicano inclusione o esclusione
            if (re.search(r'\b(?:must|eligible|including|have|be)\b', line.lower()) and
                not re.search(r'\b(?:not|non|exclude|exclusion|ineligible)\b', line.lower())):
                inclusion_section += line + '\n'
            elif re.search(r'\b(?:not|exclude|exclusion|ineligible|contraindication)\b', line.lower()):
                exclusion_section += line + '\n'
            else:
                # Se non ci sono indicazioni chiare, considera come inclusione
                inclusion_section += line + '\n'
    
    # Processa i criteri
    inclusion_criteria = process_criteria(inclusion_section, 'inclusion')
    exclusion_criteria = process_criteria(exclusion_section, 'exclusion')
    
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
    
    # Divide in punti elenco basati su vari separatori
    criteria_items = []
    
    # Pattern per identificare punti elenco
    bullet_patterns = [
        r'(?:^|\n)\s*[-•*]\s*(.*?)(?=(?:\n\s*[-•*])|$)',  # Trattini, punti elenco
        r'(?:^|\n)\s*\d+\.\s*(.*?)(?=(?:\n\s*\d+\.)|$)',  # Numeri ordinali
        r'(?:^|\n)\s*[a-z](?:\)|\.)?\s*(.*?)(?=(?:\n\s*[a-z](?:\)|\.))|$)',  # Lettere minuscole
        r'(?:^|\n)\s*[A-Z](?:\)|\.)?\s*(.*?)(?=(?:\n\s*[A-Z](?:\)|\.))|$)'   # Lettere maiuscole
    ]
    
    # Cerca i pattern di punti elenco
    items_found = False
    for pattern in bullet_patterns:
        items = re.findall(pattern, criteria_text, re.DOTALL)
        if items:
            items_found = True
            for item in items:
                item = item.strip()
                if item:
                    criteria_items.append({
                        'text': item,
                        'type': identify_criterion_type(item, criteria_type)
                    })
    
    # Se non sono stati trovati punti elenco, utilizza l'intero testo o dividilo per righe
    if not items_found:
        # Verifica se ci sono punti fermi che potrebbero indicare criteri separati
        if re.search(r'\.\s+[A-Z]', criteria_text):
            sentences = re.split(r'\.\s+(?=[A-Z])', criteria_text)
            for sentence in sentences:
                sentence = sentence.strip()
                if sentence:
                    criteria_items.append({
                        'text': sentence + '.',
                        'type': identify_criterion_type(sentence, criteria_type)
                    })
        else:
            # Usa l'intero testo come unico criterio
            criteria_items.append({
                'text': criteria_text,
                'type': identify_criterion_type(criteria_text, criteria_type)
            })
    
    return criteria_items

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
    
    # Tipo di criterio più specifico basato sulle parole chiave
    if re.search(r'\bage\b|\byears\b|\byear old\b', text_lower):
        return f"{default_type}_age"
    elif re.search(r'\bgender\b|\bsex\b|\bmale\b|\bfemale\b', text_lower):
        return f"{default_type}_gender"
    elif re.search(r'\bcancer\b|\btumor\b|\bcarcinoma\b|\bmalignancy\b|\bneoplasm\b', text_lower):
        return f"{default_type}_diagnosis"
    elif re.search(r'\bstage\b|\bgrading\b|\bgrade\b|\bTNM\b', text_lower):
        return f"{default_type}_stage"
    elif re.search(r'\bECOG\b|\bperformance status\b|\bKarnofsky\b|\bPS\b', text_lower):
        return f"{default_type}_performance_status"
    elif re.search(r'\bmutation\b|\bgene\b|\bmolecular\b|\bBRAF\b|\bEGFR\b|\bHER2\b|\bALK\b|\bROS1\b', text_lower):
        return f"{default_type}_mutation"
    elif re.search(r'\bmetastasis\b|\bmetastatic\b|\bmetastases\b|\badvanced\b', text_lower):
        return f"{default_type}_metastasis"
    elif re.search(r'\bpregnancy\b|\bpregnant\b|\blactating\b|\bbreastfeeding\b', text_lower):
        return f"{default_type}_pregnancy"
    elif re.search(r'\btreatment\b|\btherapy\b|\bmedication\b|\bregimen\b', text_lower):
        return f"{default_type}_treatment"
    elif re.search(r'\blaboratory\b|\blab\b|\bblood\b|\bhematology\b|\bchemistry\b', text_lower):
        return f"{default_type}_lab_value"
    elif re.search(r'\borgan\b|\bcardiac\b|\bheart\b|\brenal\b|\bkidney\b|\bliver\b|\bhepatic\b|\blung\b', text_lower):
        return f"{default_type}_organ_function"
    elif re.search(r'\bconsent\b|\bwilling\b|\bagree\b|\bable\b', text_lower):
        return f"{default_type}_consent"
    elif re.search(r'\bcomorbidity\b|\bcomorbid\b|\bdisease\b|\bmedical history\b', text_lower):
        return f"{default_type}_comorbidity"
    
    # Tipo predefinito
    return default_type

def fetch_and_save_trial_by_id(trial_id: str, save_to_db: bool = True, save_to_json: bool = True) -> Optional[Dict[str, Any]]:
    """
    Recupera un trial clinico da ClinicalTrials.gov in base all'ID e lo salva nel database e/o nel file JSON.
    
    Args:
        trial_id: ID del trial da recuperare (NCT, EudraCT, ID del protocollo, Registry ID)
        save_to_db: Se True, salva il trial nel database
        save_to_json: Se True, aggiorna il file JSON
        
    Returns:
        Optional[Dict[str, Any]]: Dati del trial elaborati o None se non trovato
    """
    try:
        # Normalizza l'ID
        normalized_id = trial_id.strip()
        
        # Determina il tipo di ID
        id_type = determine_id_type(normalized_id)
        
        # Variabile per memorizzare l'ID NCT
        nct_id = None
        
        # Gestisci in base al tipo di ID
        if id_type == "NCT":
            nct_id = normalized_id
        else:
            # Cerca l'ID NCT basato sull'ID alternativo
            nct_id = search_trial_by_other_id(normalized_id)
            
            if not nct_id:
                logger.warning(f"Impossibile trovare l'ID NCT per: {normalized_id}")
                return None
        
        # Recupera i dati completi del trial utilizzando l'ID NCT
        trial_data = fetch_trial_by_nct_id(nct_id)
        
        if not trial_data:
            logger.warning(f"Impossibile recuperare i dati del trial con ID NCT: {nct_id}")
            return None
        
        # Applica correzioni specifiche se necessario
        # Esempio: correggi informazioni per D5087C00001 / SAFFRON trial
        if normalized_id == "D5087C00001" or (trial_data.get('org_study_id') == "D5087C00001"):
            # Assicurati che l'ID del protocollo sia presente
            if 'protocol_ids' not in trial_data:
                trial_data['protocol_ids'] = ["D5087C00001", "HUDSON"]
            
            # Aggiungi altre correzioni specifiche se necessario
        
        # Salva nel database se richiesto
        if save_to_db:
            from flask import current_app
            with current_app.app_context():
                single_trial_list = [trial_data]
                success = import_trials_to_db(single_trial_list)
                if not success:
                    logger.warning(f"Errore nel salvataggio del trial nel database: {nct_id}")
        
        # Aggiorna il file JSON se richiesto
        if save_to_json:
            # Carica i trial esistenti
            existing_trials = load_trials_from_json()
            
            # Rimuovi il trial con lo stesso ID se presente
            existing_trials = [t for t in existing_trials if t.get('id') != trial_data.get('id')]
            
            # Aggiungi il nuovo trial
            existing_trials.append(trial_data)
            
            # Salva il file aggiornato
            success = save_trials_to_json(existing_trials)
            if not success:
                logger.warning(f"Errore nel salvataggio del file JSON dopo l'aggiornamento del trial: {nct_id}")
        
        return trial_data
    except Exception as e:
        logger.error(f"Errore nel processo di recupero e salvataggio del trial {trial_id}: {str(e)}")
        return None

def update_trials(search_terms: List[str] = None, max_trials: int = 100) -> bool:
    """
    Aggiorna i trial clinici nel database e nel file JSON, recuperandoli da ClinicalTrials.gov.
    
    Args:
        search_terms: Lista di termini di ricerca (es. ["lung cancer", "NSCLC"])
        max_trials: Numero massimo di trial da recuperare per termine di ricerca
        
    Returns:
        bool: True se l'aggiornamento è riuscito, False altrimenti
    """
    try:
        # Termini di ricerca predefiniti se non specificati
        if not search_terms:
            search_terms = [
                "lung cancer", "NSCLC", "breast cancer", "colorectal cancer",
                "prostate cancer", "melanoma", "ovarian cancer", "pancreatic cancer",
                "gastric cancer", "liver cancer", "renal cell carcinoma"
            ]
        
        # Lista per memorizzare i trial recuperati
        all_trials = []
        
        # Per ogni termine di ricerca
        for term in search_terms:
            logger.info(f"Recupero trial per: {term}")
            
            # Costruisci URL di ricerca per i campi di studio
            # Filtri: solo trial attivi o in reclutamento, solo trial di intervento
            fields_param = ",".join(DEFAULT_FIELDS)
            url = f"{CTGOV_API_BASE}?expr={term}+AND+AREA[OverallStatus]EXPAND[Term]RANGE[active,recruiting,not yet recruiting]&fields={fields_param}&fmt=json&max_rnk={max_trials}"
            
            try:
                # Effettua la richiesta HTTP
                response = requests.get(url, timeout=60)
                
                # Verifica lo status della risposta
                if response.status_code != 200:
                    logger.warning(f"Errore nell'API di ClinicalTrials.gov per {term}: {response.status_code}, {response.text}")
                    continue
                
                # Elabora la risposta JSON
                data = response.json()
                
                # Verifica se sono stati trovati studi
                studies_count = data.get('StudyFieldsResponse', {}).get('NStudiesFound', 0)
                if studies_count == 0:
                    logger.warning(f"Nessun trial trovato per: {term}")
                    continue
                
                # Estrai i dati degli studi
                studies = data.get('StudyFieldsResponse', {}).get('StudyFields', [])
                if not studies:
                    logger.warning(f"Nessun dettaglio trovato per i trial di: {term}")
                    continue
                
                logger.info(f"Trovati {len(studies)} trial per: {term}")
                
                # Processa ogni studio
                for study in studies:
                    # Estrai e trasforma i dati del trial
                    processed_study = process_study_fields(study)
                    
                    if processed_study:
                        # Recupera i dati completi per ogni studio utilizzando l'ID NCT
                        nct_id = processed_study.get('id')
                        if nct_id:
                            try:
                                full_study = fetch_trial_by_nct_id(nct_id)
                                if full_study:
                                    all_trials.append(full_study)
                            except Exception as study_error:
                                logger.warning(f"Errore nel recupero dei dati completi per {nct_id}: {str(study_error)}")
                                # Utilizza i dati parziali se non è possibile recuperare i dati completi
                                all_trials.append(processed_study)
                
                # Aggiungi un ritardo per evitare di sovraccaricare l'API
                time.sleep(1)
                
            except requests.RequestException as e:
                logger.error(f"Errore nella richiesta HTTP per {term}: {str(e)}")
            except Exception as e:
                logger.error(f"Errore generico nell'elaborazione dei trial per {term}: {str(e)}")
        
        # Rimuovi duplicati basati sull'ID NCT
        unique_trials = []
        seen_ids = set()
        
        for trial in all_trials:
            trial_id = trial.get('id')
            if trial_id and trial_id not in seen_ids:
                seen_ids.add(trial_id)
                unique_trials.append(trial)
        
        logger.info(f"Recuperati {len(unique_trials)} trial unici in totale")
        
        # Salva i trial nel database
        from flask import current_app
        with current_app.app_context():
            success_db = import_trials_to_db(unique_trials)
            if not success_db:
                logger.warning("Errore nel salvataggio dei trial nel database")
        
        # Aggiorna il file JSON
        success_json = save_trials_to_json(unique_trials)
        if not success_json:
            logger.warning("Errore nel salvataggio dei trial nel file JSON")
        
        return success_db and success_json
    except Exception as e:
        logger.error(f"Errore nell'aggiornamento dei trial: {str(e)}")
        return False

def process_study_fields(study_fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processa i campi di uno studio recuperato dall'API di ClinicalTrials.gov.
    
    Args:
        study_fields: Dati grezzi dello studio da ClinicalTrials.gov
        
    Returns:
        Dict[str, Any]: Dati dello studio elaborati nel formato richiesto dall'applicazione
    """
    try:
        # Estrai i campi principali, gestendo array singoli
        nct_id = study_fields.get('NCTId', [''])[0] if study_fields.get('NCTId') else ''
        title = study_fields.get('BriefTitle', [''])[0] if study_fields.get('BriefTitle') else ''
        official_title = study_fields.get('OfficialTitle', [''])[0] if study_fields.get('OfficialTitle') else ''
        status = study_fields.get('OverallStatus', [''])[0] if study_fields.get('OverallStatus') else ''
        phase = study_fields.get('Phase', [''])[0] if study_fields.get('Phase') else ''
        description = study_fields.get('DetailedDescription', [''])[0] if study_fields.get('DetailedDescription') else ''
        
        if not description:
            description = study_fields.get('BriefSummary', [''])[0] if study_fields.get('BriefSummary') else ''
        
        gender = study_fields.get('EligibilityGender', [''])[0] if study_fields.get('EligibilityGender') else ''
        min_age = study_fields.get('MinimumAge', [''])[0] if study_fields.get('MinimumAge') else ''
        max_age = study_fields.get('MaximumAge', [''])[0] if study_fields.get('MaximumAge') else ''
        
        # Estrai i criteri di idoneità
        criteria_text = study_fields.get('EligibilityCriteria', [''])[0] if study_fields.get('EligibilityCriteria') else ''
        inclusion_criteria, exclusion_criteria = extract_inclusion_exclusion_criteria(criteria_text)
        
        # Estrai le condizioni (malattie)
        conditions = study_fields.get('Condition', []) if study_fields.get('Condition') else []
        
        # Estrai gli ID secondari e dell'organizzazione
        org_study_id = study_fields.get('OrgStudyId', [''])[0] if study_fields.get('OrgStudyId') else ''
        secondary_ids_raw = study_fields.get('SecondaryId', []) if study_fields.get('SecondaryId') else []
        secondary_ids = [{'id': sec_id, 'type': 'Other', 'domain': 'Other'} for sec_id in secondary_ids_raw]
        
        # Costruisci il dizionario finale
        processed_study = {
            'id': nct_id,
            'org_study_id': org_study_id,
            'secondary_ids': secondary_ids,
            'title': title,
            'official_title': official_title,
            'status': status,
            'phase': phase,
            'description': description,
            'conditions': conditions,
            'inclusion_criteria': inclusion_criteria,
            'exclusion_criteria': exclusion_criteria,
            'gender': gender,
            'min_age': min_age,
            'max_age': max_age
        }
        
        # Special case for D5087C00001 / NCT05261399 (SAFFRON trial)
        if org_study_id == "D5087C00001" or "D5087C00001" in str(secondary_ids):
            processed_study['protocol_ids'] = ["D5087C00001", "HUDSON"]
        
        return processed_study
    except Exception as e:
        logger.error(f"Errore nell'elaborazione dei campi dello studio: {str(e)}")
        return {}