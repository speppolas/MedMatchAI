
import os
import logging
import subprocess
import threading
import requests
from typing import Optional

logger = logging.getLogger(__name__)

class LLMProcessor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.llama_cpp_path = "./llama.cpp/build/bin/server"
        self.model_path = "./models/llama-2-7b-chat.Q4_K_M.gguf"
        self.api_url = "http://localhost:8080/v1/completions"
        self._ensure_llama_cpp_server()

    def _ensure_llama_cpp_server(self):
        """Ensure llama.cpp server is available."""
        if not os.path.exists(self.llama_cpp_path):
            raise RuntimeError("llama.cpp server binary not found. Please build llama.cpp first.")
        if not os.path.exists(self.model_path):
            raise RuntimeError("Model file not found. Please download a GGUF model first.")

    def _set_cuda_environment(self):
        """Set CUDA variables for GPU acceleration."""
        os.environ['GGML_CUDA'] = 'yes'
        os.environ['GGML_CUDA_FORCE_MMQ'] = 'yes'
        os.environ['GGML_CUDA_FORCE_CUBLAS'] = 'yes'
        os.environ['GGML_CUDA_MAX_BATCH_SIZE'] = '1024'

    def generate_response(self, prompt: str, 
                      temperature: float = 0.7,
                      max_tokens: int = 2048) -> str:
        """Generate response using llama.cpp server."""
        try:
            payload = {
                "prompt": prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False
            }

            response = requests.post(self.api_url, json=payload)
            if response.status_code == 200:
                return response.json()['choices'][0]['text']
            else:
                self.logger.error(f"llama.cpp server error: {response.status_code}")
                return "Error generating response"

        except Exception as e:
            self.logger.error(f"Error calling llama.cpp server: {str(e)}")
            return "Error connecting to llama.cpp server"

def get_llm_processor():
    """Returns an instance of the LLM Processor."""
    return LLMProcessor()
