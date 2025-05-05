"""
Utilities per la gestione del database.

Questo modulo fornisce funzioni utility per le operazioni sul database PostgreSQL
usato in MedMatchINT. Include funzioni per l'inizializzazione, il popolamento
e la manutenzione del database.
"""

import os
import sys
import json
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import and_, or_, not_, cast, String, func
from sqlalchemy.dialects.postgresql import JSONB

# Aggiungi la directory principale al path per l'importazione dei moduli
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import db, ClinicalTrial

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database():
    """
    Inizializza il database creando le tabelle necessarie.
    Da chiamare all'interno di un contesto Flask.
    """
    try:
        db.create_all()
        logger.info("Database inizializzato con successo")
        return True
    except Exception as e:
        logger.error(f"Errore nell'inizializzazione del database: {str(e)}")
        return False

def load_trials_from_json(json_file='trials_int.json') -> List[Dict[str, Any]]:
    """
    Carica i trials da un file JSON.
    
    Args:
        json_file: Percorso al file JSON contenente i dati dei trial
        
    Returns:
        List[Dict[str, Any]]: Lista di trial in formato dizionario
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            trials = json.load(f)
        logger.info(f"Caricati {len(trials)} trial dal file {json_file}")
        return trials
    except Exception as e:
        logger.error(f"Errore nel caricamento del file JSON {json_file}: {str(e)}")
        return []

def save_trials_to_json(trials: List[Dict[str, Any]], json_file='trials_int.json') -> bool:
    """
    Salva i trial in un file JSON.
    
    Args:
        trials: Lista di trial da salvare
        json_file: Percorso dove salvare il file JSON
        
    Returns:
        bool: True se l'operazione è riuscita, False altrimenti
    """
    try:
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(trials, f, indent=2, ensure_ascii=False)
        logger.info(f"Salvati {len(trials)} trial nel file {json_file}")
        return True
    except Exception as e:
        logger.error(f"Errore nel salvataggio del file JSON {json_file}: {str(e)}")
        return False

def import_trials_to_db(trials: List[Dict[str, Any]]) -> bool:
    """
    Importa i trial nel database.
    Da chiamare all'interno di un contesto Flask.
    
    Args:
        trials: Lista di trial da importare
        
    Returns:
        bool: True se l'operazione è riuscita, False altrimenti
    """
    try:
        # Contatori per statistiche
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        for trial_data in trials:
            # Verifica se esiste già un trial con lo stesso ID
            existing_trial = ClinicalTrial.query.filter_by(id=trial_data['id']).first()
            
            if existing_trial:
                # Se il trial esiste già, aggiorna solo se il timestamp è più recente
                last_update_existing = existing_trial.last_update_submitted_date
                last_update_new = trial_data.get('last_update_submitted_date')
                
                if last_update_new and (not last_update_existing or last_update_new > last_update_existing):
                    # Aggiorna tutti i campi
                    for key, value in trial_data.items():
                        setattr(existing_trial, key, value)
                    updated_count += 1
                else:
                    skipped_count += 1
                    continue
            else:
                # Se il trial non esiste, creane uno nuovo
                new_trial = ClinicalTrial(**trial_data)
                db.session.add(new_trial)
                created_count += 1
            
            # Commit ogni 100 trial per evitare transazioni troppo grandi
            if (created_count + updated_count) % 100 == 0:
                db.session.commit()
                logger.info(f"Progresso: {created_count + updated_count}/{len(trials)} trial processati")
        
        # Commit finale
        db.session.commit()
        
        logger.info(f"Importazione completata: {created_count} trial creati, {updated_count} trial aggiornati, {skipped_count} trial invariati")
        return True
    except Exception as e:
        # In caso di errore, esegue rollback
        db.session.rollback()
        logger.error(f"Errore nell'importazione dei trial nel database: {str(e)}")
        return False

def get_all_trials_db() -> List[Dict[str, Any]]:
    """
    Ottiene tutti i trial clinici dal database.
    Da chiamare all'interno di un contesto Flask.
    
    Returns:
        List[Dict[str, Any]]: Lista di tutti i trial clinici
    """
    try:
        trials = ClinicalTrial.query.all()
        return [trial.to_dict() for trial in trials]
    except Exception as e:
        logger.error(f"Errore nel recupero dei trial dal database: {str(e)}")
        return []

def get_trial_by_id(trial_id: str) -> Optional[Dict[str, Any]]:
    """
    Cerca un trial specifico per ID.
    Da chiamare all'interno di un contesto Flask.
    
    Args:
        trial_id: ID del trial da cercare
        
    Returns:
        Optional[Dict[str, Any]]: Dati del trial trovato o None
    """
    try:
        # Normalizza l'ID per la ricerca
        normalized_id = trial_id.strip().upper()
        
        # Cerca per corrispondenza esatta dell'ID principale
        trial = ClinicalTrial.query.filter(func.upper(ClinicalTrial.id) == normalized_id).first()
        
        if trial:
            return trial.to_dict()
        
        # Cerca in ID dell'organizzazione
        trial = ClinicalTrial.query.filter(func.upper(ClinicalTrial.org_study_id) == normalized_id).first()
        
        if trial:
            return trial.to_dict()
        
        # Cerca negli ID secondari (più complesso perché è un campo JSONB)
        # Questa è una query complessa che dipende dal DB specifico
        # Usando PostgreSQL con SQLAlchemy:
        
        # Per prima cosa, ottieni tutti i trial
        all_trials = ClinicalTrial.query.all()
        
        # Cerca manualmente negli ID secondari
        for t in all_trials:
            if t.secondary_ids:
                for sec_id in t.secondary_ids:
                    if 'id' in sec_id and sec_id['id'].upper() == normalized_id:
                        return t.to_dict()
        
        return None
    except Exception as e:
        logger.error(f"Errore nella ricerca del trial con ID {trial_id}: {str(e)}")
        return None

def find_similar_trials(diagnosis: str, age: Optional[int] = None, gender: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Trova trial clinici simili basati su diagnosi, età e genere.
    Da chiamare all'interno di un contesto Flask.
    
    Args:
        diagnosis: Diagnosi del paziente
        age: Età del paziente (opzionale)
        gender: Genere del paziente (opzionale)
        
    Returns:
        List[Dict[str, Any]]: Lista di trial potenzialmente compatibili
    """
    try:
        # Inizia con una query di base
        query = ClinicalTrial.query
        
        # Aggiungi condizioni per i trial attivi
        query = query.filter(
            or_(
                ClinicalTrial.status.ilike("Recruiting"),
                ClinicalTrial.status.ilike("Not yet recruiting"),
                ClinicalTrial.status.ilike("Active, not recruiting")
            )
        )
        
        # Filtra per età se specificata
        if age is not None:
            query = query.filter(
                or_(
                    ClinicalTrial.min_age.is_(None),
                    ClinicalTrial.min_age == "",
                    func.regexp_replace(ClinicalTrial.min_age, r'[^0-9]', '', 'g').cast(String).cast(Integer) <= age
                )
            ).filter(
                or_(
                    ClinicalTrial.max_age.is_(None),
                    ClinicalTrial.max_age == "",
                    func.regexp_replace(ClinicalTrial.max_age, r'[^0-9]', '', 'g').cast(String).cast(Integer) >= age
                )
            )
        
        # Filtra per genere se specificato
        if gender is not None:
            gender_map = {
                'male': 'Male',
                'female': 'Female',
                'm': 'Male',
                'f': 'Female'
            }
            mapped_gender = gender_map.get(gender.lower(), gender)
            
            query = query.filter(
                or_(
                    ClinicalTrial.gender.is_(None),
                    ClinicalTrial.gender == "",
                    ClinicalTrial.gender == "All",
                    ClinicalTrial.gender.ilike("both"),
                    ClinicalTrial.gender.ilike(f"%{mapped_gender}%")
                )
            )
        
        # Estrai parole chiave dalla diagnosi per il filtraggio
        keywords = extract_diagnosis_keywords(diagnosis)
        
        # Filtra per parole chiave della diagnosi
        if keywords:
            keyword_conditions = []
            for keyword in keywords:
                if len(keyword) > 3:  # Ignora parole troppo corte
                    keyword_cond = or_(
                        ClinicalTrial.description.ilike(f"%{keyword}%"),
                        cast(ClinicalTrial.inclusion_criteria, String).ilike(f"%{keyword}%")
                    )
                    keyword_conditions.append(keyword_cond)
            
            if keyword_conditions:
                query = query.filter(or_(*keyword_conditions))
        
        # Esegui la query
        results = query.all()
        
        return [trial.to_dict() for trial in results]
    except Exception as e:
        logger.error(f"Errore nella ricerca di trial simili: {str(e)}")
        return []

def extract_diagnosis_keywords(diagnosis: str) -> List[str]:
    """
    Estrae parole chiave significative dalla diagnosi per il filtraggio.
    
    Args:
        diagnosis: Testo della diagnosi
        
    Returns:
        List[str]: Lista di parole chiave
    """
    # Rimuovi parole comuni non significative
    diagnosis = diagnosis.lower()
    stopwords = ['a', 'di', 'il', 'la', 'lo', 'gli', 'le', 'e', 'in', 'con', 'su', 'per', 
                'the', 'of', 'in', 'with', 'and', 'or', 'at', 'from', 'to', 
                'cancer', 'tumor', 'tumour', 'carcinoma', 'cancro', 'tumore']
    
    # Estrai terminologia specifica di oncologia
    cancer_types = [
        'lung', 'breast', 'colorectal', 'ovarian', 'prostate', 'pancreatic',
        'gastric', 'liver', 'hepatic', 'renal', 'bladder', 'melanoma', 'sarcoma',
        'lymphoma', 'leukemia', 'myeloma', 'glioma', 'polmone', 'mammella', 'colonretto',
        'ovaio', 'prostata', 'pancreas', 'stomaco', 'fegato', 'rene', 'vescica',
        'NSCLC', 'SCLC', 'HCC', 'RCC', 'DLBCL', 'AML', 'ALL', 'CLL', 'CML', 'MM'
    ]
    
    subtypes = [
        'adenocarcinoma', 'squamous', 'small cell', 'non-small cell',
        'ductal', 'lobular', 'neuroendocrine', 'transitional', 'papillary',
        'follicular', 'medullary', 'anaplastic', 'germ cell', 'seminoma',
        'non-seminoma', 'sarcomatoid', 'diffuse', 'hodgkin', 'non-hodgkin'
    ]
    
    modifiers = [
        'metastatic', 'advanced', 'refractory', 'recurrent', 'relapsed',
        'stage iv', 'stage iii', 'stage ii', 'stage i',
        'metastatico', 'avanzato', 'refrattario', 'recidivato', 'recidiva'
    ]
    
    # Cerca corrispondenze tra le parole chiave e la diagnosi
    keywords = []
    
    # Aggiungi tipi di cancro trovati
    for cancer_type in cancer_types:
        if cancer_type.lower() in diagnosis:
            keywords.append(cancer_type)
    
    # Aggiungi sottotipi trovati
    for subtype in subtypes:
        if subtype.lower() in diagnosis:
            keywords.append(subtype)
    
    # Aggiungi modificatori trovati
    for modifier in modifiers:
        if modifier.lower() in diagnosis:
            keywords.append(modifier)
    
    # Se non abbiamo trovato parole chiave specifiche, usa la diagnosi intera
    # ma rimuovi le stopwords
    if not keywords:
        words = diagnosis.split()
        keywords = [word for word in words if word.lower() not in stopwords and len(word) > 3]
    
    return keywords