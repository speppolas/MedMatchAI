import os
import json
import pdfplumber
import logging
import requests
import re
import time
import shutil
from datetime import datetime, timedelta
from flask import current_app

def extract_text_from_pdf(pdf_file):
    """
    Extract text content from a PDF file using pdfplumber.
    
    Args:
        pdf_file: Either a file object from request.files or a filepath string
        
    Returns:
        str: Extracted text from the PDF
    """
    text = ""
    try:
        # Check if pdf_file is a string (filepath) or a file object
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text
    except Exception as e:
        logging.error(f"Error extracting text from PDF: {str(e)}")
        raise Exception(f"Could not extract text from PDF: {str(e)}")

def extract_features(text):
    """
    Extract clinical features from text using a local LLM.
    
    Args:
        text: The text content to analyze
        
    Returns:
        dict: Extracted clinical features in JSON format
    """
    try:
        # Using Ollama (if available) or fallback to simple regex extraction
        features = extract_with_ollama(text)
        
        # If Ollama isn't available or fails, fall back to basic extraction
        if not features:
            features = basic_feature_extraction(text)
            
        return features
    except Exception as e:
        logging.error(f"Error extracting features: {str(e)}")
        # Fallback to basic extraction in case of any error
        return basic_feature_extraction(text)
        
def format_features_concise(features):
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

def extract_with_ollama(text):
    """
    Extract clinical features from patient text using Ollama local LLM.
    
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
            # Estrai il testo generato dalla risposta
            result = response.json().get('response', '')
            
            # Estrai solo la parte JSON dalla risposta
            # Questo è importante poiché l'LLM potrebbe includere testo aggiuntivo
            json_match = re.search(r'({[\s\S]*})', result)
            if json_match:
                json_str = json_match.group(1)
                try:
                    # Conversione della stringa JSON in dizionario Python
                    features = json.loads(json_str)
                    # Aggiungiamo il testo originale per mostrarlo nella UI
                    features["original_text"] = text
                    logging.info("Feature estratte con successo da Ollama LLM")
                    return features
                except json.JSONDecodeError as e:
                    logging.error(f"Errore nella decodifica JSON: {str(e)}")
                    return None
            else:
                logging.warning("Nessun formato JSON valido trovato nella risposta di Ollama")
                return None
        else:
            logging.warning(f"Ollama API ha risposto con codice: {response.status_code}")
            return None
    except Exception as e:
        logging.warning(f"Estrazione con Ollama fallita: {str(e)}. Ritorno all'estrazione di base.")
        return None

def clean_expired_files(max_age_minutes=30):
    """
    Rimuove i file PDF scaduti dalla cartella uploads.
    
    Questa funzione scansiona la cartella degli upload e rimuove i file PDF
    che sono stati creati più di max_age_minutes minuti fa. Questo garantisce che
    i documenti sensibili non rimangano sul server più a lungo del necessario.
    
    Args:
        max_age_minutes: Il tempo massimo in minuti per cui un file può rimanere sul server.
                        Default: 30 minuti.
    """
    try:
        upload_folder = current_app.config['UPLOAD_FOLDER']
        
        # Se la cartella non esiste, non c'è nulla da pulire
        if not os.path.exists(upload_folder):
            return
            
        # Calcola il timestamp di scadenza
        expiration_time = datetime.now() - timedelta(minutes=max_age_minutes)
        expiration_timestamp = expiration_time.timestamp()
        
        # Verifica tutti i file nella cartella uploads
        for filename in os.listdir(upload_folder):
            if filename.endswith('.pdf'):
                file_path = os.path.join(upload_folder, filename)
                file_creation_time = os.path.getctime(file_path)
                
                # Se il file è più vecchio del tempo massimo consentito, eliminalo
                if file_creation_time < expiration_timestamp:
                    try:
                        os.remove(file_path)
                        logging.info(f"Rimosso file scaduto: {filename}")
                    except Exception as e:
                        logging.error(f"Errore durante la rimozione del file {filename}: {str(e)}")
    except Exception as e:
        logging.error(f"Errore durante la pulizia dei file scaduti: {str(e)}")

def basic_feature_extraction(text):
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
    features = {
        "age": {"value": None, "source": ""},
        "gender": {"value": None, "source": ""},
        "diagnosis": {"value": None, "source": ""},
        "stage": {"value": None, "source": ""},
        "ecog": {"value": None, "source": ""},
        "mutations": [],
        "metastases": [],
        "previous_treatments": [],
        "lab_values": {}
    }
    
    # Salviamo anche il testo originale per mostrarlo nella UI
    features["original_text"] = text
    
    # Basic age extraction
    age_match = re.search(r'(\d+)[\s-]*(?:year|yr)s?[\s-]*old', text, re.IGNORECASE)
    if age_match:
        features["age"]["value"] = int(age_match.group(1))
        features["age"]["source"] = age_match.group(0)
    
    # Basic gender extraction
    if re.search(r'\b(male|man)\b', text, re.IGNORECASE):
        features["gender"]["value"] = "male"
        features["gender"]["source"] = "male reference in text"
    elif re.search(r'\b(female|woman)\b', text, re.IGNORECASE):
        features["gender"]["value"] = "female"
        features["gender"]["source"] = "female reference in text"
    
    # Basic diagnosis patterns
    cancer_types = [
        "lung cancer", "breast cancer", "colorectal cancer", "prostate cancer",
        "melanoma", "leukemia", "lymphoma", "pancreatic cancer", "ovarian cancer",
        "non-small cell lung cancer", "NSCLC", "small cell lung cancer", "SCLC",
        "glioblastoma", "glioma", "hepatocellular carcinoma", "HCC"
    ]
    
    for cancer in cancer_types:
        if cancer.lower() in text.lower():
            features["diagnosis"]["value"] = cancer
            
            # Try to find a more precise context
            context_match = re.search(r'([^.]*' + re.escape(cancer) + r'[^.]*\.)', text, re.IGNORECASE)
            if context_match:
                features["diagnosis"]["source"] = context_match.group(1).strip()
            else:
                features["diagnosis"]["source"] = f"contains '{cancer}'"
            
            break
    
    # Stage extraction
    stage_match = re.search(r'stage\s+(I{1,3}V?|IV|III|II|I)([A-C])?', text, re.IGNORECASE)
    if stage_match:
        features["stage"]["value"] = stage_match.group(1) + (stage_match.group(2) or "")
        features["stage"]["source"] = stage_match.group(0)
    
    # ECOG extraction
    ecog_match = re.search(r'ECOG\s*(?:PS|performance status)?\s*(?:of|:)?\s*([0-4])', text, re.IGNORECASE)
    if ecog_match:
        features["ecog"]["value"] = int(ecog_match.group(1))
        features["ecog"]["source"] = ecog_match.group(0)
    
    # Common mutations
    mutations = [
        "EGFR", "ALK", "ROS1", "BRAF V600E", "KRAS", "HER2", "BRCA1", "BRCA2", 
        "PD-L1", "MSI-H", "dMMR", "NTRK", "RET", "MET"
    ]
    
    # Tracciamo le mutazioni già trovate per evitare duplicati
    found_mutations = set()
    
    for mutation in mutations:
        # Se la mutazione è già stata trovata, saltiamo
        if mutation in found_mutations:
            continue
            
        pattern = r'([^.]*\b' + re.escape(mutation) + r'\b[^.]*\.)'
        best_match = None
        best_match_text = ""
        
        # Cerchiamo tutte le occorrenze e manteniamo la migliore (quella con più informazioni)
        for match in re.finditer(pattern, text, re.IGNORECASE):
            match_text = match.group(0).strip()
            
            # Se è la prima occorrenza o è più informativa della precedente
            if best_match is None or len(match_text) > len(best_match_text):
                # Controlliamo se contiene termini specifici come "mutazione" o "mut" che indicano informazioni più specifiche
                specificity_terms = ["mutazione", "mut ", "mut:", "mutation", "alterazione", "delezione", "inserzione", "traslocazione"]
                current_specificity = any(term in match_text.lower() for term in specificity_terms)
                previous_specificity = any(term in best_match_text.lower() for term in specificity_terms) if best_match_text else False
                
                # Se la nuova è più specifica o la precedente non era specifica
                if current_specificity or not previous_specificity:
                    best_match = match
                    best_match_text = match_text
        
        # Se abbiamo trovato almeno un'occorrenza per questa mutazione
        if best_match is not None:
            features["mutations"].append({
                "value": mutation,
                "source": best_match_text
            })
            found_mutations.add(mutation)
    
    # Common metastasis sites
    metastasis_sites = [
        "brain", "liver", "bone", "lung", "adrenal", "lymph node", 
        "peritoneal", "pleural", "skin"
    ]
    
    # Tracciamo i siti metastatici già trovati per evitare duplicati
    found_metastases = set()
    
    for site in metastasis_sites:
        # Se il sito è già stato trovato, saltiamo
        if site in found_metastases:
            continue
            
        pattern = r'([^.]*\b' + re.escape(site) + r'(?:\s+metastases|\s+metastasis|\s+lesions|\s+mets|\s+spread)[^.]*\.)'
        best_match = None
        best_match_text = ""
        
        # Cerchiamo tutte le occorrenze e manteniamo la migliore (quella con più informazioni)
        for match in re.finditer(pattern, text, re.IGNORECASE):
            match_text = match.group(0).strip()
            
            # Se è la prima occorrenza o è più informativa della precedente
            if best_match is None or len(match_text) > len(best_match_text):
                best_match = match
                best_match_text = match_text
        
        # Se abbiamo trovato almeno un'occorrenza per questo sito metastatico
        if best_match is not None:
            features["metastases"].append({
                "value": site,
                "source": best_match_text
            })
            found_metastases.add(site)
    
    # Common treatments
    treatments = [
        "chemotherapy", "radiation", "surgery", "immunotherapy", 
        "carboplatin", "cisplatin", "paclitaxel", "docetaxel", "pembrolizumab",
        "nivolumab", "atezolizumab", "durvalumab", "trastuzumab", "osimertinib",
        "erlotinib", "gefitinib", "crizotinib", "alectinib", "cetuximab"
    ]
    
    # Tracciamo i trattamenti già trovati per evitare duplicati
    found_treatments = set()
    
    for treatment in treatments:
        # Se il trattamento è già stato trovato, saltiamo
        if treatment in found_treatments:
            continue
            
        pattern = r'([^.]*\b(?:previous|prior|received|treated with|therapy with)\s[^.]*\b' + re.escape(treatment) + r'\b[^.]*\.)'
        best_match = None
        best_match_text = ""
        
        # Cerchiamo tutte le occorrenze e manteniamo la migliore
        for match in re.finditer(pattern, text, re.IGNORECASE):
            match_text = match.group(0).strip()
            
            # Se è la prima occorrenza o è più informativa della precedente
            if best_match is None or len(match_text) > len(best_match_text):
                # Controlliamo se contiene termini specifici come "cicli" o "dosaggio" che indicano informazioni più specifiche
                specificity_terms = ["cicli", "ciclo", "dose", "dosaggio", "mg", "gr", "effetti collaterali", "tossicità"]
                current_specificity = any(term in match_text.lower() for term in specificity_terms)
                previous_specificity = any(term in best_match_text.lower() for term in specificity_terms) if best_match_text else False
                
                # Se la nuova è più specifica o la precedente non era specifica
                if current_specificity or not previous_specificity:
                    best_match = match
                    best_match_text = match_text
        
        # Se abbiamo trovato almeno un'occorrenza per questo trattamento
        if best_match is not None:
            features["previous_treatments"].append({
                "value": treatment,
                "source": best_match_text
            })
            found_treatments.add(treatment)
    
    # Common lab values
    lab_tests = {
        "hemoglobin": r'(?:Hgb|Hemoglobin|Hb)[\s:]+(\d+\.?\d*)\s*(?:g/dL|g/dl)',
        "wbc": r'(?:WBC|White blood cells?)[\s:]+(\d+\.?\d*)\s*(?:K/μL|x10\^9/L)',
        "platelets": r'(?:PLT|Platelets)[\s:]+(\d+\.?\d*)\s*(?:K/μL|x10\^9/L)',
        "creatinine": r'(?:Cr|Creatinine)[\s:]+(\d+\.?\d*)\s*(?:mg/dL|mg/dl)',
        "alt": r'(?:ALT|SGPT)[\s:]+(\d+\.?\d*)\s*(?:U/L|IU/L)',
        "ast": r'(?:AST|SGOT)[\s:]+(\d+\.?\d*)\s*(?:U/L|IU/L)'
    }
    
    for lab_name, pattern in lab_tests.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            features["lab_values"][lab_name] = {
                "value": match.group(0),
                "source": match.group(0)
            }
    
    return features

def match_trials(patient_features):
    """
    Match patient features with available clinical trials.
    
    Args:
        patient_features: Extracted patient features
        
    Returns:
        list: Matching clinical trials with explanation
    """
    try:
        # Load clinical trials from the JSON file
        with open('trials_int.json', 'r') as f:
            trials = json.load(f)
        
        matched_trials = []
        
        for trial in trials:
            # Initialize match score and explanations
            match_score = 0
            total_criteria = 0
            matches = []
            non_matches = []
            
            # Check inclusion criteria
            for criterion in trial.get('inclusion_criteria', []):
                total_criteria += 1
                match_result = check_criterion_match(criterion, patient_features)
                
                if match_result['matches']:
                    match_score += 1
                    matches.append(match_result)
                else:
                    non_matches.append(match_result)
            
            # Check exclusion criteria
            for criterion in trial.get('exclusion_criteria', []):
                total_criteria += 1
                match_result = check_criterion_match(criterion, patient_features)
                
                # For exclusion criteria, we want it NOT to match
                if not match_result['matches']:
                    match_score += 1
                    matches.append({
                        'criterion': criterion,
                        'matches': True,
                        'explanation': "Patient does not meet exclusion criterion"
                    })
                else:
                    non_matches.append({
                        'criterion': criterion,
                        'matches': False,
                        'explanation': "Patient meets exclusion criterion: " + match_result['explanation']
                    })
            
            # Calculate match percentage
            match_percentage = (match_score / total_criteria * 100) if total_criteria > 0 else 0
            
            # Add to matched trials if score is above threshold
            if match_percentage >= 50:  # Minimum 50% match
                matched_trials.append({
                    'trial_id': trial.get('id'),
                    'title': trial.get('title'),
                    'phase': trial.get('phase'),
                    'match_percentage': round(match_percentage, 1),
                    'matches': matches,
                    'non_matches': non_matches,
                    'description': trial.get('description', '')
                })
        
        # Sort by match percentage (descending)
        matched_trials.sort(key=lambda x: x['match_percentage'], reverse=True)
        
        return matched_trials
    
    except Exception as e:
        logging.error(f"Error matching trials: {str(e)}")
        # Return empty list in case of error
        return []

def get_all_trials():
    """
    Get all available clinical trials from the JSON file.
    
    Returns:
        list: All clinical trials
    """
    try:
        with open('trials_int.json', 'r') as f:
            trials = json.load(f)
        return trials
    except Exception as e:
        logging.error(f"Error loading trials: {str(e)}")
        return []

def check_criterion_match(criterion, patient_features):
    """
    Check if a patient matches a specific clinical trial criterion.
    
    Args:
        criterion: The criterion to check
        patient_features: The patient's extracted features
        
    Returns:
        dict: Match result with explanation
    """
    criterion_text = criterion.get('text', '').lower()
    criterion_type = criterion.get('type', '').lower()
    
    result = {
        'criterion': criterion,
        'matches': False,
        'explanation': ""
    }
    
    # Age criteria
    if 'age' in criterion_type or re.search(r'\bage\b', criterion_text):
        if patient_features['age']['value'] is not None:
            age = patient_features['age']['value']
            
            # Check for minimum age
            min_age_match = re.search(r'(?:age|patients?)\s*(?:>=|≥|>=|greater than or equal to|at least|minimum|>|greater than)\s*(\d+)', criterion_text)
            if min_age_match and age < int(min_age_match.group(1)):
                result['explanation'] = f"Patient age {age} is below minimum required age {min_age_match.group(1)}"
                return result
            
            # Check for maximum age
            max_age_match = re.search(r'(?:age|patients?)\s*(?:<=|≤|<=|less than or equal to|maximum|<|less than)\s*(\d+)', criterion_text)
            if max_age_match and age > int(max_age_match.group(1)):
                result['explanation'] = f"Patient age {age} is above maximum allowed age {max_age_match.group(1)}"
                return result
            
            result['matches'] = True
            result['explanation'] = f"Patient age {age} meets criterion"
        else:
            result['explanation'] = "Patient age unknown"
    
    # Gender criteria
    elif 'gender' in criterion_type or re.search(r'\b(?:male|female|gender|sex)\b', criterion_text):
        if patient_features['gender']['value'] is not None:
            gender = patient_features['gender']['value'].lower()
            
            if 'male' in criterion_text and gender == 'male':
                result['matches'] = True
                result['explanation'] = "Patient is male as required"
            elif 'female' in criterion_text and gender == 'female':
                result['matches'] = True
                result['explanation'] = "Patient is female as required"
            elif 'male' in criterion_text and 'female' in criterion_text:
                result['matches'] = True
                result['explanation'] = "Both genders are allowed"
            else:
                result['explanation'] = f"Patient gender {gender} does not match required gender"
        else:
            result['explanation'] = "Patient gender unknown"
    
    # Diagnosis criteria
    elif 'diagnosis' in criterion_type or any(x in criterion_text for x in ['cancer', 'tumor', 'carcinoma', 'sarcoma', 'leukemia', 'lymphoma']):
        if patient_features['diagnosis']['value'] is not None:
            diagnosis = patient_features['diagnosis']['value'].lower()
            
            # Check if the diagnosis matches
            if diagnosis in criterion_text or any(term in criterion_text for term in diagnosis.split()):
                result['matches'] = True
                result['explanation'] = f"Patient diagnosis '{diagnosis}' matches criterion"
            else:
                result['explanation'] = f"Patient diagnosis '{diagnosis}' not mentioned in criterion"
        else:
            result['explanation'] = "Patient diagnosis unknown"
    
    # Stage criteria
    elif 'stage' in criterion_type or re.search(r'\bstage\b', criterion_text):
        if patient_features['stage']['value'] is not None:
            stage = patient_features['stage']['value']
            
            if stage.lower() in criterion_text:
                result['matches'] = True
                result['explanation'] = f"Patient stage {stage} matches criterion"
            else:
                result['explanation'] = f"Patient stage {stage} not mentioned in criterion"
        else:
            result['explanation'] = "Patient stage unknown"
    
    # ECOG criteria
    elif 'ecog' in criterion_type or 'performance status' in criterion_text or re.search(r'\becog\b', criterion_text):
        if patient_features['ecog']['value'] is not None:
            ecog = patient_features['ecog']['value']
            
            # Check for maximum ECOG (common criterion)
            ecog_match = re.search(r'ecog\s*(?:performance status)?\s*(?:<=|≤|<=|less than or equal to|of)\s*(\d)', criterion_text, re.IGNORECASE)
            if ecog_match and ecog <= int(ecog_match.group(1)):
                result['matches'] = True
                result['explanation'] = f"Patient ECOG {ecog} is within allowed range (≤{ecog_match.group(1)})"
            elif ecog_match:
                result['explanation'] = f"Patient ECOG {ecog} exceeds maximum allowed {ecog_match.group(1)}"
            else:
                # Simple text match if no specific comparison found
                if str(ecog) in criterion_text:
                    result['matches'] = True
                    result['explanation'] = f"Patient ECOG {ecog} mentioned in criterion"
                else:
                    result['explanation'] = f"Patient ECOG {ecog} not specifically mentioned"
        else:
            result['explanation'] = "Patient ECOG status unknown"
    
    # Mutation criteria
    elif 'mutation' in criterion_type or any(x in criterion_text for x in ['mutation', 'genetic', 'biomarker', 'expression']):
        if patient_features['mutations']:
            # Check if any of the patient's mutations are mentioned in the criterion
            matching_mutations = []
            for mutation in patient_features['mutations']:
                if mutation['value'].lower() in criterion_text:
                    matching_mutations.append(mutation['value'])
            
            if matching_mutations:
                result['matches'] = True
                result['explanation'] = f"Patient has required mutation(s): {', '.join(matching_mutations)}"
            else:
                result['explanation'] = "Patient mutations do not match required mutations"
        else:
            if 'negative' in criterion_text or 'without' in criterion_text:
                result['matches'] = True
                result['explanation'] = "No mutations detected, which matches negative mutation criterion"
            else:
                result['explanation'] = "No patient mutations detected"
    
    # Metastasis criteria
    elif 'metastasis' in criterion_type or any(x in criterion_text for x in ['metastasis', 'metastases', 'metastatic']):
        if patient_features['metastases']:
            # Check for specific metastasis sites mentioned in criterion
            matching_sites = []
            for metastasis in patient_features['metastases']:
                if metastasis['value'].lower() in criterion_text:
                    matching_sites.append(metastasis['value'])
            
            if matching_sites:
                result['matches'] = True
                result['explanation'] = f"Patient has metastases in mentioned sites: {', '.join(matching_sites)}"
            else:
                result['explanation'] = "Patient metastasis sites do not match mentioned sites"
        else:
            if 'without' in criterion_text or 'no ' in criterion_text:
                result['matches'] = True
                result['explanation'] = "No metastases detected, which matches criterion"
            else:
                result['explanation'] = "No patient metastases detected"
    
    # Prior treatment criteria
    elif 'treatment' in criterion_type or any(x in criterion_text for x in ['prior therapy', 'previous treatment', 'received', 'undergone']):
        if patient_features['previous_treatments']:
            # Check for treatments mentioned in criterion
            matching_treatments = []
            for treatment in patient_features['previous_treatments']:
                if treatment['value'].lower() in criterion_text:
                    matching_treatments.append(treatment['value'])
            
            if matching_treatments:
                if 'without' in criterion_text or 'no prior' in criterion_text:
                    result['explanation'] = f"Patient has received treatments mentioned as exclusions: {', '.join(matching_treatments)}"
                else:
                    result['matches'] = True
                    result['explanation'] = f"Patient has received required treatments: {', '.join(matching_treatments)}"
            else:
                if 'without' in criterion_text or 'no prior' in criterion_text:
                    result['matches'] = True
                    result['explanation'] = "Patient has not received excluded treatments"
                else:
                    result['explanation'] = "Patient has not received the required treatments"
        else:
            if 'without' in criterion_text or 'no prior' in criterion_text:
                result['matches'] = True
                result['explanation'] = "No prior treatments detected, which matches criterion"
            else:
                result['explanation'] = "No patient treatment history detected"
    
    # Simple keyword matching for other criteria
    else:
        # Convert patient features to a simple text for keyword matching
        patient_text = json.dumps(patient_features).lower()
        
        # Extract key terms from criterion
        key_terms = re.findall(r'\b\w{4,}\b', criterion_text)  # Words with 4+ characters
        matching_terms = [term for term in key_terms if term in patient_text]
        
        if matching_terms:
            result['matches'] = True
            result['explanation'] = f"Patient data contains key terms: {', '.join(matching_terms)}"
        else:
            result['explanation'] = "No matching terms found in patient data"
    
    return result
