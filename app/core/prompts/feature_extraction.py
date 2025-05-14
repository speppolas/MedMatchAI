
"""
Feature extraction prompts for LLM interactions.
These prompts are designed to extract clinical features from patient documents.
"""

FEATURE_EXTRACTION_PROMPT = '''
# TASK
You are a medical assistant specialized in analyzing oncological clinical documents.
Extract the following medical features from the patient text and return ONLY a valid JSON object.

# FIELDS TO EXTRACT
- age: patient age as number (or null if not found)
- gender: "male", "female", or null if not found
- diagnosis: primary cancer diagnosis (or null if not found)
- stage: cancer stage (or null if not found)
- ecog: ECOG performance status as number (or null if not found)
- mutations: list of genetic mutations (empty list if none found)
- metastases: list of metastasis locations (empty list if none found)
- previous_treatments: list of previous treatments (empty list if none found)
- lab_values: object with lab values as key-value pairs (empty object if none found)

# IMPORTANT INSTRUCTIONS
1. For each extracted value, include a "source" field with the exact text fragment.
2. Return ONLY the JSON without additional text.
3. Use null for missing single fields or empty lists/objects for collections.
4. Be precise in extraction and use medical context for accurate identification.

# PATIENT TEXT
{text}

# OUTPUT JSON FORMAT
{
    "age": { "value": 65, "source": "65-year-old" },
    "gender": { "value": "female", "source": "female patient" },
    "diagnosis": { "value": "non-small cell lung cancer", "source": "diagnosed with non-small cell lung cancer" },
    "stage": { "value": "IV", "source": "stage IV" },
    "ecog": { "value": 1, "source": "ECOG PS 1" },
    "mutations": [
        { "value": "EGFR T790M", "source": "positive for EGFR T790M mutation" }
    ],
    "metastases": [
        { "value": "brain", "source": "brain metastases" }
    ],
    "previous_treatments": [
        { "value": "carboplatin", "source": "received carboplatin" }
    ],
    "lab_values": {
        "hemoglobin": { "value": "11.2 g/dL", "source": "Hemoglobin: 11.2 g/dL" }
    }
}
'''
