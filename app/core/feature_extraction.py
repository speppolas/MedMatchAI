"""
Modulo per l'estrazione di caratteristiche cliniche da documenti del paziente.

Questo modulo fornisce funzionalità per estrarre informazioni cliniche rilevanti dai 
documenti dei pazienti, utilizzando vari approcci che vanno dall'uso di un LLM locale
all'analisi basata su pattern con espressioni regolari.
"""

import os
import sys
import re
import json
import logging
import requests
import pdfplumber
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta

# Aggiungi la directory principale al path per l'importazione dei moduli
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_file: Union[str, bytes]) -> str:
    """
    Estrae il testo da un file PDF utilizzando pdfplumber.
    
    Args:
        pdf_file: Percorso al file PDF o oggetto file dal form di upload
        
    Returns:
        str: Testo estratto dal PDF
    """
    try:
        # Determina se l'input è un percorso di file o un oggetto file
        if isinstance(pdf_file, str):
            # È un percorso di file
            with pdfplumber.open(pdf_file) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""
                return text
        else:
            # È un oggetto file da request.files
            with pdfplumber.open(pdf_file) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""
                return text
    except Exception as e:
        logger.error(f"Errore nell'estrazione del testo dal PDF: {str(e)}")
        raise Exception(f"Impossibile estrarre testo dal PDF: {str(e)}")

def extract_features(text: str) -> Dict[str, Any]:
    """
    Estrae caratteristiche cliniche dal testo utilizzando vari approcci.
    
    L'estrazione avviene in questo ordine di priorità:
    1. LLM locale tramite llama.cpp (se configurato)
    2. Ollama (se disponibile sulla macchina)
    3. Estrazione di base con espressioni regolari (fallback)
    
    Args:
        text: Il testo da analizzare
        
    Returns:
        dict: Caratteristiche cliniche estratte in formato JSON
    """
    try:
        # Prova prima con llama.cpp se configurato
        try:
            from app.llm_processor import get_llm_processor, LLM_AVAILABLE
            if LLM_AVAILABLE:
                llm = get_llm_processor()
                features = llm.extract_patient_features(text)
                logger.info("Caratteristiche estratte con successo utilizzando llama.cpp")
                return features
            else:
                logger.info("llama.cpp non disponibile, provo con Ollama...")
        except Exception as llm_error:
            logger.warning(f"Errore nell'utilizzo di llama.cpp: {str(llm_error)}")
            
        # Prova con Ollama
        features = extract_with_ollama(text)
        
        # Se Ollama non è disponibile, usa l'estrazione di base
        if not features:
            logger.info("Ollama non disponibile, utilizzo estrazione di base")
            features = basic_feature_extraction(text)
            
        return features
    except Exception as e:
        logger.error(f"Errore nell'estrazione delle caratteristiche: {str(e)}")
        # Fallback all'estrazione di base in caso di errore
        logger.info("Fallback all'estrazione di base a causa di un errore")
        return basic_feature_extraction(text)

def format_features_concise(features: Dict[str, Any]) -> Dict[str, Any]:
    """
    Formatta le caratteristiche estratte in modo conciso per la visualizzazione.
    
    Questa funzione elabora le caratteristiche estratte dal testo del paziente
    per renderle più concise e leggibili nell'interfaccia utente. Rimuove le informazioni
    di contesto e il testo sorgente completo, mantenendo solo i valori essenziali.
    
    Args:
        features: Dizionario delle caratteristiche estratte
        
    Returns:
        dict: Caratteristiche formattate in modo conciso
    """
    concise_features = {
        'original_text': features.get('original_text', '')
    }
    
    # Copia le caratteristiche semplici
    for key in ['age', 'gender', 'diagnosis', 'stage', 'ecog']:
        if key in features and features[key]:
            concise_features[key] = features[key]
    
    # Elabora le mutazioni per renderle concise
    if 'mutations' in features and features['mutations']:
        concise_mutations = []
        for mutation in features['mutations']:
            if not mutation or not isinstance(mutation, dict):
                continue
                
            concise_value = mutation.get('value', '')
            source = mutation.get('source', '')
            
            # Cerca pattern specifici per estrarre informazioni più precise
            if source and concise_value and concise_value.lower() in source.lower():
                # Cerca pattern come "KRAS G12C" o "PD-L1 90%"
                pdl1_match = re.search(r'{}\s+([0-9]+)\s*%'.format(re.escape(concise_value)), source, re.I)
                mutation_match = re.search(r'{}\s+([A-Z][0-9]+[A-Z])'.format(re.escape(concise_value)), source, re.I)
                status_match = re.search(r'(positive|negative|mutato|wild.?type)', source, re.I)
                
                if pdl1_match:
                    concise_value = f"{concise_value} {pdl1_match.group(1)}%"
                elif mutation_match:
                    concise_value = f"{concise_value} {mutation_match.group(1)}"
                elif status_match:
                    concise_value = f"{concise_value} {status_match.group(1)}"
            
            concise_mutations.append({'value': concise_value})
        
        concise_features['mutations'] = concise_mutations
    
    # Elabora le metastasi per renderle concise
    if 'metastases' in features and features['metastases']:
        concise_metastases = []
        for metastasis in features['metastases']:
            if not metastasis or not isinstance(metastasis, dict):
                continue
                
            concise_value = metastasis.get('value', '')
            source = metastasis.get('source', '')
            
            # Estrai informazioni significative come numero e dimensioni
            if source and concise_value:
                count_match = re.search(r'(multiple|singular|numerose|singole|solitarie?)\s+', source, re.I)
                size_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:mm|cm)', source, re.I)
                
                description = ""
                if count_match:
                    description += count_match.group(1) + " "
                if size_match:
                    description += size_match.group(0) + " "
                
                if description:
                    concise_value = description + concise_value
                else:
                    concise_value = concise_value + " metastasis"
            
            concise_metastases.append({'value': concise_value})
        
        concise_features['metastases'] = concise_metastases
    
    # Elabora i trattamenti precedenti per renderli concisi
    if 'previous_treatments' in features and features['previous_treatments']:
        concise_treatments = []
        for treatment in features['previous_treatments']:
            if not treatment or not isinstance(treatment, dict):
                continue
                
            concise_value = treatment.get('value', '')
            source = treatment.get('source', '')
            
            # Estrai informazioni sui cicli, dosaggio o date
            if source and concise_value:
                cycles_match = re.search(r'(\d+)\s*(?:cicli|ciclo|cycles|cycle)', source, re.I)
                dose_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:mg\/m2|mg|g\/m2|g|ml)', source, re.I)
                date_match = re.search(r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})', source, re.I)
                
                info = []
                if cycles_match:
                    info.append(cycles_match.group(0))
                if dose_match:
                    info.append(dose_match.group(0))
                if date_match:
                    info.append(date_match.group(0))
                
                if info:
                    concise_value = f"{concise_value} ({', '.join(info)})"
            
            concise_treatments.append({'value': concise_value})
        
        concise_features['previous_treatments'] = concise_treatments
    
    # Elabora i valori di laboratorio per renderli concisi
    if 'lab_values' in features and features['lab_values']:
        concise_lab_values = {}
        for key, value in features['lab_values'].items():
            if isinstance(value, dict) and 'value' in value:
                concise_lab_values[key] = {'value': value['value']}
        
        concise_features['lab_values'] = concise_lab_values
    
    return concise_features

def extract_with_ollama(text: str) -> Optional[Dict[str, Any]]:
    """
    Estrae caratteristiche cliniche dal testo del paziente utilizzando Ollama LLM locale.
    
    Questa funzione utilizza un LLM locale tramite Ollama per estrarre feature cliniche strutturate
    dal testo del paziente. Il prompt è progettato specificamente per estrarre informazioni oncologiche
    rilevanti come età, genere, diagnosi, stadio, stato ECOG, mutazioni genetiche, metastasi,
    trattamenti precedenti e valori di laboratorio.
    
    Args:
        text: Il testo del paziente da analizzare
        
    Returns:
        dict: Feature estratte in formato JSON strutturato, o None se Ollama non è disponibile
    """
    try:
        # URL di Ollama API - controlla la variabile d'ambiente o usa il default
        ollama_api_url = os.environ.get('OLLAMA_API_URL', 'http://localhost:11434')
        
        # SYSTEM PROMPT
        # Questo è il prompt di sistema che definisce il compito e il formato di output per il LLM
        prompt = f"""
        # COMPITO
        Sei un assistente medico esperto specializzato nell'analisi di documenti clinici oncologici.
        Estrai le seguenti caratteristiche mediche dal testo del paziente oncologico e restituisci
        SOLO un oggetto JSON valido con i campi specificati.
        
        # CAMPI DA ESTRARRE
        - age: età del paziente come numero (o null se non trovata)
        - gender: "male", "female", o null se non trovato
        - diagnosis: diagnosi primaria del cancro (o null se non trovata)
        - stage: stadio del cancro (o null se non trovato)
        - ecog: stato di performance ECOG come numero (o null se non trovato)
        - mutations: lista di mutazioni genetiche (lista vuota se nessuna trovata)
        - metastases: lista di localizzazioni di metastasi (lista vuota se nessuna trovata)
        - previous_treatments: lista di trattamenti precedenti (lista vuota se nessuna trovata)
        - lab_values: oggetto con valori di laboratorio come coppie chiave-valore (oggetto vuoto se nessuno trovato)
        
        # ISTRUZIONI IMPORTANTI
        1. Per ogni valore estratto, includi un campo "source" con l'esatto frammento di testo da cui è stato estratto.
        2. Restituisci SOLO il JSON senza testo aggiuntivo.
        3. Se un'informazione non è presente nel testo, usa null per i campi singoli o liste/oggetti vuoti per le collezioni.
        4. Sii preciso nell'estrazione e utilizza il contesto medico per identificare correttamente le informazioni.
        
        # TESTO DEL PAZIENTE
        {text}
        
        # FORMATO OUTPUT JSON (esempio da completare con valori effettivi)
        {{
            "age": {{ "value": 65, "source": "65-year-old" }},
            "gender": {{ "value": "female", "source": "female patient" }},
            "diagnosis": {{ "value": "non-small cell lung cancer", "source": "diagnosed with non-small cell lung cancer" }},
            "stage": {{ "value": "IV", "source": "stage IV" }},
            "ecog": {{ "value": 1, "source": "ECOG PS 1" }},
            "mutations": [
                {{ "value": "EGFR T790M", "source": "positive for EGFR T790M mutation" }}
            ],
            "metastases": [
                {{ "value": "brain", "source": "brain metastases" }},
                {{ "value": "bone", "source": "bone lesions" }}
            ],
            "previous_treatments": [
                {{ "value": "carboplatin", "source": "received carboplatin" }}
            ],
            "lab_values": {{
                "hemoglobin": {{ "value": "11.2 g/dL", "source": "Hemoglobin: 11.2 g/dL" }}
            }}
        }}

        Restituisci SOLO il JSON senza testo aggiuntivo.
        """
        
        # Configurazione della richiesta all'API di Ollama
        request_data = {
            'model': 'mistral',  # Modello LLM da utilizzare (modificabile in base alla disponibilità)
            'prompt': prompt,     # Il prompt contenente le istruzioni e il testo del paziente
            'stream': False       # Non utilizziamo lo streaming per questa operazione
        }
        
        # Timeout più lungo per gestire documenti complessi
        timeout_seconds = 60
        
        # Log per debug
        logging.debug(f"Inviando richiesta a Ollama API: {ollama_api_url}")
        
        # Effettua la richiesta all'API di Ollama
        response = requests.post(
            f"{ollama_api_url}/api/generate",
            json=request_data,
            timeout=timeout_seconds
        )
        
        # Verifica se la richiesta ha avuto successo
        if response.status_code == 200:
            response_data = response.json()
            result_text = response_data.get('response', '')
            
            # Cerca di estrarre il JSON dalla risposta
            try:
                # Cerca il JSON nella risposta (può essere circondato da altro testo)
                json_start = result_text.find('{')
                json_end = result_text.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = result_text[json_start:json_end]
                    extracted_features = json.loads(json_str)
                    logger.info("Caratteristiche estratte con successo utilizzando Ollama")
                    return extracted_features
                else:
                    logger.warning("Impossibile trovare un oggetto JSON valido nella risposta di Ollama")
                    return None
            except json.JSONDecodeError:
                logger.warning("Errore di parsing JSON nella risposta di Ollama")
                return None
            except Exception as json_error:
                logger.warning(f"Errore nell'elaborazione della risposta JSON: {str(json_error)}")
                return None
        else:
            logger.warning(f"Errore nella chiamata all'API Ollama: {response.status_code}, {response.text}")
            return None
    except requests.RequestException as e:
        logger.warning(f"Estrazione con Ollama fallita: {str(e)}. Ritorno all'estrazione di base.")
        return None
    except Exception as e:
        logger.warning(f"Errore generico nell'estrazione con Ollama: {str(e)}")
        return None

def basic_feature_extraction(text: str) -> Dict[str, Any]:
    """
    Esegue un'estrazione di base delle feature utilizzando pattern regex quando LLM non è disponibile.
    
    Questa funzione implementa un'estrazione di base delle caratteristiche cliniche
    utilizzando espressioni regolari. Viene utilizzata come fallback quando:
    1. Non è disponibile una connessione a un modello LLM locale
    2. L'estrazione con LLM fallisce per qualsiasi motivo
    
    Il metodo cerca nel testo i seguenti elementi:
    - Età del paziente (es. "65-year-old")
    - Genere (male/female)
    - Diagnosi di cancro da una lista predefinita
    - Stadio del cancro (I, II, III, IV con possibili sottoclassificazioni A, B, C)
    - Stato di performance ECOG (0-4)
    - Mutazioni genetiche comuni in oncologia
    - Siti di metastasi comuni
    - Trattamenti oncologici precedenti
    - Valori di laboratorio comuni
    
    Args:
        text: Il testo da analizzare
        
    Returns:
        dict: Feature estratte con struttura compatibile con l'output dell'LLM
    """
    logger.info("Esecuzione estrazione di feature con pattern regex")
    
    # Risultato dell'estrazione
    features = {
        'original_text': text[:200] + ('...' if len(text) > 200 else '')  # Versione troncata per display
    }
    
    # Estrazione dell'età
    age_patterns = [
        r'(?:aged|età|age)[:\s]+(\d{1,2})',
        r'(\d{1,2})[\s-](?:year|anni|anno)(?:s)?[\s-](?:old|di età)',
        r'(?:paziente|patient)(?:[^\n.]{1,20})(\d{1,2})[\s-](?:year|anni|anno)',
        r'(?:paziente|patient)(?:[^\n.]{1,20})(?:aged|età|age)[:\s]+(\d{1,2})'
    ]
    
    for pattern in age_patterns:
        age_match = re.search(pattern, text, re.IGNORECASE)
        if age_match:
            age_value = int(age_match.group(1))
            features['age'] = {
                'value': age_value,
                'source': age_match.group(0)
            }
            break
    
    # Estrazione del genere
    if re.search(r'\b(?:male|man|uomo|maschio)\b', text, re.IGNORECASE):
        gender_match = re.search(r'[^.]*(?:male|man|uomo|maschio)[^.]*', text, re.IGNORECASE)
        source = gender_match.group(0) if gender_match else "male reference in text"
        features['gender'] = {
            'value': 'male',
            'source': source
        }
    elif re.search(r'\b(?:female|woman|donna|femmina)\b', text, re.IGNORECASE):
        gender_match = re.search(r'[^.]*(?:female|woman|donna|femmina)[^.]*', text, re.IGNORECASE)
        source = gender_match.group(0) if gender_match else "female reference in text"
        features['gender'] = {
            'value': 'female',
            'source': source
        }
    
    # Estrazione della diagnosi
    diagnosis_patterns = [
        r'diagnos(?:is|i|ed with)[:\s]+([^.;]{3,60}(?:carcinoma|cancer|sarcoma|leukemia|lymphoma|neoplasm|tumor|melanoma)(?:[^.;]{0,40}))',
        r'(?:carcinoma|cancer|sarcoma|leukemia|lymphoma|neoplasm|tumor|melanoma)[:\s]+([^.;]{3,60})',
        r'([^.;]{0,40}(?:lung|breast|colorectal|prostate|ovarian|gastric|pancreatic|renal|bladder)[^.;]{0,40}(?:carcinoma|cancer|tumor))',
        r'(?:NSCLC|SCLC|CRC|CLL|AML|ALL|DLBCL|MM)[^.;]{0,60}',
    ]
    
    for pattern in diagnosis_patterns:
        diagnosis_match = re.search(pattern, text, re.IGNORECASE)
        if diagnosis_match:
            # Pulisci ed estrai la diagnosi
            diagnosis_text = diagnosis_match.group(0) if diagnosis_match.group(1) is None else diagnosis_match.group(1)
            diagnosis_text = diagnosis_text.strip()
            
            features['diagnosis'] = {
                'value': diagnosis_text,
                'source': diagnosis_match.group(0)
            }
            break
    
    # Estrazione dello stadio
    stage_patterns = [
        r'stage[\s:-]+([IV]+\s*[ABC]?)',
        r'stadio[\s:-]+([IV]+\s*[ABC]?)',
        r'(?:cancer|carcinoma|tumor|disease)[\s:]+stage[\s:-]+([IV]+\s*[ABC]?)',
        r'T(\d)[N](\d)[M](\d)',  # TNM staging
    ]
    
    for pattern in stage_patterns:
        stage_match = re.search(pattern, text, re.IGNORECASE)
        if stage_match:
            # Per il TNM staging, formatta in modo appropriato
            if 'TNM' in pattern:
                stage_text = f"T{stage_match.group(1)}N{stage_match.group(2)}M{stage_match.group(3)}"
            else:
                stage_text = stage_match.group(1)
            
            features['stage'] = {
                'value': stage_text,
                'source': stage_match.group(0)
            }
            break
    
    # Estrazione del performance status ECOG
    ecog_patterns = [
        r'ECOG(?:\s+status|\s+performance\s+status|\s+PS|\s+score)?[\s:-]+([0-4])',
        r'(?:performance|funzionale)(?:\s+status)?[\s:-]+ECOG[\s:-]+([0-4])',
        r'PS[\s:-]+([0-4])(?:[^0-9]|$)',
    ]
    
    for pattern in ecog_patterns:
        ecog_match = re.search(pattern, text, re.IGNORECASE)
        if ecog_match:
            features['ecog'] = {
                'value': int(ecog_match.group(1)),
                'source': ecog_match.group(0)
            }
            break
    
    # Estrazione di mutazioni genetiche
    mutation_patterns = [
        r'(?:mutation|mutazione)[\s:-]+([^\n.;,]{3,40})',
        r'([A-Z0-9]{2,5})[\s:-]+mutation',
        r'([A-Z0-9]{2,5})(?:\s+[A-Z][0-9]+[A-Z])?(?:\s+mutation|\s+positive|\s+negativee)',
        r'(?:EGFR|ALK|ROS1|BRAF|KRAS|NRAS|HER2|BRCA|PD-L1|MET|RET|NTRK|TP53)(?:\s+[A-Z][0-9]+[A-Z])?(?:\s+mutation|\s+positive|\s+negative)?'
    ]
    
    mutations = []
    for pattern in mutation_patterns:
        for mutation_match in re.finditer(pattern, text, re.IGNORECASE):
            mutations.append({
                'value': mutation_match.group(0).strip(),
                'source': mutation_match.group(0)
            })
    
    if mutations:
        # Rimuovi duplicati basati sul valore
        unique_mutations = []
        seen = set()
        for m in mutations:
            if m['value'].lower() not in seen:
                seen.add(m['value'].lower())
                unique_mutations.append(m)
        
        features['mutations'] = unique_mutations
    
    # Estrazione di metastasi
    metastasis_sites = [
        'brain', 'liver', 'lung', 'bone', 'adrenal', 'lymph node', 'pleural',
        'peritoneal', 'cerebal', 'spinal', 'cervello', 'fegato', 'polmone',
        'ossea', 'ossee', 'linfonodale', 'pleurica', 'peritoneale'
    ]
    
    metastasis_patterns = [
        r'(?:metastasi|metastases|metastasis|metastatic|metastatico)[\s:-]+(?:to|in|al|alla|ai|alle|del|della|dei|delle)?\s+([^\n.;]{3,40})',
        r'([^\n.;]{0,30}\b(?:{})\b[^\n.;]{{0,30}}(?:metastasi|metastases|metastasis|metastatic|metastatico))'.format('|'.join(metastasis_sites))
    ]
    
    metastases = []
    for pattern in metastasis_patterns:
        for metastasis_match in re.finditer(pattern, text, re.IGNORECASE):
            # Estrai il sito specifico della metastasi
            site = None
            source = metastasis_match.group(0)
            
            # Cerca di isolare il sito della metastasi
            for site_term in metastasis_sites:
                if re.search(r'\b{}\b'.format(site_term), source, re.IGNORECASE):
                    site = site_term
                    break
            
            if site:
                metastases.append({
                    'value': site,
                    'source': source
                })
            else:
                # Se non è stato trovato un sito specifico, usa il testo completo
                metastases.append({
                    'value': metastasis_match.group(1) if metastasis_match.group(1) else source,
                    'source': source
                })
    
    if metastases:
        # Rimuovi duplicati basati sul valore
        unique_metastases = []
        seen = set()
        for m in metastases:
            if m['value'].lower() not in seen:
                seen.add(m['value'].lower())
                unique_metastases.append(m)
        
        features['metastases'] = unique_metastases
    
    # Estrazione di trattamenti precedenti
    treatment_terms = [
        'chemotherapy', 'radiation', 'surgery', 'immunotherapy', 'targeted therapy',
        'docetaxel', 'paclitaxel', 'carboplatin', 'cisplatin', 'gemcitabine',
        'pemetrexed', 'erlotinib', 'gefitinib', 'osimertinib', 'crizotinib',
        'pembrolizumab', 'nivolumab', 'atezolizumab', 'bevacizumab',
        'chemioterapia', 'radioterapia', 'chirurgia', 'immunoterapia', 'terapia'
    ]
    
    treatment_patterns = [
        r'(?:previous|prior|precedente) (?:treatment|therapy|trattamento|terapia)[:\s]+([^\n.;]{3,60})',
        r'(?:received|treated with|ricevuto|trattato con)[:\s]+([^\n.;]{3,60})',
        r'(?:history of|storia di)[^.;]{0,30}([^\n.;]{0,60}(?:{}))'.format('|'.join(treatment_terms))
    ]
    
    treatments = []
    for pattern in treatment_patterns:
        for treatment_match in re.finditer(pattern, text, re.IGNORECASE):
            # Estrai il trattamento specifico
            treatment = None
            source = treatment_match.group(0)
            
            # Cerca di isolare il tipo di trattamento
            for term in treatment_terms:
                if re.search(r'\b{}\b'.format(term), source, re.IGNORECASE):
                    treatment = term
                    break
            
            if treatment:
                treatments.append({
                    'value': treatment,
                    'source': source
                })
            else:
                # Se non è stato trovato un trattamento specifico, usa il testo completo
                treatments.append({
                    'value': treatment_match.group(1) if treatment_match.group(1) else source,
                    'source': source
                })
    
    if treatments:
        # Rimuovi duplicati basati sul valore
        unique_treatments = []
        seen = set()
        for t in treatments:
            if t['value'].lower() not in seen:
                seen.add(t['value'].lower())
                unique_treatments.append(t)
        
        features['previous_treatments'] = unique_treatments
    
    # Estrazione di valori di laboratorio
    lab_terms = [
        'hemoglobin', 'hgb', 'wbc', 'white blood cell', 'platelet', 'plt',
        'neutrophil', 'lymphocyte', 'creatinine', 'alt', 'ast', 'bilirubin',
        'albumin', 'ldh', 'emoglobina', 'piastrine', 'neutrofili', 'linfociti',
        'creatinina', 'bilirubina', 'albumina'
    ]
    
    lab_patterns = [
        r'({})[:\s]+([0-9]+\.?[0-9]*\s*(?:g/dL|g/L|x10\^9/L|U/L|mg/dL|umol/L|%))'.format('|'.join(lab_terms)),
        r'({})[:\s]+([0-9]+\.?[0-9]*\s*(?:g/dL|g/L|x10\^9/L|U/L|mg/dL|umol/L|%))'.format('|'.join([t[:4] for t in lab_terms]))
    ]
    
    lab_values = {}
    for pattern in lab_patterns:
        for lab_match in re.finditer(pattern, text, re.IGNORECASE):
            lab_name = lab_match.group(1).lower()
            lab_value = lab_match.group(2)
            
            # Normalizza il nome del test di laboratorio
            for term in lab_terms:
                if term.lower().startswith(lab_name) or lab_name.startswith(term.lower()):
                    lab_name = term
                    break
            
            lab_values[lab_name] = {
                'value': lab_value,
                'source': lab_match.group(0)
            }
    
    if lab_values:
        features['lab_values'] = lab_values
    
    return features

def clean_expired_files(upload_folder: str = 'uploads', max_age_minutes: int = 30) -> None:
    """
    Rimuove i file PDF scaduti dalla cartella uploads.
    
    Questa funzione scansiona la cartella degli upload e rimuove i file PDF
    che sono stati creati più di max_age_minutes minuti fa. Questo garantisce che
    i documenti sensibili non rimangano sul server più a lungo del necessario.
    
    Args:
        upload_folder: Percorso alla cartella degli upload. Default: 'uploads'.
        max_age_minutes: Il tempo massimo in minuti per cui un file può rimanere sul server.
                        Default: 30 minuti.
    """
    try:
        # Converti minuti in secondi
        max_age_seconds = max_age_minutes * 60
        now = datetime.now().timestamp()
        
        # Verifica che la cartella degli upload esista
        if not os.path.exists(upload_folder):
            logger.warning(f"La cartella {upload_folder} non esiste.")
            return
        
        # Itera attraverso i file nella cartella degli upload
        for filename in os.listdir(upload_folder):
            if filename.endswith('.pdf'):
                file_path = os.path.join(upload_folder, filename)
                file_creation_time = os.path.getctime(file_path)
                
                # Se il file è più vecchio di max_age_minutes, eliminalo
                if now - file_creation_time > max_age_seconds:
                    os.remove(file_path)
                    logger.info(f"Rimosso file scaduto: {filename}")
    except Exception as e:
        logger.error(f"Errore durante la pulizia dei file scaduti: {str(e)}")