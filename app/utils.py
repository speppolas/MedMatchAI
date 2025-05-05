import os
import json
import pdfplumber
import logging
import requests
import re
from flask import current_app

def extract_text_from_pdf(pdf_file):
    """
    Extract text content from a PDF file using pdfplumber.
    
    Args:
        pdf_file: The PDF file object from request.files
        
    Returns:
        str: Extracted text from the PDF
    """
    text = ""
    try:
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

def extract_with_ollama(text):
    """
    Extract features using Ollama local LLM.
    
    Args:
        text: The text to analyze
        
    Returns:
        dict: Extracted features or None if Ollama is not available
    """
    try:
        # Define the prompt for the LLM
        prompt = f"""
        Extract the following medical features from this oncology patient text and return ONLY a valid JSON object with these fields:
        - age: patient age as number (or null if not found)
        - gender: "male", "female", or null if not found
        - diagnosis: primary cancer diagnosis (or null if not found)
        - stage: cancer stage (or null if not found)
        - ecog: ECOG performance status as number (or null if not found)
        - mutations: list of genetic mutations (empty list if none found)
        - metastases: list of metastasis locations (empty list if none found)
        - previous_treatments: list of previous treatments (empty list if none found)
        - lab_values: object with lab values as key-value pairs (empty object if none found)
        
        For each extracted value, include a "source" field with the exact text fragment it was extracted from.
        
        Here is the patient text:
        {text}
        
        JSON output format (fill with actual values):
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

        Return ONLY the JSON with no additional text.
        """
        
        # Try to connect to the Ollama API running locally
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': 'mistral',  # or another available model
                'prompt': prompt,
                'stream': False
            },
            timeout=60  # timeout in seconds
        )
        
        if response.status_code == 200:
            # Extract the generated text
            result = response.json().get('response', '')
            
            # Extract only the JSON part from the response
            json_match = re.search(r'({[\s\S]*})', result)
            if json_match:
                json_str = json_match.group(1)
                return json.loads(json_str)
            
        return None
    except Exception as e:
        logging.warning(f"Ollama extraction failed: {str(e)}. Falling back to basic extraction.")
        return None

def basic_feature_extraction(text):
    """
    Perform basic feature extraction using regex patterns when LLM is not available.
    
    Args:
        text: The text to analyze
        
    Returns:
        dict: Basic extracted features
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
    
    for mutation in mutations:
        pattern = r'([^.]*\b' + re.escape(mutation) + r'\b[^.]*\.)'
        for match in re.finditer(pattern, text, re.IGNORECASE):
            features["mutations"].append({
                "value": mutation,
                "source": match.group(0).strip()
            })
    
    # Common metastasis sites
    metastasis_sites = [
        "brain", "liver", "bone", "lung", "adrenal", "lymph node", 
        "peritoneal", "pleural", "skin"
    ]
    
    for site in metastasis_sites:
        pattern = r'([^.]*\b' + re.escape(site) + r'(?:\s+metastases|\s+metastasis|\s+lesions|\s+mets|\s+spread)[^.]*\.)'
        for match in re.finditer(pattern, text, re.IGNORECASE):
            features["metastases"].append({
                "value": site,
                "source": match.group(0).strip()
            })
    
    # Common treatments
    treatments = [
        "chemotherapy", "radiation", "surgery", "immunotherapy", 
        "carboplatin", "cisplatin", "paclitaxel", "docetaxel", "pembrolizumab",
        "nivolumab", "atezolizumab", "durvalumab", "trastuzumab", "osimertinib",
        "erlotinib", "gefitinib", "crizotinib", "alectinib", "cetuximab"
    ]
    
    for treatment in treatments:
        pattern = r'([^.]*\b(?:previous|prior|received|treated with|therapy with)\s[^.]*\b' + re.escape(treatment) + r'\b[^.]*\.)'
        for match in re.finditer(pattern, text, re.IGNORECASE):
            features["previous_treatments"].append({
                "value": treatment,
                "source": match.group(0).strip()
            })
    
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
