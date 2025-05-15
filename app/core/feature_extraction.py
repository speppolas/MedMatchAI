import os
import time
import re
import json
import logging
import pdfplumber
from typing import Dict, Any, Union, List
from datetime import datetime, timedelta
from flask import current_app
from app.core.llm_processor import get_llm_processor
from app.core.schema_validation import ClinicalFeatures, ValidationError
from app.utils import get_all_trials

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_file: Union[str, bytes]) -> str:
    try:
        text = ""
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "")
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise Exception(f"Unable to extract text from PDF: {str(e)}")

def extract_features_with_llm(text: str) -> Dict[str, Any]:
    llm = get_llm_processor()
    prompt = f"""You are a clinical NLP model. Extract ONLY the following JSON object from the text below, with no explanation or extra text. Use keys:

{{
  "age": int or null,
  "gender": "male", "female", or "not mentioned",
  "diagnosis": "NSCLC", "SCLC", "other", or "not mentioned",
  "stage": "I", "II", "III", "IV", or "not mentioned",
  "ecog": "0" to "4" or "not mentioned",
  "mutations": list of gene names or "none",
  "metastases": list or empty list,
  "previous_treatments": list,
  "lab_values": dict of test name to value
}}

Text:
{text}

"""
    logger.info(f"🔍 LLM Prompt Length (chars): {len(prompt)}")
    logger.info(f"Prompt sent to LLM:\n{prompt[:2000]}")  # Log the prompt snippet
    
    response = llm.generate_response(prompt, max_tokens=llm.max_tokens)
    logger.info("🧠 LLM Raw Response: %s", response[:1000])

    # Write debug log with timestamped filename
    try:
        os.makedirs("logs", exist_ok=True)
        filename = f"logs/llm_raw_debug_{int(time.time())}.json"
        with open(filename, "w") as f:
            json.dump({"prompt": prompt, "response": response}, f, indent=2)
        logger.info(f"💾 Saved LLM debug output to {filename}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to write raw debug log: {e}")

    # Then proceed parsing the response JSON as before
    try:
        resp_json = json.loads(response)
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse outer JSON from LLM response: {e}, raw: {response}")
        return {}

    llm_text = resp_json.get("response", "").strip()
    if not llm_text:
        logger.error("❌ LLM response 'response' field is empty")
        return {}

    try:
        data = json.loads(llm_text)
        validated = ClinicalFeatures(**data)
        logger.info(f"✅ Extracted fields summary: {json.dumps(validated.dict(), indent=2)}")
        return validated.dict()
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse JSON from LLM 'response' text: {e}, text: {llm_text}")
    except ValidationError as ve:
        logger.error(f"❌ Schema Validation Error: {ve}")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
    return {}

def highlight_sources(text: str, features: Dict[str, Any]) -> str:
    for key, value in features.items():
        if key.endswith('_source_text') and isinstance(value, str) and value.strip():
            try:
                escaped = re.escape(value.strip())
                text = re.sub(f"({escaped})", r'<mark>\1</mark>', text, flags=re.IGNORECASE)
            except Exception as e:
                logger.warning(f"⚠️ Failed to highlight '{value}': {e}")
    return text

def match_trials_llm(patient_features: Dict[str, Any]) -> List[Dict[str, Any]]:
    llm = get_llm_processor()
    trials = get_all_trials()

    if not trials:
        logger.error("No trials found in database")
        return []

    matched_trials = []

    for trial in trials:
        prompt = f"""
Does the following patient match this trial?

PATIENT:
{json.dumps(patient_features, indent=2)}

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
        response = llm.generate_response(prompt, max_tokens=llm.max_tokens)
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
            logger.error(f"❌ LLM response could not be parsed: {response}")
            continue

    matched_trials.sort(key=lambda x: x['confidence'], reverse=True)
    return matched_trials

def clean_expired_files(upload_folder: str = 'uploads', max_age_minutes: int = 30) -> None:
    try:
        expiration_time = datetime.now() - timedelta(minutes=max_age_minutes)
        if not os.path.exists(upload_folder):
            logger.warning(f"⚠️ Upload folder does not exist: {upload_folder}")
            return

        for filename in os.listdir(upload_folder):
            file_path = os.path.join(upload_folder, filename)
            if os.path.isfile(file_path) and filename.endswith('.pdf'):
                file_creation_time = datetime.fromtimestamp(os.path.getctime(file_path))
                if file_creation_time < expiration_time:
                    os.remove(file_path)
                    logger.info(f"🗑️ Removed expired file: {filename}")
    except Exception as e:
        logger.error(f"❌ Error cleaning expired files: {str(e)}")
