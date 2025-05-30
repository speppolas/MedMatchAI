import os
import json
import logging
import subprocess
from flask import Blueprint, request, jsonify, render_template, current_app, send_from_directory
from werkzeug.utils import secure_filename
from app.api import bp
from app.utils import (
    extract_text_from_pdf,
    clean_expired_files,
    format_features_concise,
    get_all_trials
)
from app.core.feature_extraction import highlight_sources, extract_features_with_llm, match_trials_llm
from app.core.llm_processor import get_llm_processor

bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)
       
 
@bp.route('/')
def index():
    logger.info("✅ Accessed home page")
    return render_template('index.html')


@bp.route('/settings')
def settings_page():
    return render_template('settings.html')

@bp.route('/api/settings', methods=['GET', 'POST'])
def update_settings():
    if request.method == 'POST':
        data = request.json
        try:
            with open("config.json", "w") as f:
                json.dump(data, f, indent=4)
            logger.info("✅ Settings updated")
            return jsonify({"status": "success", "message": "Settings updated successfully"}), 200
        except Exception as e:
            logger.error(f"❌ Failed to update settings: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    elif request.method == 'GET':
        try:
            with open("config.json", "r") as f:
                settings = json.load(f)
            return jsonify(settings), 200
        except Exception as e:
            logger.error(f"❌ Failed to retrieve settings: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
        


@bp.route('/api/models')
def get_models():
    try:
        output = subprocess.check_output(['ollama', 'list'], text=True)
        models = []
        for line in output.splitlines()[1:]:
            parts = line.split()
            if parts:
                models.append(parts[0])
        return jsonify(models)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/process', methods=['POST'])
def process():
    try:
        upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)

        file = request.files.get('file')
        raw_text = request.form.get('text', '').strip()
        text = ''
        pdf_filename = None

        if file and file.filename.endswith('.pdf'):
            pdf_filename = secure_filename(file.filename)
            upload_path = os.path.join(upload_dir, pdf_filename)
            file.save(upload_path)

            with open(upload_path, 'rb') as f:
                text = extract_text_from_pdf(f)

            logger.info(f"📄 PDF '{pdf_filename}' uploaded and text extracted ({len(text)} chars)")

        elif raw_text:
            text = raw_text
            logger.info(f"📝 Raw text received ({len(text)} chars)")

        else:
            logger.warning("❌ No input provided")
            return jsonify({'error': 'Please upload a PDF or enter clinical text.'}), 400

        if not text:
            logger.warning("❌ Extracted text is empty")
            return jsonify({'error': 'Extracted text is empty.'}), 400

        logger.info("🤖 Calling LLM for feature extraction...")
        llm_text = extract_features_with_llm(text)

        if not isinstance(llm_text, dict) or not llm_text:
            logger.error("❌ Invalid or empty response from LLM")
            return jsonify({'error': 'LLM returned an invalid or empty response.'}), 500
        logger.info(f"✅ Extracted Features: {llm_text}")
        # highlighted_text = highlight_sources(text, features)
    #     print(features)
    #     return jsonify({
    #         'features': features,
    #         'text': text,
    #         'text_highlighted': 'highlighted_text',
    #         'pdf_filename': pdf_filename
    #     })

    # except Exception as e:
    #     logger.exception("❌ Unhandled exception in /process")
    #     return jsonify({'error': str(e)}), 500
    
        # Step 3: Use extracted features for trial matching
        logger.info("🤖 Calling LLM for trial matching...")
        matched_trials = match_trials_llm(llm_text)
        return jsonify({
            'features': llm_text,
            'text': text,
            'pdf_filename': pdf_filename,
            'matched_trials': matched_trials
        })
    except Exception as e:
        logger.exception("❌ Unhandled exception in /process")
        return jsonify({'error': str(e)}), 500
        
        
        
        
        
        '''
        llm = get_llm_processor()
        trials = get_all_trials()  # Load all available trials
        matched_trials = []

        for trial in trials:
            prompt = f"""
Does the following patient match this trial?

PATIENT:
{json.dumps(features, indent=2)}

TRIAL:
{json.dumps(trial, indent=2)}

Return a JSON with:
{{
  "match_score": integer (0 to 100),
  "overall_recommendation": string,
  "criteria_analysis": dict,
  "summary": string
}}
"""
            response = llm.generate_response(prompt)
            try:
                match_result = json.loads(response)
                matched_trials.append({
                    "trial_id": trial.get("id"),
                    "confidence": match_result.get("match_score", 0),
                    "recommendation": match_result.get("overall_recommendation", "UNKNOWN"),
                    "analysis": match_result.get("criteria_analysis", {}),
                    "summary": match_result.get("summary", "No summary available.")
                })
            except json.JSONDecodeError:
                logger.error(f"❌ LLM response could not be parsed for trial matching: {response}")
                continue
        
        # Sort matched trials by confidence
        matched_trials.sort(key=lambda x: x['confidence'], reverse=True)
        logger.info("✅ Trial matching completed")

        return jsonify({
            'features': features,
            'text': text,
            'text_highlighted': 'highlighted_text',
            'pdf_filename': pdf_filename,
            'matched_trials': matched_trials
        })

    except Exception as e:
        logger.exception("❌ Unhandled exception in /process")
        return jsonify({'error': str(e)}), 500
'''



@bp.route('/api/trials', methods=['GET'])
def get_trials():
    try:
        trials = get_all_trials()
        return jsonify(trials)
    except Exception as e:
        logger.error(f"❌ Failed to retrieve trials: {e}")
        return jsonify({'error': 'Unable to retrieve trials'}), 500

@bp.route('/trials')
def trials_page():
    return render_template('trials.html')

@bp.route('/view-pdf/<path:filename>')
def view_pdf(filename):
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    return send_from_directory(upload_folder, filename)

@bp.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(current_app.root_path, 'static', 'img'),
        'logo.svg',
        mimetype='image/svg+xml'
    )

# Clean Expired Files
@bp.route('/api/clean', methods=['POST'])
def clean_files():
    try:
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        clean_expired_files(upload_folder)
        logger.info("✅ Expired files cleaned")
        return jsonify({'status': 'success', 'message': 'Expired files cleaned successfully'}), 200
    except Exception as e:
        logger.error(f"❌ Failed to clean files: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500