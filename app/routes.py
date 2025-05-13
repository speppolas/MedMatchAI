import os
import json
import re
import logging
import uuid
import threading  # ✅ Import threading for background processing
from werkzeug.utils import secure_filename
from flask import render_template, request, jsonify, current_app, send_from_directory, session, abort
from app import bp, socketio
from app.utils import extract_text_from_pdf, extract_features, clean_expired_files, format_features_concise  # type: ignore
from app.llm_processor import get_llm_processor 

logger = logging.getLogger(__name__)

@bp.route('/')
def index():
    logger.info("✅ Index route accessed")
    return render_template('index.html')

@bp.route('/trials')
def trials():
    return render_template('trials.html')

@bp.route('/process', methods=['POST'])
def process():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded.'}), 400

        uploaded_file = request.files['file']
        if uploaded_file.filename == '':
            return jsonify({'error': 'No selected file.'}), 400

        emit_progress("🔍 Extracting text from PDF...")
        text = extract_text_from_pdf(uploaded_file)

        if not text.strip():
            logger.error("❌ No text extracted from PDF.")
            return jsonify({'error': 'Failed to extract text from PDF.'}), 400

        emit_progress("✅ Text extracted successfully.")

        thread = threading.Thread(target=extract_features_and_send, args=(text,))
        thread.start()

        return jsonify({'message': 'Feature extraction in progress. Please wait.'}), 202
    except Exception as e:
        logger.error(f"❌ Error starting the extraction thread: {str(e)}")
        return jsonify({'error': f'Error starting the extraction thread: {str(e)}'}), 500


def extract_features_and_send(text):
    try:
        llm = get_llm_processor()
        emit_progress("🔍 Extracting features using LLM...")

        clean_text = "\n".join(str(line).strip() for line in text.splitlines() if str(line).strip())

        prompt_text = f"Extract all relevant patient features from the following text in JSON format:\n\n{clean_text}"
        logger.info(f"🔧 Complete Prompt Text for LLM:\n{prompt_text}")

        response = llm.generate_response(prompt_text)

        if not response:
            emit_progress("❌ Failed to extract features. Please try again.")
            logger.error("❌ No response from LLM.")
            socketio.emit('llm_response', {'error': 'Failed to extract features. Please try again.'})
            return

        # ✅ Formatta JSON come stringa e utilizza format_features_concise
        features = json.loads(response)
        concise_features = format_features_concise(features)

        emit_progress("✅ Features extracted successfully.")
        logger.info(f"✅ LLM JSON Response: {concise_features}")

        socketio.emit('llm_response', {'features': concise_features, 'text': clean_text})
    except Exception as e:
        logger.error(f"❌ Error processing request: {str(e)}")
        emit_progress(f"❌ Error processing request: {str(e)}")
        socketio.emit('llm_response', {'error': str(e)})


def emit_progress(message):
    logger.info(f"🔧 Progress Update: {message}")
    try:
        socketio.emit('progress_update', {'message': message})
    except Exception as e:
        logger.warning(f"❌ Error emitting progress: {str(e)}")
