import os
import logging
import requests
import json

logger = logging.getLogger(__name__)

# Carica i parametri dal file di configurazione
def load_config():
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
        return config
    except Exception as e:
        logger.error(f"❌ Unable to load config file: {e}")
        return {
            "LLM_MODEL": "llama3.1:8b-custom",
            "LLM_CONTEXT_SIZE": 131072,
            "LLM_TEMPERATURE": 0.1
        }

class LLMProcessor:
    def __init__(self):
        config = load_config()
        self.api_url = os.getenv("OLLAMA_SERVER_URL", "http://127.0.0.1:11434/api/generate")
        self.model = config.get("LLM_MODEL")
        self.context_size = config.get("LLM_CONTEXT_SIZE")
        self.temperature = config.get("LLM_TEMPERATURE")
        self.max_tokens = min(self.context_size - 512, self.context_size // 2)

    def generate_response(self, prompt: str, temperature: float = None, max_tokens: int = None) -> str:
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "temperature": temperature,
                "num_ctx": self.context_size,
                "max_tokens": max_tokens,
                "stream": False
            }
            logger.info(f"Sending request to Ollama API with payload: {payload}")
            response = requests.post(self.api_url, json=payload)
            logger.info(f"Ollama API response status: {response.status_code}")
            if response.status_code == 200:
                logger.info(f"Ollama API response body (truncated): {response.text[:500]}")
                return response.text
            else:
                logger.error(f"Non-200 response from Ollama API: {response.status_code} - {response.text}")
                return ""
        except Exception as e:
            logger.error(f"Error contacting Ollama API: {e}")
            return ""


def get_llm_processor():
    return LLMProcessor()