import os
import json
import re
import logging
import uuid
from werkzeug.utils import secure_filename
from flask import render_template, request, jsonify, current_app, send_from_directory, session, abort
from app import bp
from app.utils import extract_text_from_pdf, extract_features, clean_expired_files, format_features_concise
from app.llm_processor import get_llm_processor

logger = logging.getLogger(__name__)

@bp.route('/')
def index():
    """Render the main application page."""
    logger.info("✅ Index route accessed")
    return render_template('index.html')

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
        return jsonify({'error': f'Error accessing PDF: {str(e)}'}), 500

@bp.route('/process', methods=['POST'])
def process():
    """
    Process uploaded PDF or text input and find matching trials using LLM (llama.cpp).
    """
    try:
        text = ""
        pdf_filename = None
        
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
        
        # Use llama.cpp (LLM) to extract features
        features = extract_features(text)
        concise_features = format_features_concise(features)
        
        # Use LLM to match with clinical trials
        matched_trials = match_trials_llm(features)
        
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
    Match patient features with clinical trials using LLM (llama.cpp).

    Args:
        patient_features: Extracted patient features (from LLM).
        
    Returns:
        list: List of matching trials with details.
    """
    try:
        logger.info("🔍 Matching trials using LLM (llama.cpp)...")
        llm = get_llm_processor()
        
        # Load clinical trials (from JSON for simplicity)
        trials = get_all_trials_json()
        matched_trials = []

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

