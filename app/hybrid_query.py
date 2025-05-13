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
        """
        Extracts features using LLM and matches with clinical trials.

        Args:
            text: Patient description text (from PDF or input).
            trials: List of all clinical trials.

        Returns:
            List[Dict[str, Any]]: List of matched trials.
        """
        logger.info("🔍 Using LLM to extract patient features...")
        prompt = f"Extract patient features (age, gender, diagnosis, etc.) from this text: {text}"
        features_response = self.llm.generate_response(prompt)

        logger.info("✅ Features extracted:")
        logger.info(features_response)

        # Parse extracted features (Assuming JSON format)
        try:
            features = json.loads(features_response)
        except json.JSONDecodeError:
            logger.error("❌ LLM response could not be parsed as JSON.")
            return []

        # Match trials using LLM
        logger.info("🔍 Using LLM to match trials based on extracted features...")
        matched_trials = []

        for trial in trials:
            prompt_match = f"Does the following patient match this trial?\nPatient: {features}\nTrial: {json.dumps(trial)}"
            match_response = self.llm.generate_response(prompt_match)
            matched_trials.append({
                "trial": trial,
                "match_response": match_response
            })

        return matched_trials


def get_hybrid_query() -> HybridQueryLLMOnly:
    """Returns an instance of the LLM-Only Hybrid Query."""
    return HybridQueryLLMOnly()
