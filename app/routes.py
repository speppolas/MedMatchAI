import os
import json
import logging
from flask import render_template, request, jsonify, current_app
from app import app
from app.utils import extract_text_from_pdf, extract_features, match_trials

@app.route('/')
def index():
    """Render the main application page."""
    return render_template('index.html')

@app.route('/process', methods=['POST'])
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
        trial_matches = match_trials(features)
        
        # Return extracted features and matching trials
        return jsonify({
            'features': features,
            'matches': trial_matches,
            'text': text
        })
        
    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500
