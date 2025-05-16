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
import sys

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
    from app.core.llm_processor import get_llm_processor
    llm = get_llm_processor()
    # prompt = f"""
    # You are a medical AI assistant. Extract clinical features from the clinical text below. For each field, return:
    # - The extracted value
    # - And the corresponding *_source_text used to infer it

    # Return ONLY a valid JSON object with this structure:

    # {{
    # "age": integer or null,
    # "age_source_text": string or null,
    # "gender": "male" | "female" | "not mentioned",
    # "gender_source_text": string or null,
    # "diagnosis": string or null,
    # "diagnosis_source_text": string or null,
    # "stage": string or null,
    # "stage_source_text": string or null,
    # "ecog": string or null,
    # "ecog_source_text": string or null,
    # "mutations": list of strings,
    # "mutations_source_text": list of strings,
    # "metastases": list of strings,
    # "metastases_source_text": list of strings,
    # "previous_treatments": list of strings,
    # "previous_treatments_source_text": list of strings,
    # "lab_values": dict,
    # "lab_values_source_text": dict
    # }}

    # TEXT:
    # {text}

    # JSON ONLY OUTPUT:
    # """
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


    logger.info(f"Prompt sent to LLM:\n{prompt[:2000]}")  # Log the prompt snippet
    
    try:
        # Send prompt to LLM and receive response
        response = llm.generate_response(prompt)
        logger.info(f"🧠 LLM Raw Response: {response[:1000]}")

        try:
            os.makedirs("logs", exist_ok=True)
            filename = f"logs/llm_raw_debug_{int(time.time())}.json"
            with open(filename, "w") as f:
                json.dump({"prompt": prompt, "response": response}, f, indent=2)
            logger.info(f"💾 Saved LLM debug output to {filename}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to write raw debug log: {e}")
        
        
        # Parse the LLM response to get 'llm_text'
        resp_json = json.loads(response)
        llm_text = json.loads(resp_json['response'])

        if not isinstance(llm_text, dict):
            logger.error(f"❌ LLM response is not a valid JSON object: {llm_text}")
            return {}

        logger.info(f"✅ Extracted Features (llm_text): {json.dumps(llm_text, indent=2)}")
        return llm_text

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON decoding error: {str(e)} - Raw response: {response}")
        return {}
    except Exception as e:
        logger.error(f"❌ Unexpected error in feature extraction: {e}")
        return {}
    
    # return llm_text
    # if not llm_text:
    #     logger.error("❌ LLM response 'response' field is empty")
    #     return {}

    # try:
    #     data = json.loads(llm_text)
    #     validated = ClinicalFeatures(**data)
    #     print(f"✅ Extracted fields summary: {json.dumps(validated.dict(), indent=2)}")
    #     return validated.dict()
    # except json.JSONDecodeError as e:
    #     print(f"❌ Failed to parse JSON from LLM 'response' text: {e}, text: {llm_text}")
    # except ValidationError as ve:
    #     print(f"❌ Schema Validation Error: {ve}")
    # except Exception as e:
    #     print(f"❌ Unexpected error: {e}")
    # return llm_text

def highlight_sources(text: str, features: Dict[str, Any]) -> str:
    for key, value in features.items():
        if key.endswith('_source_text') and isinstance(value, str) and value.strip():
            try:
                escaped = re.escape(value.strip())
                text = re.sub(f"({escaped})", r'<mark>\1</mark>', text, flags=re.IGNORECASE)
            except Exception as e:
                logger.warning(f"⚠️ Failed to highlight '{value}': {e}")
    return text


def match_trials_llm(llm_text: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Perform fast, efficient trial matching using a Hybrid (Rule + LLM) approach.
    """
    llm = get_llm_processor()
    trials = get_all_trials()  # Load all available trials

    if not trials:
        logger.error("❌ No trials found in database")
        return []

    matched_trials = []

    logger.info("🔍 Hybrid Matching: Fast Pre-Filter + LLM Matching...")
    
    # ✅ Step 1: Fast Rule-Based Pre-Filter (age, diagnosis, etc.)
    filtered_trials = []
    for trial in trials:
        if 'conditions' in trial and llm_text.get('diagnosis') and llm_text['diagnosis'].lower() in trial['conditions'].lower():
            filtered_trials.append(trial)

    logger.info(f"✅ {len(filtered_trials)} trials pre-selected for LLM matching.")

    # ✅ Step 2: LLM Matching Only on Pre-Filtered Trials
    for trial in filtered_trials:
        prompt = f"""
Does the following patient match this trial?

PATIENT:
{json.dumps(llm_text, indent=2)}

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
                "title": trial.get("title", "Unknown Trial"),
                "description": trial.get("description", "No description provided."),
                "match_score": match_result.get("match_score", 0),
                "recommendation": match_result.get("overall_recommendation", "UNKNOWN"),
                "criteria_analysis": match_result.get("criteria_analysis", {}),
                "summary": match_result.get("summary", "No summary available.")
            })
        except json.JSONDecodeError:
            logger.error(f"❌ LLM response could not be parsed for trial matching: {response}")
            continue

    # ✅ Step 3: Sort by Match Score (High to Low)
    matched_trials.sort(key=lambda x: x['match_score'], reverse=True)
    logger.info(f"✅ Trial matching completed. {len(matched_trials)} trials matched.")
    
    return matched_trials


def format_criteria(criteria_list):
    """Format criteria list into a readable string for the LLM prompt"""
    if not criteria_list:
        return "None"
    
    formatted = []
    for i, criterion in enumerate(criteria_list):
        # If criterion is a string
        if isinstance(criterion, str):
            formatted.append(f"{i+1}. {criterion}")
        # If criterion is a dict
        elif isinstance(criterion, dict):
            criterion_id = criterion.get('id', i+1)
            criterion_text = criterion.get('text', criterion.get('description', 'No description'))
            formatted.append(f"{criterion_id}. {criterion_text}")
    
    return "\n".join(formatted)


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