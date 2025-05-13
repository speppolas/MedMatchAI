
import os
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

OLLAMA_API_URL = "http://localhost:11434/api/generate"

class OllamaProcessor:
    def __init__(self):
        self.model = "mistral"
        
    def generate(self, prompt: str, max_tokens: int = 512) -> Optional[str]:
        try:
            response = requests.post(OLLAMA_API_URL, json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "max_tokens": max_tokens
            })
            if response.status_code == 200:
                return response.json().get('response', '')
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error calling Ollama API: {e}")
            return None

    @staticmethod
    def is_available() -> bool:
        try:
            requests.get("http://localhost:11434/api/health")
            return True
        except:
            return False
