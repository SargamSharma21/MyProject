# backend/app/services/drug_safety_service.py
import os
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class DrugSafetySchema(BaseModel):
    brand_name: str = Field(description="Recognized brand name or standardized name")
    generic_name: str = Field(description="Active pharmacological salts / chemical composition")
    uses: str = Field(description="Primary therapeutic uses and indications")
    side_effects: str = Field(description="Common and notable adverse side effects")
    contraindications: str = Field(description="Scenarios, conditions, or patient types who should avoid this")
    food_interactions: str = Field(description="Interactions with food, alcohol, or timing guidelines")

DRUG_SAFETY_SYSTEM_PROMPT = """
You are an expert clinical pharmacologist. 
Your task is to provide accurate, concise, and structured drug safety data for any queried medicine or active salt.
Always identify the active generic salt composition, standard therapeutic indications, documented side effects, critical contraindications, and food/alcohol precautions.
Avoid conversational filler. Output strictly according to the provided JSON schema.
"""

def fetch_drug_from_gemini(query: str) -> DrugSafetySchema | None:
    try:
        prompt = f"Provide clinical drug safety details for the medicine or active salt: '{query}'"
        
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=DRUG_SAFETY_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=DrugSafetySchema,
                temperature=0.1,
            ),
        )
        
        if response.text:
            return DrugSafetySchema.model_validate_json(response.text)
        return None
    except Exception as e:
        print(f"[Drug Safety Service] Gemini lookup failed for query '{query}': {e}")
        return None