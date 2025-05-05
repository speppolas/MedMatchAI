import os
import json
import re
import logging
from flask import render_template, request, jsonify, current_app
from app import bp
from app.utils import extract_text_from_pdf, extract_features
from models import ClinicalTrial, db

@bp.route('/')
def index():
    """Render the main application page."""
    return render_template('index.html')

@bp.route('/trials')
def trials():
    """Render the trials listing page."""
    return render_template('trials.html')

@bp.route('/api/trials')
def api_trials():
    """API endpoint to get all available trials."""
    try:
        trials = get_all_trials_db()
        return jsonify(trials)
    except Exception as e:
        logging.error(f"Error fetching trials: {str(e)}")
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@bp.route('/process', methods=['POST'])
def process():
    """Process uploaded PDF or text input and find matching trials."""
    try:
        # Check if we have a file upload or text input
        text = ""
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            if file.filename.endswith('.pdf'):
                text = extract_text_from_pdf(file)
            else:
                return jsonify({'error': 'Only PDF files are supported'}), 400
        elif 'text' in request.form and request.form['text'].strip():
            text = request.form['text']
        else:
            return jsonify({'error': 'No input provided. Please upload a PDF or enter text.'}), 400
        
        # Extract features using local LLM
        features = extract_features(text)
        
        # Match with clinical trials
        trial_matches = match_trials_db(features)
        
        # Return extracted features and matching trials
        return jsonify({
            'features': features,
            'matches': trial_matches,
            'text': text
        })
        
    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

# Database functions

def get_all_trials_db():
    """
    Get all available clinical trials from the database.
    
    Returns:
        list: All clinical trials as dictionaries
    """
    try:
        trials = ClinicalTrial.query.all()
        return [trial.to_dict() for trial in trials]
    except Exception as e:
        logging.error(f"Error retrieving trials from DB: {str(e)}")
        # Se il database non è disponibile, usa il vecchio metodo
        return get_all_trials_json()

def get_all_trials_json():
    """
    Get all available clinical trials from the JSON file (fallback).
    
    Returns:
        list: All clinical trials
    """
    try:
        with open('trials_int.json', 'r') as f:
            trials = json.load(f)
        return trials
    except Exception as e:
        logging.error(f"Error loading trials from JSON: {str(e)}")
        return []

def match_trials_db(patient_features):
    """
    Match patient features with available clinical trials in database.
    
    Args:
        patient_features: Extracted patient features
        
    Returns:
        list: Matching clinical trials with explanation
    """
    try:
        # Get trials from database
        trials = get_all_trials_db()
        
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
            else:
                result['explanation'] = f"Patient gender {gender} does not match criterion"
        else:
            result['explanation'] = "Patient gender unknown"
    
    # Diagnosis criteria
    elif 'diagnosis' in criterion_type or re.search(r'\b(?:cancer|tumor|carcinoma|sarcoma|leukemia|lymphoma|melanoma|glioma|blastoma)\b', criterion_text):
        if patient_features['diagnosis']['value'] is not None:
            diagnosis = patient_features['diagnosis']['value'].lower()
            
            # Check for cancer type match
            if any(cancer_type in diagnosis for cancer_type in ['lung', 'breast', 'colorectal', 'ovarian', 'prostate', 'pancreatic']):
                if cancer_type in criterion_text:
                    result['matches'] = True
                    result['explanation'] = f"Patient has {diagnosis} which matches criterion"
                else:
                    result['explanation'] = f"Patient has {diagnosis} which does not match required cancer type"
            else:
                # More generic check if specific cancer types not found
                common_terms = ['non-small cell', 'small cell', 'metastatic', 'advanced', 'recurrent', 'invasive']
                matches_general = any(term in diagnosis and term in criterion_text for term in common_terms)
                
                if matches_general:
                    result['matches'] = True
                    result['explanation'] = f"Patient's diagnosis {diagnosis} generally matches criterion"
                else:
                    result['explanation'] = f"Patient's diagnosis {diagnosis} does not match criterion"
        else:
            result['explanation'] = "Patient diagnosis unknown"
    
    # Stage criteria
    elif 'stage' in criterion_type or re.search(r'\bstage\b', criterion_text):
        if patient_features['stage']['value'] is not None:
            stage = patient_features['stage']['value'].upper()
            
            # Extract stage from criterion
            stage_in_criterion = re.search(r'stage\s+(I{1,3}V?|IV|III|II|I)([A-C])?', criterion_text, re.IGNORECASE)
            if stage_in_criterion:
                criterion_stage = stage_in_criterion.group(1).upper() + (stage_in_criterion.group(2) or "").upper()
                
                # Check for exact match
                if stage == criterion_stage:
                    result['matches'] = True
                    result['explanation'] = f"Patient stage {stage} matches criterion exactly"
                # Check for stage ranges (e.g. "stage II-IV")
                elif re.search(r'stage\s+([I]{1,3}V?|IV|III|II|I)\s*[-–—]\s*([I]{1,3}V?|IV|III|II|I)', criterion_text, re.IGNORECASE):
                    range_match = re.search(r'stage\s+([I]{1,3}V?|IV|III|II|I)\s*[-–—]\s*([I]{1,3}V?|IV|III|II|I)', criterion_text, re.IGNORECASE)
                    start_stage = range_match.group(1).upper()
                    end_stage = range_match.group(2).upper()
                    
                    # Convert Roman numerals to integers for comparison
                    roman_to_int = {'I': 1, 'II': 2, 'III': 3, 'IV': 4}
                    patient_stage_num = roman_to_int.get(re.sub(r'[A-C]', '', stage), 0)
                    start_stage_num = roman_to_int.get(start_stage, 0)
                    end_stage_num = roman_to_int.get(end_stage, 0)
                    
                    if start_stage_num <= patient_stage_num <= end_stage_num:
                        result['matches'] = True
                        result['explanation'] = f"Patient stage {stage} is within the range {start_stage}-{end_stage}"
                    else:
                        result['explanation'] = f"Patient stage {stage} is outside the range {start_stage}-{end_stage}"
                else:
                    result['explanation'] = f"Patient stage {stage} does not match criterion stage {criterion_stage}"
            else:
                # If no specific stage in criterion, check for general mentions
                if "early stage" in criterion_text and stage in ["I", "II", "IA", "IB", "IIA", "IIB"]:
                    result['matches'] = True
                    result['explanation'] = f"Patient has early stage disease ({stage})"
                elif "advanced stage" in criterion_text and stage in ["III", "IV", "IIIA", "IIIB", "IIIC", "IV"]:
                    result['matches'] = True
                    result['explanation'] = f"Patient has advanced stage disease ({stage})"
                else:
                    result['explanation'] = f"Cannot determine if patient stage {stage} matches criterion"
        else:
            result['explanation'] = "Patient disease stage unknown"
    
    # ECOG/Performance status criteria
    elif 'performance' in criterion_type or 'ecog' in criterion_type or re.search(r'\b(?:ECOG|performance status|PS)\b', criterion_text):
        if patient_features['ecog']['value'] is not None:
            ecog = patient_features['ecog']['value']
            
            # Check for specific ECOG value
            ecog_in_criterion = re.search(r'ECOG\s*(?:PS|performance status)?\s*(?:of|:|=)?\s*(\d)', criterion_text, re.IGNORECASE)
            if ecog_in_criterion:
                criterion_ecog = int(ecog_in_criterion.group(1))
                if ecog == criterion_ecog:
                    result['matches'] = True
                    result['explanation'] = f"Patient ECOG {ecog} matches criterion exactly"
                else:
                    result['explanation'] = f"Patient ECOG {ecog} does not match criterion ECOG {criterion_ecog}"
            
            # Check for ECOG range (e.g. "ECOG 0-2")
            elif re.search(r'ECOG\s*(?:PS|performance status)?\s*(?:of|:|=)?\s*(\d)\s*[-–—]\s*(\d)', criterion_text, re.IGNORECASE):
                range_match = re.search(r'ECOG\s*(?:PS|performance status)?\s*(?:of|:|=)?\s*(\d)\s*[-–—]\s*(\d)', criterion_text, re.IGNORECASE)
                min_ecog = int(range_match.group(1))
                max_ecog = int(range_match.group(2))
                
                if min_ecog <= ecog <= max_ecog:
                    result['matches'] = True
                    result['explanation'] = f"Patient ECOG {ecog} is within the range {min_ecog}-{max_ecog}"
                else:
                    result['explanation'] = f"Patient ECOG {ecog} is outside the range {min_ecog}-{max_ecog}"
            
            # Check for ECOG using words like "less than or equal to"
            elif re.search(r'ECOG\s*(?:PS|performance status)?\s*(?:<=|≤|less than or equal to)\s*(\d)', criterion_text, re.IGNORECASE):
                match = re.search(r'ECOG\s*(?:PS|performance status)?\s*(?:<=|≤|less than or equal to)\s*(\d)', criterion_text, re.IGNORECASE)
                max_ecog = int(match.group(1))
                
                if ecog <= max_ecog:
                    result['matches'] = True
                    result['explanation'] = f"Patient ECOG {ecog} is less than or equal to {max_ecog}"
                else:
                    result['explanation'] = f"Patient ECOG {ecog} is greater than {max_ecog}"
            else:
                result['explanation'] = f"Cannot determine if patient ECOG {ecog} matches criterion"
        else:
            result['explanation'] = "Patient ECOG status unknown"
    
    # Mutation criteria
    elif 'mutation' in criterion_type:
        # Get patient mutations as a list of values
        patient_mutations = [mutation['value'].lower() for mutation in patient_features['mutations']]
        
        # Check for common mutation types
        common_mutations = {
            'egfr': ['egfr', 'epidermal growth factor receptor'],
            'alk': ['alk', 'anaplastic lymphoma kinase'],
            'ros1': ['ros1'],
            'braf': ['braf', 'braf v600e', 'braf v600'],
            'kras': ['kras', 'kras g12c'],
            'her2': ['her2', 'erbb2'],
            'brca': ['brca1', 'brca2'],
            'pd-l1': ['pd-l1', 'pdl1'],
            'msi': ['msi-h', 'microsatellite instability-high'],
            'tmb': ['tmb-high', 'tumor mutational burden-high']
        }
        
        # Check if patient has/doesn't have mutations mentioned in criterion
        for mutation_type, aliases in common_mutations.items():
            if any(alias in criterion_text for alias in aliases):
                has_mutation = any(any(alias in mutation for alias in aliases) for mutation in patient_mutations)
                
                # If criterion requires mutation presence
                if 'positive' in criterion_text or 'with mutation' in criterion_text:
                    if has_mutation:
                        result['matches'] = True
                        result['explanation'] = f"Patient is positive for {mutation_type} mutation"
                    else:
                        result['explanation'] = f"Patient is not positive for {mutation_type} mutation"
                    return result
                
                # If criterion requires mutation absence
                if 'negative' in criterion_text or 'without mutation' in criterion_text or 'wild-type' in criterion_text:
                    if not has_mutation:
                        result['matches'] = True
                        result['explanation'] = f"Patient is negative for {mutation_type} mutation"
                    else:
                        result['explanation'] = f"Patient is not negative for {mutation_type} mutation"
                    return result
        
        # Generic mutation check if specific types not found
        has_any_mutation = len(patient_mutations) > 0
        requires_any_mutation = 'mutation' in criterion_text and ('positive' in criterion_text or 'with mutation' in criterion_text)
        requires_no_mutation = 'mutation' in criterion_text and ('negative' in criterion_text or 'without mutation' in criterion_text)
        
        if requires_any_mutation:
            if has_any_mutation:
                result['matches'] = True
                result['explanation'] = "Patient has mutations as required"
            else:
                result['explanation'] = "Patient does not have any mutations"
        elif requires_no_mutation:
            if not has_any_mutation:
                result['matches'] = True
                result['explanation'] = "Patient has no mutations as required"
            else:
                result['explanation'] = "Patient has mutations which are not allowed"
        else:
            result['explanation'] = "Cannot determine if patient's mutation status matches criterion"
    
    # Metastasis criteria
    elif 'metastasis' in criterion_type or re.search(r'\b(?:metastases|metastasis|metastatic)\b', criterion_text):
        # Get patient metastases as a list of values
        patient_metastases = [metastasis['value'].lower() for metastasis in patient_features['metastases']]
        
        # Check for brain metastases specifically (common exclusion criterion)
        if 'brain' in criterion_text and 'metastases' in criterion_text:
            has_brain_mets = any('brain' in mets for mets in patient_metastases)
            
            # If criterion requires absence of brain metastases
            if 'no ' in criterion_text or 'without ' in criterion_text or 'absence of ' in criterion_text:
                if not has_brain_mets:
                    result['matches'] = True
                    result['explanation'] = "Patient does not have brain metastases as required"
                else:
                    result['explanation'] = "Patient has brain metastases which are not allowed"
            # If criterion requires presence of brain metastases
            else:
                if has_brain_mets:
                    result['matches'] = True
                    result['explanation'] = "Patient has brain metastases as required"
                else:
                    result['explanation'] = "Patient does not have brain metastases"
            return result
        
        # Generic metastasis check
        has_any_metastases = len(patient_metastases) > 0
        requires_metastatic = 'metastatic' in criterion_text and not ('no ' in criterion_text or 'not ' in criterion_text)
        requires_non_metastatic = 'non-metastatic' in criterion_text or ('metastatic' in criterion_text and ('no ' in criterion_text or 'not ' in criterion_text))
        
        if requires_metastatic:
            if has_any_metastases:
                result['matches'] = True
                result['explanation'] = "Patient has metastatic disease as required"
            else:
                result['explanation'] = "Patient does not have metastatic disease"
        elif requires_non_metastatic:
            if not has_any_metastases:
                result['matches'] = True
                result['explanation'] = "Patient has non-metastatic disease as required"
            else:
                result['explanation'] = "Patient has metastatic disease which does not match criterion"
        else:
            result['explanation'] = "Cannot determine if patient's metastatic status matches criterion"
    
    # Prior treatment criteria
    elif 'treatment' in criterion_type or re.search(r'\b(?:prior|previous|therapy|treatment)\b', criterion_text):
        # Get patient prior treatments as a list of values
        prior_treatments = [treatment['value'].lower() for treatment in patient_features['previous_treatments']]
        
        # Check for common treatment types
        common_treatments = {
            'chemotherapy': ['chemotherapy', 'cytotoxic'],
            'radiation': ['radiation', 'radiotherapy'],
            'immunotherapy': ['immunotherapy', 'checkpoint inhibitor', 'anti-pd-1', 'anti-pd-l1', 'anti-ctla-4'],
            'targeted therapy': ['targeted therapy', 'tyrosine kinase inhibitor', 'tki', 'egfr-tki'],
            'surgery': ['surgery', 'resection', 'surgical']
        }
        
        for treatment_type, aliases in common_treatments.items():
            if any(alias in criterion_text for alias in aliases):
                has_prior_treatment = any(any(alias in treatment for alias in aliases) for treatment in prior_treatments)
                
                # If criterion requires no prior treatment
                if 'no prior' in criterion_text or 'without prior' in criterion_text:
                    if not has_prior_treatment:
                        result['matches'] = True
                        result['explanation'] = f"Patient has not received prior {treatment_type} as required"
                    else:
                        result['explanation'] = f"Patient has received prior {treatment_type} which is not allowed"
                    return result
                
                # If criterion requires prior treatment
                if 'prior' in criterion_text or 'previous' in criterion_text:
                    if has_prior_treatment:
                        result['matches'] = True
                        result['explanation'] = f"Patient has received prior {treatment_type} as required"
                    else:
                        result['explanation'] = f"Patient has not received prior {treatment_type}"
                    return result
        
        # Check for treatment-naive (no prior treatment)
        if 'treatment-naive' in criterion_text or 'treatment naive' in criterion_text:
            if len(prior_treatments) == 0:
                result['matches'] = True
                result['explanation'] = "Patient is treatment-naive as required"
            else:
                result['explanation'] = "Patient has received prior treatment"
            return result
        
        # Generic treatment check if specific types not found
        has_any_treatment = len(prior_treatments) > 0
        requires_any_treatment = 'prior treatment' in criterion_text and not ('no prior' in criterion_text or 'without prior' in criterion_text)
        requires_no_treatment = 'no prior treatment' in criterion_text or 'without prior treatment' in criterion_text
        
        if requires_any_treatment:
            if has_any_treatment:
                result['matches'] = True
                result['explanation'] = "Patient has received prior treatment as required"
            else:
                result['explanation'] = "Patient has not received prior treatment"
        elif requires_no_treatment:
            if not has_any_treatment:
                result['matches'] = True
                result['explanation'] = "Patient has not received prior treatment as required"
            else:
                result['explanation'] = "Patient has received prior treatment which is not allowed"
        else:
            result['explanation'] = "Cannot determine if patient's treatment history matches criterion"
    
    # General and other criteria types - more lenient matching
    else:
        # For general criteria, we'll assume they match if not clearly in the categories above
        # This is a simplification that can be improved with more sophisticated matching
        result['matches'] = True
        result['explanation'] = "Criterion assumed to match (general criterion)"
    
    return result
