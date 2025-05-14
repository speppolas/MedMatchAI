
"""
Trial matching prompts for LLM interactions with XAI capabilities.
These prompts are designed to provide explainable trial matching results.
"""

TRIAL_MATCHING_PROMPT = '''
# TASK
Analyze if the patient matches the clinical trial criteria and provide detailed explanations.

# INPUT
Patient Features: {patient_features}
Clinical Trial: {trial}

# EVALUATION CRITERIA
1. Inclusion Criteria
2. Exclusion Criteria
3. Age Requirements
4. Cancer Type and Stage
5. Performance Status
6. Previous Treatments
7. Biomarkers/Mutations

# OUTPUT FORMAT
{
    "match_score": 0-100,
    "overall_recommendation": "RECOMMENDED|NOT_RECOMMENDED|POTENTIALLY_ELIGIBLE",
    "criteria_analysis": {
        "inclusion_criteria": [
            {
                "criterion": "string",
                "met": true|false,
                "explanation": "string",
                "confidence": 0-100
            }
        ],
        "exclusion_criteria": [
            {
                "criterion": "string",
                "violated": true|false,
                "explanation": "string",
                "confidence": 0-100
            }
        ]
    },
    "key_factors": {
        "supporting": ["list of main factors supporting eligibility"],
        "opposing": ["list of main factors opposing eligibility"]
    },
    "uncertainty_areas": ["list of criteria that need clarification"],
    "next_steps": ["recommended actions for clarification"]
}
'''

TRIAL_SUMMARY_PROMPT = '''
# TASK
Create a concise, patient-friendly summary of why this trial matches or doesn't match.

# INPUT
Match Analysis: {match_analysis}

# REQUIRED POINTS
1. Overall recommendation
2. Key matching points
3. Key mismatches
4. Important considerations
5. Next steps

# FORMAT
{
    "summary": "2-3 sentence summary",
    "key_points": ["bullet points of most important factors"],
    "patient_guidance": "what the patient should discuss with their doctor"
}
'''
