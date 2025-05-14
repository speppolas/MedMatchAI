
import os
import logging
import requests
import json

logger = logging.getLogger(__name__)

class LLMProcessor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_url = "http://0.0.0.0:11434/api/generate"

    def generate_response(self, prompt: str, 
                      temperature: float = 0.7,
                      max_tokens: int = 2048) -> str:
        """Generate response using Ollama."""
        try:
            payload = {
                "model": "mistral",
                "prompt": prompt,
                "temperature": temperature,
                "max_length": max_tokens,
                "stream": False
            }

            response = requests.post(self.api_url, json=payload)
            if response.status_code == 200:
                return response.json()['response']
            else:
                self.logger.error(f"Ollama server error: {response.status_code}")
                return "Error generating response"

        except Exception as e:
            self.logger.error(f"Error calling Ollama server: {str(e)}")
            return "Error connecting to Ollama server"

    def process_feature_extraction(self, text: str) -> dict:
        """Process feature extraction using the dedicated prompt."""
        from .prompts.feature_extraction import FEATURE_EXTRACTION_PROMPT
        prompt = FEATURE_EXTRACTION_PROMPT.format(text=text)
        response = self.generate_response(prompt, temperature=0.7)
        return self._parse_json_response(response)

    def process_trial_matching(self, patient_features: dict, trial: dict) -> dict:
        """Process trial matching with XAI using the dedicated prompt."""
        from .prompts.trial_matching import TRIAL_MATCHING_PROMPT
        prompt = TRIAL_MATCHING_PROMPT.format(
            patient_features=json.dumps(patient_features, indent=2),
            trial=json.dumps(trial, indent=2)
        )
        response = self.generate_response(prompt, temperature=0.7)
        return self._parse_json_response(response)

    def generate_trial_summary(self, match_analysis: dict) -> dict:
        """Generate a patient-friendly trial match summary."""
        from .prompts.trial_matching import TRIAL_SUMMARY_PROMPT
        prompt = TRIAL_SUMMARY_PROMPT.format(
            match_analysis=json.dumps(match_analysis, indent=2)
        )
        response = self.generate_response(prompt, temperature=0.7)
        return self._parse_json_response(response)

    def _parse_json_response(self, response: str) -> dict:
        """Parse JSON response from the LLM."""
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSONDecodeError: {e}")
            self.logger.error(f"Response causing the error: {response}")
            return {}

def get_llm_processor():
    """Returns an instance of the LLM Processor."""
    return LLMProcessor()
