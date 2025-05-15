from pydantic import BaseModel, Field, validator, ValidationError
from typing import Optional, List, Dict

class ClinicalFeatures(BaseModel):
    age: Optional[int] = Field(None, ge=0, le=120)
    gender: Optional[str] = Field(None, pattern=r"^(male|female|not mentioned)$")
    diagnosis: Optional[str] = Field(None, pattern=r"^(NSCLC|SCLC|other|not mentioned)$")
    stage: Optional[str] = Field(None, pattern=r"^(I|II|III|IV|not mentioned)$")
    ecog: Optional[str] = Field(None, pattern=r"^(0|1|2|3|4|not mentioned)$")
    mutations: List[str] = []
    metastases: List[str] = []
    previous_treatments: List[str] = []
    lab_values: Dict[str, str] = {}

    @validator("gender", "diagnosis", "stage", "ecog", pre=True, always=True)
    def null_or_valid(cls, v):
        if v is None or v == "null":
            return "not mentioned"
        return v

    @validator("mutations", "metastases", "previous_treatments", pre=True, always=True)
    def ensure_list(cls, v):
        return v if isinstance(v, list) else []

    @validator("lab_values", pre=True, always=True)
    def ensure_dict(cls, v):
        return v if isinstance(v, dict) else {}
