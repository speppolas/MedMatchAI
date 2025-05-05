"""
Modulo per l'implementazione dell'approccio ibrido PostgreSQL + LLM.
Questo modulo fornisce funzionalità per il filtraggio iniziale tramite SQL 
e la successiva valutazione semantica tramite LLM.
"""

import os
import json
import logging
import re
from typing import Dict, List, Any, Tuple, Optional
from sqlalchemy import or_, and_, func, cast, String, Float, Integer
from sqlalchemy.sql.expression import literal

from models import ClinicalTrial, db
from app.llm_processor import get_llm_processor

# Configurazione del logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HybridQuery:
    """
    Classe per l'esecuzione di query ibride PostgreSQL + LLM.
    Questa classe implementa l'approccio di filtraggio in due fasi:
    1. Filtro rapido con PostgreSQL per criteri oggettivi
    2. Valutazione semantica con LLM per criteri soggettivi e complessi
    """
    
    def __init__(self):
        """Inizializza il processore di query ibrido."""
        self.llm = get_llm_processor()
        logger.info("Inizializzazione del sistema di query ibrido")
        
    def filter_trials_by_criteria(self, 
                                patient_features: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Filtra i trial clinici in base ai criteri del paziente usando un approccio ibrido.
        
        Args:
            patient_features: Caratteristiche estratte del paziente
            
        Returns:
            List[Dict[str, Any]]: Lista di trial clinici corrispondenti con valutazione
        """
        # Fase 1: Filtraggio basato su database per criteri oggettivi
        db_filtered_trials = self._filter_with_database(patient_features)
        
        logger.info(f"Filtro PostgreSQL: trovati {len(db_filtered_trials)} trial potenziali")
        
        if not db_filtered_trials:
            return []
        
        # Fase 2: Valutazione semantica con LLM per criteri complessi
        semantic_results = self._evaluate_with_llm(patient_features, db_filtered_trials)
        
        return semantic_results
    
    def _filter_with_database(self, 
                             patient_features: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Esegue il filtraggio iniziale basato su criteri oggettivi utilizzando SQL.
        
        Args:
            patient_features: Caratteristiche estratte del paziente
            
        Returns:
            List[Dict[str, Any]]: Lista di trial clinici che soddisfano i criteri di base
        """
        # Prepara le condizioni SQL in base alle caratteristiche del paziente
        conditions = []
        
        # Filtro per età (se disponibile)
        if 'age' in patient_features and patient_features['age'] is not None:
            if isinstance(patient_features['age'], dict) and 'value' in patient_features['age']:
                age = patient_features['age']['value']
            else:
                age = patient_features['age']
                
            if age and isinstance(age, (int, float)):
                # Filtra per età minima (se specificata nel trial)
                min_age_cond = or_(
                    ClinicalTrial.min_age.is_(None),  # No age restriction
                    ClinicalTrial.min_age == "",      # Empty string
                    func.regexp_replace(ClinicalTrial.min_age, r'[^0-9]', '', 'g').cast(Integer) <= age
                )
                conditions.append(min_age_cond)
                
                # Filtra per età massima (se specificata nel trial)
                max_age_cond = or_(
                    ClinicalTrial.max_age.is_(None),  # No age restriction
                    ClinicalTrial.max_age == "",      # Empty string
                    func.regexp_replace(ClinicalTrial.max_age, r'[^0-9]', '', 'g').cast(Integer) >= age
                )
                conditions.append(max_age_cond)
        
        # Filtro per genere (se disponibile)
        if 'gender' in patient_features and patient_features['gender'] is not None:
            if isinstance(patient_features['gender'], dict) and 'value' in patient_features['gender']:
                gender = patient_features['gender']['value']
            else:
                gender = patient_features['gender']
                
            if gender:
                # Map gender values to database format
                gender_map = {
                    'male': 'Male',
                    'female': 'Female',
                    'm': 'Male',
                    'f': 'Female'
                }
                mapped_gender = gender_map.get(gender.lower(), gender)
                
                gender_cond = or_(
                    ClinicalTrial.gender.is_(None),           # No gender restriction
                    ClinicalTrial.gender == "",               # Empty string
                    ClinicalTrial.gender == "All",            # All genders
                    ClinicalTrial.gender.ilike("both"),       # Both genders
                    ClinicalTrial.gender.ilike(f"%{mapped_gender}%")  # Specific gender
                )
                conditions.append(gender_cond)
        
        # Filtro per diagnosi (se disponibile)
        # Questo è più complesso e potrebbe richiedere un'analisi semantica,
        # ma possiamo fare un filtro preliminare basato su corrispondenze di parole chiave
        if 'diagnosis' in patient_features and patient_features['diagnosis'] is not None:
            if isinstance(patient_features['diagnosis'], dict) and 'value' in patient_features['diagnosis']:
                diagnosis = patient_features['diagnosis']['value']
            else:
                diagnosis = patient_features['diagnosis']
                
            if diagnosis and isinstance(diagnosis, str):
                # Estrai parole chiave dalla diagnosi
                keywords = self._extract_diagnosis_keywords(diagnosis)
                
                if keywords:
                    # Cerca le parole chiave nella descrizione del trial o nei criteri
                    diagnosis_conditions = []
                    for keyword in keywords:
                        if len(keyword) > 3:  # Ignora parole troppo corte
                            keyword_cond = or_(
                                ClinicalTrial.description.ilike(f"%{keyword}%"),
                                cast(ClinicalTrial.inclusion_criteria, String).ilike(f"%{keyword}%")
                            )
                            diagnosis_conditions.append(keyword_cond)
                    
                    if diagnosis_conditions:
                        # Almeno una parola chiave deve corrispondere
                        conditions.append(or_(*diagnosis_conditions))
        
        # Stato del trial (includi solo trial attivi)
        status_condition = or_(
            ClinicalTrial.status.ilike("Recruiting"),
            ClinicalTrial.status.ilike("Not yet recruiting"),
            ClinicalTrial.status.ilike("Active, not recruiting")
        )
        conditions.append(status_condition)
        
        # Esegui la query se ci sono condizioni
        if conditions:
            query = ClinicalTrial.query.filter(and_(*conditions))
            trials = query.all()
            
            # Converti i risultati in dizionari
            return [trial.to_dict() for trial in trials]
        else:
            # Se non ci sono condizioni, restituisci tutti i trial attivi
            query = ClinicalTrial.query.filter(status_condition)
            trials = query.all()
            return [trial.to_dict() for trial in trials]
    
    def _extract_diagnosis_keywords(self, diagnosis: str) -> List[str]:
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
    
    def _evaluate_with_llm(self, 
                         patient_features: Dict[str, Any], 
                         trials: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Valuta la compatibilità semantica tra paziente e trial utilizzando il LLM.
        
        Args:
            patient_features: Caratteristiche del paziente
            trials: Lista di trial già filtrati dal database
            
        Returns:
            List[Dict[str, Any]]: Trial valutati con punteggi e spiegazioni
        """
        results = []
        
        for trial in trials:
            # Usa l'LLM per valutare la compatibilità in modo più approfondito
            evaluation = self.llm.evaluate_trial_match(patient_features, trial)
            
            # Aggiungi il risultato della valutazione al trial
            trial_with_evaluation = {
                **trial,
                "semantic_match": evaluation.get("match"),
                "match_score": evaluation.get("score"),
                "match_explanation": evaluation.get("explanation"),
                "matching_criteria": evaluation.get("matching_criteria", []),
                "conflicting_criteria": evaluation.get("conflicting_criteria", [])
            }
            
            results.append(trial_with_evaluation)
        
        # Ordina i risultati per punteggio di compatibilità (se disponibile)
        if results and all(result.get("match_score") is not None for result in results):
            results.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        
        return results

# Funzione di comodo per ottenere una nuova istanza
def get_hybrid_query() -> HybridQuery:
    """
    Restituisce una nuova istanza di HybridQuery.
    
    Returns:
        HybridQuery: Una nuova istanza del query processor ibrido
    """
    return HybridQuery()