
from app.core.llm_processor import LLMProcessor

def test_feature_extraction():
    llm = LLMProcessor()
    test_text = """
    Paziente donna di 65 anni con diagnosi di carcinoma mammario HER2+, 
    stadio IV con metastasi ossee. ECOG PS 1.
    Precedente trattamento con trastuzumab.
    """
    features = llm.process_feature_extraction(test_text)
    print("Extracted Features:", features)

if __name__ == "__main__":
    test_feature_extraction()
