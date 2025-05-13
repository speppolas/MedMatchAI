import logging
from typing import Dict, Any, List
from app.llm_processor import get_llm_processor
import json

logger = logging.getLogger(__name__)

class HybridQueryLLMOnly:
    """
    LLM-Only Hybrid Query System.
    - Directly uses llama.cpp for feature extraction and trial matching.
    """

    def __init__(self):
        self.llm = get_llm_processor()

    def filter_trials_by_criteria(self, text: str, trials: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        logger.info("🔍 Using LLM to extract patient features...")

        # ✅ Improved Prompt (Force JSON Response)
        prompt = f"""
        You are an advanced language model. Extract all relevant patient features from the following text in JSON format only:
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
        Do not provide any explanation, only JSON.
        """

        features_response = self.llm.generate_response(prompt)

        logger.info("✅ Raw Features Response:")
        logger.info(features_response)

        # ✅ Enhanced JSON Parsing with Error Handling
        features = self._parse_llm_response(features_response)
        if not features:
            logger.error("❌ Failed to extract patient features. Exiting.")
            return []

        logger.info("✅ Extracted Features:")
        logger.info(features)


        # ✅ Using Extracted Features to Match Trials
        logger.info("🔍 Using LLM to match trials based on extracted features...")
        matched_trials = []

        for trial in trials:
            prompt_match = f"""
            Does this patient match the following trial?
            Patient: {json.dumps(features, indent=2)}
            Trial: {json.dumps(trial, indent=2)}
            Answer in JSON: {{"match": true/false, "reason": "explanation"}}
            """
            match_response = self.llm.generate_response(prompt_match)
            match_data = self._parse_llm_response(match_response)
            
            if match_data and match_data.get("match"):
                matched_trials.append({
                    "trial": trial,
                    "match": True,
                    "reason": match_data.get("reason", "No reason provided.")
                })
            else:
                matched_trials.append({
                    "trial": trial,
                    "match": False,
                    "reason": match_data.get("reason", "LLM did not provide a valid reason.")
                })

        logger.info(f"✅ {len(matched_trials)} trials matched using LLM.")
        return matched_trials

    def _parse_llm_response(self, response: str) -> dict:
        """
        Parses and validates the LLM response as JSON.
        """
        if not response or not response.strip():
            logger.error("❌ LLM response is empty.")
            return None

        # ✅ Clean the response to focus only on JSON
        response = response.strip()
        json_start = response.find("{")
        json_end = response.rfind("}") + 1

        if json_start == -1 or json_end == -1:
            logger.error("❌ LLM response does not contain valid JSON.")
            return None

        json_text = response[json_start:json_end]

        try:
            data = json.loads(json_text)
            if isinstance(data, dict):
                return data
            else:
                logger.error("❌ LLM response is not a valid JSON object.")
                return None
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON Parsing Error: {str(e)}")
            logger.error(f"❌ Raw Response: {response}")
            return None


def get_hybrid_query() -> HybridQueryLLMOnly:
    """Returns an instance of the LLM-Only Hybrid Query."""
    return HybridQueryLLMOnly()
