
import logging
import requests
import json

class LLMProcessor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_url = "http://localhost:8080/v1/completions"
        
    def generate_response(self, prompt: str) -> str:
        """
        Generate a response using the llama.cpp server.
        """
        try:
            payload = {
                "prompt": prompt,
                "temperature": 0.7,
                "top_p": 0.95,
                "stream": False,
                "max_tokens": 512
            }
            
            response = requests.post(self.api_url, json=payload)
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['text']
            else:
                self.logger.error(f"LLM Server error: {response.status_code}")
                return "Error generating response"
                
        except Exception as e:
            self.logger.error(f"Error calling LLM server: {str(e)}")
            return "Error connecting to LLM server"
