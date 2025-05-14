
from app.core.llm_processor import LLMProcessor

def test_llm():
    llm = LLMProcessor()
    response = llm.generate_response("Sei un assistente medico. Rispondi: come stai?")
    print("LLM Response:", response)

if __name__ == "__main__":
    test_llm()
