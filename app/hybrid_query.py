"""
Modulo per l'implementazione dell'approccio ibrido PostgreSQL + LLM.
Questo modulo fornisce funzionalità per il filtraggio iniziale tramite SQL 
e la successiva valutazione semantica tramite LLM.
"""

import re
import logging
import json
from typing import Dict, Any, List, Optional, Set
import random
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.sql.expression import text

from models import ClinicalTrial, db
from app.llm_processor import get_llm_processor, LLM_AVAILABLE, LLM_ERROR_MESSAGE
from config import MIN_KEYWORD_MATCH_SCORE, MAX_TRIALS_TO_EVALUATE

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
        
    def filter_trials_by_criteria(self, 
                                patient_features: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Filtra i trial clinici in base ai criteri del paziente usando un approccio ibrido.
        
        Args:
            patient_features: Caratteristiche estratte del paziente
            
        Returns:
            List[Dict[str, Any]]: Lista di trial clinici corrispondenti con valutazione
        """
        logger.info("Inizio filtraggio trial con approccio ibrido")
        
        # Fase 1: Filtro iniziale con PostgreSQL
        filtered_trials = self._filter_with_database(patient_features)
        
        if not filtered_trials:
            logger.warning("Nessun trial trovato con il filtro PostgreSQL iniziale")
            return []
            
        logger.info(f"Filtro iniziale completato: {len(filtered_trials)} trial trovati")
        
        # Fase 2: Valutazione semantica con LLM
        evaluated_trials = self._evaluate_with_llm(patient_features, filtered_trials)
        
        # Ordina i trial per punteggio di compatibilità
        evaluated_trials.sort(key=lambda x: x.get('evaluation', {}).get('score', 0), reverse=True)
        
        logger.info(f"Valutazione semantica completata: {len(evaluated_trials)} trial valutati")
        
        return evaluated_trials
        
    def _filter_with_database(self, 
                             patient_features: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Esegue il filtraggio iniziale basato su criteri oggettivi utilizzando SQL.
        
        Args:
            patient_features: Caratteristiche estratte del paziente
            
        Returns:
            List[Dict[str, Any]]: Lista di trial clinici che soddisfano i criteri di base
        """
        logger.debug("Esecuzione filtro database")
        
        # Estrai i dati del paziente
        age = patient_features.get('age')
        gender = patient_features.get('gender', '').lower()
        diagnosis = patient_features.get('diagnosis', '')
        is_pediatric = age is not None and age < 18
        
        # Costruisci la query base
        query = db.session.query(ClinicalTrial)
        
        # Filtra per stato del trial (solo trial attivi)
        query = query.filter(
            sa.or_(
                ClinicalTrial.status == 'Recruiting',
                ClinicalTrial.status == 'Active, not recruiting',
                ClinicalTrial.status == 'Not yet recruiting'
            )
        )
        
        # Filtra per età se disponibile
        if age is not None:
            age_str = str(age)
            # Filtra per intervallo di età
            query = query.filter(
                sa.or_(
                    # Nessun limite di età specificato
                    ClinicalTrial.min_age.is_(None),
                    ClinicalTrial.min_age == '',
                    # Età minima specificata come numero
                    sa.and_(
                        ClinicalTrial.min_age.op('~')(r'^\d+'),
                        sa.cast(sa.func.regexp_replace(ClinicalTrial.min_age, r'[^0-9]', '', 'g'), sa.Integer) <= age
                    ),
                    # Età minima specificata come "X Years"/"X Anno" ecc.
                    sa.and_(
                        ClinicalTrial.min_age.op('~')(r'\d+\s*(Years|Year|Anni|Anno|Y)'),
                        sa.cast(sa.func.regexp_replace(ClinicalTrial.min_age, r'[^0-9]', '', 'g'), sa.Integer) <= age
                    )
                )
            )
            
            query = query.filter(
                sa.or_(
                    # Nessun limite massimo di età
                    ClinicalTrial.max_age.is_(None),
                    ClinicalTrial.max_age == '',
                    # Età massima specificata come numero
                    sa.and_(
                        ClinicalTrial.max_age.op('~')(r'^\d+'),
                        sa.cast(sa.func.regexp_replace(ClinicalTrial.max_age, r'[^0-9]', '', 'g'), sa.Integer) >= age
                    ),
                    # Età massima specificata come "X Years"/"X Anno" ecc.
                    sa.and_(
                        ClinicalTrial.max_age.op('~')(r'\d+\s*(Years|Year|Anni|Anno|Y)'),
                        sa.cast(sa.func.regexp_replace(ClinicalTrial.max_age, r'[^0-9]', '', 'g'), sa.Integer) >= age
                    ),
                    # "N/A" or "No limit"
                    ClinicalTrial.max_age.in_(['N/A', 'No limit', 'No Limit'])
                )
            )
        
        # Filtra per genere se disponibile
        if gender and gender not in ['unknown', 'altro', 'non specificato']:
            if gender in ['male', 'maschio', 'm']:
                query = query.filter(
                    sa.or_(
                        ClinicalTrial.gender.in_(['All', 'Male', 'Both', '']), 
                        ClinicalTrial.gender.is_(None)
                    )
                )
            elif gender in ['female', 'femmina', 'f']:
                query = query.filter(
                    sa.or_(
                        ClinicalTrial.gender.in_(['All', 'Female', 'Both', '']), 
                        ClinicalTrial.gender.is_(None)
                    )
                )
        
        # Se è un paziente pediatrico, cerca trial specifici per bambini
        if is_pediatric:
            # Prioritizzare i trial che sono specificamente per bambini
            # Non escludiamo altri trial in questa fase
            pass
            
        # Filtra per diagnosi/tumore se disponibile
        if diagnosis:
            # Estrai parole chiave significative dalla diagnosi
            keywords = self._extract_diagnosis_keywords(diagnosis)
            if keywords:
                # Costruisci un'espressione per cercare trial con parole chiave nella descrizione o nei criteri
                keyword_conditions = []
                for keyword in keywords:
                    keyword_lower = keyword.lower()
                    keyword_conditions.append(
                        sa.or_(
                            sa.func.lower(ClinicalTrial.title).contains(keyword_lower),
                            sa.func.lower(ClinicalTrial.description).contains(keyword_lower)
                        )
                    )
                
                # Aggiungi la condizione delle parole chiave alla query
                if keyword_conditions:
                    # Un trial deve contenere almeno una parola chiave
                    query = query.filter(sa.or_(*keyword_conditions))
        
        # Esegui la query
        filtered_trials = query.all()
        
        # Converti i risultati in dizionari per la successiva elaborazione
        trial_dicts = [trial.to_dict() for trial in filtered_trials]
        
        return trial_dicts
    
    def _extract_diagnosis_keywords(self, diagnosis: str) -> List[str]:
        """
        Estrae parole chiave significative dalla diagnosi per il filtraggio.
        
        Args:
            diagnosis: Testo della diagnosi
            
        Returns:
            List[str]: Lista di parole chiave
        """
        # Rimuovi numeri, punteggiatura e caratteri speciali
        cleaned_text = re.sub(r'[^\w\s]', ' ', diagnosis)
        cleaned_text = re.sub(r'\d+', ' ', cleaned_text)
        
        # Dividi in parole
        words = cleaned_text.split()
        
        # Parole da ignorare (stopwords)
        stopwords = set([
            'di', 'a', 'da', 'in', 'con', 'su', 'per', 'tra', 'fra', 'il', 'lo', 'la', 
            'i', 'gli', 'le', 'un', 'uno', 'una', 'e', 'o', 'ma', 'the', 'of', 'and',
            'to', 'in', 'that', 'is', 'was', 'for', 'on', 'are', 'with', 'they',
            'be', 'at', 'one', 'have', 'this', 'from', 'by', 'had', 'not', 'but',
            'what', 'all', 'were', 'when', 'we', 'there', 'can', 'an', 'your'
        ])
        
        # Filtra le parole troppo brevi o stopwords
        filtered_words = [word.lower() for word in words if len(word) > 2 and word.lower() not in stopwords]
        
        # Lista di nomi di tumori e termini oncologici rilevanti
        cancer_terms = set([
            'cancer', 'tumor', 'tumour', 'carcinoma', 'sarcoma', 'leukemia', 'leucemia',
            'lymphoma', 'linfoma', 'melanoma', 'blastoma', 'myeloma', 'mieloma',
            'adenocarcinoma', 'metastatic', 'metastatico', 'neoplasm', 'neoplasma',
            'malignant', 'maligno', 'oncology', 'oncologico'
        ])
        
        # Lista di siti anatomici comuni per tumori
        anatomical_sites = set([
            'lung', 'polmone', 'breast', 'seno', 'mammella', 'prostate', 'prostata',
            'colorectal', 'colon', 'retto', 'rectum', 'pancreas', 'liver', 'fegato',
            'ovarian', 'ovaio', 'cervical', 'cervice', 'uterine', 'utero', 'uterus',
            'brain', 'cervello', 'kidney', 'rene', 'bladder', 'vescica', 'gastric',
            'stomach', 'stomaco', 'esophageal', 'esofago', 'esophagus', 'head', 'testa',
            'neck', 'collo', 'thyroid', 'tiroide', 'skin', 'pelle', 'bone', 'osso',
            'testicular', 'testicolo', 'testes'
        ])
        
        # Dai priorità ai termini oncologici e siti anatomici
        prioritized_keywords = []
        other_keywords = []
        
        for word in filtered_words:
            if word in cancer_terms or word in anatomical_sites:
                prioritized_keywords.append(word)
            else:
                other_keywords.append(word)
        
        # Combina le parole chiave, dando priorità ai termini oncologici
        keywords = prioritized_keywords + other_keywords[:10]  # Limita le parole chiave generiche
        
        return keywords[:15]  # Limita il numero totale di parole chiave
        
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
        # Limita il numero di trial da valutare
        trials_to_evaluate = trials[:MAX_TRIALS_TO_EVALUATE]
        logger.info(f"Valutazione semantica di {len(trials_to_evaluate)} trial su {len(trials)} filtrati")
        
        # Valuta ogni trial utilizzando l'LLM
        evaluated_trials = []
        
        # Se l'LLM non è disponibile, utilizza un approccio basato su pattern
        if not LLM_AVAILABLE:
            logger.warning("LLM non disponibile, utilizzando valutazione basata su pattern")
            for trial in trials_to_evaluate:
                evaluation = self._evaluate_with_pattern_matching(patient_features, trial)
                trial_with_eval = trial.copy()
                trial_with_eval['evaluation'] = evaluation
                evaluated_trials.append(trial_with_eval)
        else:
            # Valuta ciascun trial con l'LLM
            for trial in trials_to_evaluate:
                evaluation = self.llm.evaluate_patient_trial_match(patient_features, trial)
                trial_with_eval = trial.copy()
                trial_with_eval['evaluation'] = evaluation
                evaluated_trials.append(trial_with_eval)
        
        return evaluated_trials
        
    def _evaluate_with_pattern_matching(self, 
                                      patient_features: Dict[str, Any], 
                                      trial: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valuta la compatibilità tra paziente e trial utilizzando pattern matching
        quando l'LLM non è disponibile.
        
        Args:
            patient_features: Caratteristiche del paziente
            trial: Dati del trial clinico
            
        Returns:
            Dict[str, Any]: Risultato della valutazione
        """
        # Implementazione di fallback basata su pattern matching
        
        # Estrai i dati del paziente
        age = patient_features.get('age')
        gender = patient_features.get('gender', '').lower()
        diagnosis = patient_features.get('diagnosis', '').lower()
        stage = patient_features.get('stage', '').lower()
        ecog = patient_features.get('ecog')
        mutations = patient_features.get('mutations', [])
        
        # Inizializza i contatori per criteri soddisfatti e non soddisfatti
        criteria_met = []
        criteria_not_met = []
        
        # Controlla l'età
        min_age = trial.get('min_age', '')
        max_age = trial.get('max_age', '')
        
        if age is not None:
            # Verifica età minima
            if min_age:
                try:
                    min_age_value = int(re.search(r'\d+', min_age).group(0))
                    if age < min_age_value:
                        criteria_not_met.append(f"Il paziente ha {age} anni, ma il trial richiede almeno {min_age_value} anni")
                    else:
                        criteria_met.append(f"Età minima soddisfatta: paziente {age} anni, minimo richiesto {min_age_value} anni")
                except (ValueError, AttributeError):
                    pass
            
            # Verifica età massima
            if max_age and max_age not in ['N/A', 'No limit', 'No Limit']:
                try:
                    max_age_value = int(re.search(r'\d+', max_age).group(0))
                    if age > max_age_value:
                        criteria_not_met.append(f"Il paziente ha {age} anni, ma il trial accetta fino a {max_age_value} anni")
                    else:
                        criteria_met.append(f"Età massima soddisfatta: paziente {age} anni, massimo accettato {max_age_value} anni")
                except (ValueError, AttributeError):
                    pass
        
        # Controlla il genere
        if gender and gender not in ['unknown', 'altro', 'non specificato']:
            trial_gender = trial.get('gender', '').lower()
            if trial_gender in ['all', 'both', '']:
                criteria_met.append("Genere: il trial accetta tutti i generi")
            elif (gender in ['male', 'maschio', 'm'] and trial_gender in ['male', 'uomo']) or \
                 (gender in ['female', 'femmina', 'f'] and trial_gender in ['female', 'donna']):
                criteria_met.append(f"Genere corrispondente: {gender}")
            elif trial_gender not in ['all', 'both', ''] and \
                 ((gender in ['male', 'maschio', 'm'] and trial_gender not in ['male', 'uomo']) or \
                  (gender in ['female', 'femmina', 'f'] and trial_gender not in ['female', 'donna'])):
                criteria_not_met.append(f"Genere non corrispondente: paziente {gender}, trial richiede {trial_gender}")
        
        # Verifica le corrispondenze nella diagnosi
        if diagnosis:
            trial_title = trial.get('title', '').lower()
            trial_desc = trial.get('description', '').lower()
            
            # Estrai parole chiave dalla diagnosi
            diagnosis_keywords = self._extract_diagnosis_keywords(diagnosis)
            
            matches = 0
            total_keywords = len(diagnosis_keywords)
            if total_keywords > 0:
                for keyword in diagnosis_keywords:
                    if keyword in trial_title or keyword in trial_desc:
                        matches += 1
                
                match_ratio = matches / total_keywords
                if match_ratio >= MIN_KEYWORD_MATCH_SCORE:
                    criteria_met.append(f"Diagnosi: {int(match_ratio*100)}% di corrispondenza delle parole chiave con il trial")
                else:
                    criteria_not_met.append(f"Possibile mancata corrispondenza della diagnosi ({int(match_ratio*100)}% parole chiave trovate)")
        
        # Cerca nel titolo e nella descrizione
        trial_text = (trial.get('title', '') + ' ' + trial.get('description', '')).lower()
        
        # Verifica ECOG
        if ecog is not None:
            ecog_patterns = [
                (r'ecog\s*performance\s*status\s*[<≤]\s*(\d+)', 'less_than'),
                (r'ecog\s*[<≤]\s*(\d+)', 'less_than'),
                (r'ecog\s*performance\s*status\s*of\s*(\d+)\s*or\s*less', 'less_than_equal'),
                (r'ecog\s*performance\s*status\s*[≤≦≠=]\s*(\d+)', 'equal'),
                (r'ecog\s*[=]\s*(\d+)', 'equal'),
                (r'ecog\s*performance\s*status\s*(\d+)[–-](\d+)', 'range'),
                (r'ecog\s*(\d+)[–-](\d+)', 'range')
            ]
            
            ecog_found = False
            for pattern, pattern_type in ecog_patterns:
                matches = re.search(pattern, trial_text)
                if matches:
                    ecog_found = True
                    if pattern_type == 'less_than':
                        max_allowed = int(matches.group(1))
                        if ecog < max_allowed:
                            criteria_met.append(f"ECOG soddisfatto: paziente {ecog}, trial richiede <{max_allowed}")
                        else:
                            criteria_not_met.append(f"ECOG non soddisfatto: paziente {ecog}, trial richiede <{max_allowed}")
                    elif pattern_type == 'less_than_equal':
                        max_allowed = int(matches.group(1))
                        if ecog <= max_allowed:
                            criteria_met.append(f"ECOG soddisfatto: paziente {ecog}, trial richiede ≤{max_allowed}")
                        else:
                            criteria_not_met.append(f"ECOG non soddisfatto: paziente {ecog}, trial richiede ≤{max_allowed}")
                    elif pattern_type == 'equal':
                        required = int(matches.group(1))
                        if ecog == required:
                            criteria_met.append(f"ECOG soddisfatto: paziente {ecog}, trial richiede ={required}")
                        else:
                            criteria_not_met.append(f"ECOG non soddisfatto: paziente {ecog}, trial richiede ={required}")
                    elif pattern_type == 'range':
                        min_range = int(matches.group(1))
                        max_range = int(matches.group(2))
                        if min_range <= ecog <= max_range:
                            criteria_met.append(f"ECOG soddisfatto: paziente {ecog}, trial accetta {min_range}-{max_range}")
                        else:
                            criteria_not_met.append(f"ECOG non soddisfatto: paziente {ecog}, trial accetta {min_range}-{max_range}")
                    break
            
            if not ecog_found and ecog <= 2:
                # Se non troviamo specifiche ECOG, assumiamo che ECOG ≤ 2 sia generalmente accettabile
                criteria_met.append(f"ECOG probabile: paziente {ecog}, probabilmente accettabile (≤2)")
            elif not ecog_found and ecog > 2:
                # Per ECOG > 2, inseriamo un avviso
                criteria_not_met.append(f"ECOG dubbio: paziente {ecog}, potrebbe non essere accettabile (>2)")
        
        # Cerca menzioni di mutazioni
        if mutations:
            mutation_found = False
            for mutation in mutations:
                mutation_lower = mutation.lower()
                if mutation_lower in trial_text:
                    mutation_found = True
                    criteria_met.append(f"Mutazione menzionata nel trial: {mutation}")
            
            if not mutation_found:
                criteria_not_met.append("Nessuna menzione specifica delle mutazioni del paziente nel trial")
        
        # Cerca menzioni dello stadio
        if stage:
            stage_patterns = [
                r'stage\s+' + re.escape(stage) + r'\b',
                r'stadio\s+' + re.escape(stage) + r'\b'
            ]
            
            stage_found = False
            for pattern in stage_patterns:
                if re.search(pattern, trial_text):
                    stage_found = True
                    criteria_met.append(f"Stadio menzionato nel trial: {stage}")
                    break
            
            if not stage_found:
                # Non lo consideriamo un criterio non soddisfatto, ma un'informazione mancante
                pass
        
        # Calcola il punteggio basato sui criteri
        total_criteria = len(criteria_met) + len(criteria_not_met)
        if total_criteria == 0:
            match_score = 50  # Punteggio neutro se non ci sono criteri
        else:
            match_score = int((len(criteria_met) / total_criteria) * 100)
        
        # Determina il tipo di match
        if match_score >= 80:
            match_type = "match"
        elif match_score >= 50:
            match_type = "maybe"
        else:
            match_type = "no_match"
        
        # Crea la spiegazione
        if len(criteria_met) > 0 and len(criteria_not_met) > 0:
            explanation = (
                f"Il paziente soddisfa {len(criteria_met)} criteri ma non soddisfa "
                f"{len(criteria_not_met)} criteri del trial."
            )
        elif len(criteria_met) > 0:
            explanation = f"Il paziente soddisfa tutti i {len(criteria_met)} criteri valutati."
        elif len(criteria_not_met) > 0:
            explanation = f"Il paziente non soddisfa nessuno dei {len(criteria_not_met)} criteri valutati."
        else:
            explanation = "Non è stato possibile valutare criteri specifici. Consultare un medico."
        
        # Crea il risultato della valutazione
        return {
            "match": match_type,
            "score": match_score,
            "explanation": explanation,
            "criteria_met": criteria_met,
            "criteria_not_met": criteria_not_met,
            "fallback_mode": True  # Indica che è stata utilizzata la modalità di fallback
        }


def get_hybrid_query() -> HybridQuery:
    """
    Restituisce una nuova istanza di HybridQuery.
    
    Returns:
        HybridQuery: Una nuova istanza del query processor ibrido
    """
    return HybridQuery()