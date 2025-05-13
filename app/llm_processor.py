import os
import logging
import subprocess
import threading
from typing import Optional

from config import (
    LLAMA_CPP_PATH, LLM_MODEL_PATH, LLM_CONTEXT_SIZE,
    LLM_TEMPERATURE, LLM_MAX_TOKENS, LLM_TIMEOUT,
    LLM_EXTRA_PARAMS
)

logger = logging.getLogger(__name__)

class LLMProcessor:
    
    def __init__(self):
        self.llama_cpp_path = LLAMA_CPP_PATH
        self.model_path = LLM_MODEL_PATH
        self.context_size = LLM_CONTEXT_SIZE
        self.temperature = LLM_TEMPERATURE
        self.max_tokens = LLM_MAX_TOKENS
        self.timeout = LLM_TIMEOUT
        self.extra_params = LLM_EXTRA_PARAMS
        
        self._set_cuda_environment()
        self._debug_cuda_configuration()

        if not os.path.exists(self.model_path):
            logger.error(f"❌ LLM Model not found at path: {self.model_path}")
            raise FileNotFoundError(f"LLM Model not found at path: {self.model_path}")

    def _set_cuda_environment(self):
        os.environ['GGML_CUDA'] = 'yes'
        os.environ['GGML_CUDA_FORCE_MMQ'] = 'yes'
        os.environ['GGML_CUDA_FORCE_CUBLAS'] = 'yes'
        os.environ['CUDA_HOME'] = '/usr/local/cuda-12.8'
        os.environ['LD_LIBRARY_PATH'] = f"{os.environ['CUDA_HOME']}/lib64"

    def _debug_cuda_configuration(self):
        logger.info("🔧 Verifying CUDA Configuration (llm_processor.py):")
        for var in ["GGML_CUDA", "GGML_CUDA_FORCE_MMQ", "GGML_CUDA_FORCE_CUBLAS", "CUDA_HOME", "LD_LIBRARY_PATH"]:
            logger.info(f"🧪 {var}: {os.environ.get(var)}")

    def generate_response(self, prompt: str, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> str:
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        cmd = [
            self.llama_cpp_path, "--model", self.model_path,
            "--prompt", prompt, "--predict", str(tokens),
            "--ctx-size", str(self.context_size), "--temp", str(temp),
            "--no-warmup"
        ]

        if self.extra_params:
            cmd.extend(self.extra_params.split())

        logger.info(f"🚀 Running llama.cpp with command: {' '.join(cmd)}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)

            if result.stderr:
                logger.error(f"❌ LLM Error: {result.stderr.strip()}")

            if result.returncode != 0:
                logger.error(f"❌ LLM process exited with code {result.returncode}")
                return None

            output = result.stdout.strip()
            logger.info(f"✅ LLM Output (Raw): {output}")

            # ✅ Ensure JSON is clean
            output = re.sub(r'(?<=: )(\d+)(?=[,}\]])', r'"\1"', output)

            return output

        except subprocess.TimeoutExpired:
            logger.error(f"❌ Timeout during LLM execution ({self.timeout}s)")
            return None

        except Exception as e:
            logger.error(f"❌ Error running llama.cpp: {str(e)}")
            return None


def get_llm_processor() -> LLMProcessor:
    return LLMProcessor()
