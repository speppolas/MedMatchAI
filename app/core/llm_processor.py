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

# Global variables for LLM availability
LLM_AVAILABLE = False
_llm_availability_checked = False
_llm_availability_lock = threading.Lock()

class LLMProcessor:
    
    def __init__(self):
        """Initialize the LLM Processor."""
        self.llama_cpp_path = LLAMA_CPP_PATH
        self.model_path = LLM_MODEL_PATH
        self.context_size = LLM_CONTEXT_SIZE
        self.temperature = LLM_TEMPERATURE
        self.max_tokens = LLM_MAX_TOKENS
        self.timeout = LLM_TIMEOUT
        self.extra_params = LLM_EXTRA_PARAMS
        
        # ✅ Forcing CUDA Settings for GPU-Only
        self._set_cuda_environment()
        
        # ✅ Debugging CUDA Variables
        logger.info("🔧 Forcing CUDA Settings for GPU-Only:")
        logger.info(f"🧪 GGML_CUDA: {os.environ.get('GGML_CUDA')}")
        logger.info(f"🧪 GGML_CUDA_FORCE_MMQ: {os.environ.get('GGML_CUDA_FORCE_MMQ')}")
        logger.info(f"🧪 GGML_CUDA_FORCE_CUBLAS: {os.environ.get('GGML_CUDA_FORCE_CUBLAS')}")
        logger.info(f"🧪 GGML_CUDA_MAX_BATCH_SIZE: {os.environ.get('GGML_CUDA_MAX_BATCH_SIZE')}")

    def _set_cuda_environment(self):
        """Set CUDA variables correctly for GPU-Only."""
        os.environ['GGML_CUDA'] = 'yes'
        os.environ['GGML_CUDA_FORCE_MMQ'] = 'yes'
        os.environ['GGML_CUDA_FORCE_CUBLAS'] = 'yes'
        os.environ['GGML_CUDA_MAX_BATCH_SIZE'] = '1024'  # Adjust based on GPU memory
        os.environ['CUDA_HOME'] = '/usr/local/cuda-12.8'
        os.environ['PATH'] = f"{os.environ['CUDA_HOME']}/bin:{os.environ.get('PATH', '')}"
        os.environ['LD_LIBRARY_PATH'] = f"{os.environ['CUDA_HOME']}/lib64:{os.environ.get('LD_LIBRARY_PATH', '')}"
    
    def generate_response(self, prompt: str, 
                     temperature: Optional[float] = None,
                     max_tokens: Optional[int] = None) -> str:
    
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        # Ensure the prompt is properly formatted (escaped)
        import json
        sanitized_prompt = json.dumps(prompt)

        # Optimized Command for GPU-Only llama.cpp
        cmd = [
            self.llama_cpp_path,
            "--model", self.model_path,
            "--prompt", sanitized_prompt,
            "--predict", str(tokens),
            "--ctx-size", str(self.context_size),
            "--temp", str(temp),
            "--no-warmup",
            "--interactive",
            "--gpu-layers", "-1",     # Use all layers on GPU
            "--threads", "32",           # CPU minimized
            "--batch-size", "1024"       # Large batch size for GPU speed
        ]

        if self.extra_params:
            cmd.extend(self.extra_params.split())
        
        # ✅ Forcing CUDA variables directly in the subprocess
        env = {
            "GGML_CUDA": "yes",
            "GGML_CUDA_FORCE_MMQ": "yes",
            "GGML_CUDA_FORCE_CUBLAS": "yes",
            "GGML_CUDA_MAX_BATCH_SIZE": "1024",
            "CUDA_HOME": "/usr/local/cuda-12.8",
            "PATH": f"/usr/local/cuda-12.8/bin:{os.getenv('PATH')}",
            "LD_LIBRARY_PATH": f"/usr/local/cuda-12.8/lib64:{os.getenv('LD_LIBRARY_PATH')}"
        }
        
        logger.info(f"🚀 Executing LLM Command with GPU-Only: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=self.timeout)
            
            if result.returncode != 0:
                logger.error(f"❌ LLM Execution Error (code {result.returncode})")
                logger.error(f"Stderr: {result.stderr}")
                return f"[LLM Error: {result.stderr.strip()}]"
            
            return result.stdout.strip()
        
        except subprocess.TimeoutExpired:
            logger.error(f"❌ Timeout during LLM execution ({self.timeout}s)")
            return "[Timeout LLM]"
        
        except Exception as e:
            logger.error(f"❌ Error during LLM usage: {str(e)}")
            return "[LLM Error]"


def get_llm_processor() -> LLMProcessor:
    """
    Returns an instance of the LLM Processor.
    """
    return LLMProcessor()
