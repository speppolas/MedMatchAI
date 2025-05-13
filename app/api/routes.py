import os
import json
import re
import logging
import uuid
from werkzeug.utils import secure_filename
from flask import render_template, request, jsonify, current_app, send_from_directory, session, abort, Response
from werkzeug.utils import secure_filename
from app.api import bp
from app.utils import extract_text_from_pdf, extract_features, clean_expired_files, format_features_concise
from app.llm_processor import get_llm_processor

logger = logging.getLogger(__name__)

@bp.route('/')
def index():
    """Render the main application page."""
    logger.info("✅ Index route accessed")
    return render_template('index.html')

@bp.route('/health')
def health():
    """Health check endpoint."""
    return {"status": "ok"}

@bp.route('/trials')
def trials():
    """Render the trials listing page."""
    return render_template('trials.html')

@bp.route('/view-pdf/<filename>')
def view_pdf(filename):
    """
    Securely view an uploaded PDF.
    """
    try:
        session_filename = session.get('pdf_filename')
        if not session_filename or session_filename != filename:
            logger.warning(f"Unauthorized access attempt to PDF: {filename}")
            abort(403)
        
        clean_expired_files()
        pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(pdf_path):
            logger.warning(f"Requested PDF not found: {filename}")
            abort(404)
        
        return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename, as_attachment=False)
    except Exception as e:
        logger.error(f"Error accessing PDF {filename}: {str(e)}")

def _basic_criteria_match(trial, basic_criteria):
    """Quick pre-filter for basic matching criteria."""
    try:
        # Check age criteria if available
        if basic_criteria['age']:
            min_age = trial.get('min_age')
            max_age = trial.get('max_age')
            if min_age and int(basic_criteria['age']) < int(min_age):
                return False
            if max_age and int(basic_criteria['age']) > int(max_age):
                return False
                
        # Check gender criteria if specified
        if basic_criteria['gender'] and trial.get('gender'):
            if trial['gender'].lower() != 'any' and \
               trial['gender'].lower() != basic_criteria['gender'].lower():
                return False
                
        # Basic diagnosis match (more detailed matching done by LLM)
        if basic_criteria['diagnosis'] and trial.get('conditions'):
            diagnosis_lower = basic_criteria['diagnosis'].lower()
            if not any(c.lower() in diagnosis_lower or diagnosis_lower in c.lower() 
                      for c in trial['conditions']):
                return False
                
        return True
    except Exception as e:
        logger.error(f"Error in basic criteria matching: {str(e)}")
        return True  # On error, let the LLM do the detailed matching

        return jsonify({'error': f'Error accessing PDF: {str(e)}'}), 500

@bp.route('/process', methods=['POST'])
def process():
    """
    Process uploaded PDF or text input and find matching trials.
    """
    try:
        text = ""
        pdf_filename = None
        
        # Ensure upload folder exists
        if not os.path.exists(current_app.config['UPLOAD_FOLDER']):
            os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            if file.filename.endswith('.pdf'):
                unique_filename = f"{str(uuid.uuid4())}.pdf"
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(file_path)
                session['pdf_filename'] = unique_filename
                pdf_filename = unique_filename
                text = extract_text_from_pdf(file_path)
            else:
                return jsonify({'error': 'Only PDF files are supported'}), 400
        elif 'text' in request.form and request.form['text'].strip():
            text = request.form['text']
        else:
            return jsonify({'error': 'No input provided. Please upload a PDF or enter text.'}), 400

        # Try feature extraction
        try:
            from app.core.feature_extraction import extract_features, format_features_concise
            
            # Extract features
            features = extract_features(text)
            
            # Format features for display
            concise_features = format_features_concise(features)
            
            # Get matching trials (using basic matching for now)
            from app.utils import match_trials
            matched_trials = match_trials(features)
            
            return jsonify({
                'features': concise_features,
                'matches': matched_trials,
                'text': text,
                'pdf_filename': pdf_filename
            })
            
        except Exception as e:
            logger.error(f"Error in feature extraction: {str(e)}")
            return jsonify({'error': 'Failed to extract features from document'}), 500
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500
        
        return jsonify({
            'features': concise_features,
            'matches': matched_trials,
            'text': text,
            'pdf_filename': pdf_filename
        })
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500


def match_trials_llm(patient_features):
    """
    Enhanced trial matching with XAI using a structured approach:
    1. Pre-filter trials based on basic criteria
    2. Detailed LLM analysis with reasoning for each criterion
    3. Confidence scoring with explanation

    Args:
        patient_features: Extracted patient features from patient document
        
    Returns:
        list: List of matching trials with detailed XAI explanations
    """
    try:
        logger.info("🔍 Starting enhanced trial matching with XAI...")
        llm = get_llm_processor()
        
        # Load clinical trials from Istituto Nazionale Tumori
        trials = get_all_trials_json()
        if not trials:
            logger.error("No trials found in database")
            return []
            
        # Pre-filter trials based on basic criteria
        basic_criteria = {
            'age': patient_features.get('age', {}).get('value'),
            'gender': patient_features.get('gender', {}).get('value'),
            'diagnosis': patient_features.get('diagnosis', {}).get('value')
        }
        
        potential_trials = [
            trial for trial in trials 
            if _basic_criteria_match(trial, basic_criteria)
        ]
        
        logger.info(f"Pre-filtered to {len(potential_trials)} potentially matching trials")
        matched_trials = []
        
        # Enhanced prompt template for XAI reasoning
        prompt_template = """
        You are a clinical trial matching expert. Analyze if this patient is eligible for the clinical trial.
        Provide detailed reasoning for each criterion.
        
        Patient Profile:
        {patient_features}
        
        Trial Information:
        - Name: {trial_name}
        - ID: {trial_id}
        - Phase: {trial_phase}
        - Status: {trial_status}
        
        Criteria Analysis Required:
        1. Inclusion Criteria: {inclusion_criteria}
        2. Exclusion Criteria: {exclusion_criteria}
        3. Disease Specific Requirements: {conditions}
        
        For each criterion, provide:
        1. Whether it is met (true/false)
        2. Confidence level (0-100%)
        3. Specific evidence from patient profile
        4. Clinical reasoning for the decision
        
        Provide a structured analysis in JSON format:
        {
            "eligible": true/false,
            "confidence_score": 0-1,
            "reasoning": {
                "inclusion_analysis": [
                    {"criterion": "criterion text", "met": true/false, "explanation": "detailed explanation"}
                ],
                "exclusion_analysis": [
                    {"criterion": "criterion text", "met": true/false, "explanation": "detailed explanation"}
                ],
                "key_factors": ["list of decisive factors"],
                "summary": "concise summary of decision"
            }
        }
        """
        
        for trial in trials:
            # Create structured prompt for matching
            prompt = f"""
            Determine if the patient matches this clinical trial. Return ONLY a JSON object with format:
            {{
                "matches": true/false,
                "reason": "brief explanation of match or mismatch",
                "confidence": number between 0-1
            }}

            Patient features:
            {json.dumps(patient_features, indent=2)}

            Trial criteria:
            {json.dumps(trial, indent=2)}

            JSON response:
            """
            
            # Generate detailed analysis for each trial
            prompt = prompt_template.format(
                patient_features=json.dumps(patient_features, indent=2),
                trial_name=trial.get('title', ''),
                trial_id=trial.get('id', ''),
                inclusion_criteria=json.dumps(trial.get('inclusion_criteria', []), indent=2),
                exclusion_criteria=json.dumps(trial.get('exclusion_criteria', []), indent=2)
            )
            
            response = llm.generate_response(prompt)
            analysis = json.loads(response)
            
            if analysis.get('eligible', False) and analysis.get('confidence_score', 0) > 0.7:
                matched_trials.append({
                    'trial': trial,
                    'analysis': analysis['reasoning'],
                    'confidence_score': analysis['confidence_score'],
                    'summary': analysis['reasoning']['summary']
                })
            
            # Log detailed analysis for transparency
            logger.info(f"Trial {trial.get('id')} analysis: {json.dumps(analysis['reasoning'], indent=2)}")
        
        # Sort by confidence
        matched_trials.sort(key=lambda x: x['confidence'], reverse=True)
        return matched_trials[:10]  # Return top 10 matches
        
    except Exception as e:
        logger.error(f"Error in trial matching: {str(e)}")
        return []

        for trial in trials:
            # Use LLM to evaluate if the patient matches the trial
            prompt = f"""
            Does this patient match the following trial?
            Patient: {json.dumps(patient_features)}
            Trial: {json.dumps(trial)}
            Answer in JSON: {{"match": true/false, "reason": "explanation"}}
            """
            response = llm.generate_response(prompt)
            try:
                match_data = json.loads(response)
                if match_data.get("match"):
                    matched_trials.append({
                        "trial": trial,
                        "match": True,
                        "reason": match_data.get("reason", "No reason provided.")
                    })
            except json.JSONDecodeError:
                logger.error(f"LLM response could not be parsed: {response}")
                continue
        
        logger.info(f"✅ {len(matched_trials)} trials matched using LLM.")
        return matched_trials
    except Exception as e:
        logger.error(f"Error matching trials: {str(e)}")
        return []

def get_all_trials_json():
    """
    Load all available clinical trials from a JSON file.
    
    Returns:
        list: List of clinical trials
    """
    try:
        with open('trials_int.json', 'r') as f:
            trials = json.load(f)
        logger.info(f"✅ Loaded {len(trials)} clinical trials from JSON.")
        return trials
    except Exception as e:
        logger.error(f"Error loading trials from JSON: {str(e)}")
        return []

def extract_features(text):
    """
    Extract patient features using llama.cpp (LLM).
    
    Args:
        text (str): Patient description text.
    
    Returns:
        dict: Extracted patient features.
    """
    llm = get_llm_processor()
    prompt = f"""
    Extract all relevant patient features from the following text in JSON format:
    Text: "{text}"
    JSON Format:
    {{
        "age": "value or None",
        "gender": "value or None",
        "diagnosis": "value or None",
        "stage": "value or None",
        "ECOG": "value or None",
        "mutations": ["mutation1", "mutation2"],
        "previous_treatments": ["treatment1", "treatment2"],
        "metastases": ["site1", "site2"],
        "comorbidities": ["condition1", "condition2"]
    }}
    """
    response = llm.generate_response(prompt)
    
    try:
        features = json.loads(response)
        logger.info(f"✅ Extracted features: {features}")
        return features
    except json.JSONDecodeError:
        logger.error(f"❌ LLM response could not be parsed as JSON: {response}")
        return {}

