import json
import logging
from app.core.llm_processor import get_llm_processor
from app.core.prompts.feature_extraction import FEATURE_EXTRACTION_PROMPT
from app.core.schema_validation import ClinicalFeatures, ValidationError

logger = logging.getLogger(__name__)

def extract_features_with_llm(text):
    """
    Extract patient features using the LLM with the predefined prompt and validate via schema.
    """
    llm = get_llm_processor()
    prompt = FEATURE_EXTRACTION_PROMPT.format(text=text)
    response = llm.generate_response(prompt)

    logger.info(f"🧠 LLM Raw Response: {response}")

    try:
        parsed = json.loads(response)
        validated = ClinicalFeatures(**parsed)
        logger.info(f"✅ Validated Features: {validated.dict()}")
        return validated.dict()

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON decoding error: {str(e)}", exc_info=True)
    except ValidationError as e:
        logger.error(f"❌ Schema validation failed: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"❌ Unexpected error in LLM response parsing: {e}", exc_info=True)

    return {}

