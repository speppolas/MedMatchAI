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
from app.core.llm_processor import get_llm_processor

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

@bp.route('/validate-int-trials')
def validate_int_trials():
    """Validate that all required INT trials are present and complete."""
    required_nct_ids = [
        'NCT04613596', 'NCT05224141', 'NCT05261399', 'NCT05261399',
        'NCT05298423', 'NCT06312137', 'NCT06305754', 'NCT05920356',
        'NCT06074588', 'NCT05609968', 'NCT05703997', 'NCT06422143',
        'NCT05676931', 'NCT06452277', 'NCT06170788', 'NCT06077760',
        'NCT06119581', 'NCT06117774'
    ]
    
    trials = get_all_trials_json()
    found_trials = {}
    missing_trials = []
    
    for nct_id in required_nct_ids:
        found = False
        for trial in trials:
            if trial.get('id') == nct_id:
                found = True
                # Validate trial completeness
                has_criteria = (
                    trial.get('inclusion_criteria') and 
                    trial.get('exclusion_criteria')
                )
                found_trials[nct_id] = {
                    'found': True,
                    'has_criteria': has_criteria,
                    'title': trial.get('title', 'No title')
                }
                break
        if not found:
            missing_trials.append(nct_id)
            found_trials[nct_id] = {'found': False}
    
    return jsonify({
        'status': 'ok' if not missing_trials else 'incomplete',
        'total_required': len(required_nct_ids),
        'found': len(required_nct_ids) - len(missing_trials),
        'missing': missing_trials,
        'trials': found_trials
    })

@bp.route('/trials')
def trials():
    """Render the trials listing page."""
    return render_template('trials.html')

@bp.route('/api/trials')
def get_trials():
    """API endpoint to get all trials."""
    try:
        from app.utils import get_all_trials
        trials_data = get_all_trials()
        if not trials_data:
            logger.error("No trials data found")
            return jsonify({'error': 'No trials data found'}), 404
        return jsonify(trials_data)
    except Exception as e:
        logger.error(f"Error loading trials: {str(e)}")
        return jsonify({'error': f'Error loading trials: {str(e)}'}), 500

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
                text = extract_text_from_pdf(file.stream)
                pdf_filename = None  # We don't save files anymore
            else:
                return jsonify({'error': 'Only PDF files are supported'}), 400
        elif 'text' in request.form and request.form['text'].strip():
            text = request.form['text']
        else:
            return jsonify({'error': 'No input provided. Please upload a PDF or enter text.'}), 400

        # Extract features using llama.cpp
        try:
            from app.core.llm_processor import get_llm_processor
            llm = get_llm_processor()

            # Extract features
            feature_prompt = f"""
            Extract clinical features from this patient text in JSON format:
            {text}

            Return ONLY a JSON object with:
            - age: number
            - gender: "male" or "female"
            - diagnosis: main cancer diagnosis
            - stage: cancer stage
            - mutations: list of genetic mutations
            - metastases: list of metastatic sites
            - previous_treatments: list of previous treatments
            """

            features_json = llm.generate_response(feature_prompt)
            import json
            features = json.loads(features_json)

            # Find matching trials
            trial_prompt = f"""
            Given these patient features:
            {json.dumps(features, indent=2)}

            Find matching clinical trials from this list:
            {json.dumps(get_all_trials_json(), indent=2)}

            Return ONLY a JSON array of matching trials with confidence scores:
            [
              {{"trial_id": "...", "confidence": 0.9, "reason": "..."}}
            ]
            """

            matches_json = llm.generate_response(trial_prompt)
            matched_trials = json.loads(matches_json)

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