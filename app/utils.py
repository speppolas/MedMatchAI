import os
import json
import pdfplumber
import logging
import re
from datetime import datetime, timedelta
from flask import current_app
from app.llm_processor import get_llm_processor

# Extract text from PDF
def extract_text_from_pdf(pdf_file):
    text = ""
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        if not text.strip():
            logging.error(f"❌ No text extracted from PDF: {pdf_file}")
            raise ValueError("No text extracted from PDF.")
        return text
    except Exception as e:
        logging.error(f"❌ Error extracting text from PDF: {str(e)}")
        raise Exception(f"Could not extract text from PDF: {str(e)}")

# Extract features using llama.cpp only
def extract_features(text):
    try:
        llm = get_llm_processor()
        features_json = llm.generate_response(text)

        if not features_json:
            logging.error("❌ No features extracted from LLM.")
            return None

        # ✅ Ensure JSON is clean and numeric values are strings
        features_json = re.sub(r'(?<=: )(\d+)(?=[,}\]])', r'"\1"', features_json)

        features = json.loads(features_json)
        logging.info("✅ Caratteristiche estratte con successo utilizzando llama.cpp")
        return features

    except Exception as e:
        logging.error(f"❌ Errore nell'estrazione delle caratteristiche con llama.cpp: {str(e)}")
        return None

# ✅ Format features for concise display
def format_features_concise(features):
    concise_features = {'original_text': features.get('original_text', '')}

    for key in ['age', 'gender', 'diagnosis', 'stage', 'ecog']:
        if key in features and features[key]:
            concise_features[key] = str(features[key])

    if 'mutations' in features:
        concise_features['mutations'] = [{'value': str(mut.get('value'))} for mut in features.get('mutations', [])]

    if 'metastases' in features:
        concise_features['metastases'] = [{'value': str(meta.get('value'))} for meta in features.get('metastases', [])]

    if 'previous_treatments' in features:
        concise_features['previous_treatments'] = [{'value': str(tr.get('value'))} for tr in features.get('previous_treatments', [])]

    if 'lab_values' in features:
        concise_features['lab_values'] = {key: {'value': str(value.get('value'))} for key, value in features.get('lab_values', {}).items() if value}

    return concise_features

# Clean expired files
def clean_expired_files(max_age_minutes=30):
    try:
        upload_folder = current_app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            return
        expiration_time = datetime.now() - timedelta(minutes=max_age_minutes)
        for filename in os.listdir(upload_folder):
            file_path = os.path.join(upload_folder, filename)
            if filename.endswith('.pdf') and os.path.getctime(file_path) < expiration_time.timestamp():
                os.remove(file_path)
                logging.info(f"✅ Rimosso file scaduto: {filename}")
    except Exception as e:
        logging.error(f"❌ Errore durante la pulizia dei file scaduti: {str(e)}")
