# backend/app/services/ocr_service.py
import os
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Explicitly typed Vitals model (replaces dynamic Dict)
class VitalsDetails(BaseModel):
    blood_pressure: Optional[str] = Field(default=None, description="BP reading, e.g. 120/80 mmHg")
    pulse: Optional[str] = Field(default=None, description="Pulse rate, e.g. 72 bpm")
    weight: Optional[str] = Field(default=None, description="Weight, e.g. 68 kg")
    temperature: Optional[str] = Field(default=None, description="Body temp, e.g. 98.6 F")

class PatientDetails(BaseModel):
    name: Optional[str] = Field(default=None, description="Patient full name")
    age: Optional[str] = Field(default=None, description="Patient age")
    gender: Optional[str] = Field(default=None, description="Gender (Male, Female, Other)")
    vitals: Optional[VitalsDetails] = Field(default=None, description="Recorded vital signs")

class ExtractedMedicine(BaseModel):
    name: str = Field(description="Brand or generic medicine name")
    form: Optional[str] = Field(default="Tablet", description="Tablet, Capsule, Syrup, Drops, Injection")
    dosage: Optional[str] = Field(default=None, description="Strength (e.g. 500mg, 40mg, 10ml)")
    frequency: str = Field(description="Frequency shorthand: 1-0-1, 1-0-0, 0-0-1, 1-1-1, TDS, BD, OD, SOS")
    timing: Optional[str] = Field(default="PC", description="AC (Before food) or PC (After food)")
    duration_days: Optional[int] = Field(default=5, description="Number of days to take")
    special_instructions: Optional[str] = Field(default=None, description="e.g. with warm water, at bedtime")

class PrescriptionExtractionResponse(BaseModel):
    doctor_name: Optional[str] = Field(default=None, description="Doctor's name with qualification")
    clinic_name: Optional[str] = Field(default=None, description="Hospital or clinic name")
    prescription_date: Optional[str] = Field(default=None, description="Date formatted as YYYY-MM-DD")
    patient: Optional[PatientDetails] = Field(default=None, description="Patient information")
    diagnosis: Optional[str] = Field(default=None, description="Provisional diagnosis or clinical symptoms")
    medicines: List[ExtractedMedicine] = Field(default=[], description="List of all prescribed medications")
    tests_advised: Optional[List[str]] = Field(default=[], description="Lab tests or scans recommended")
    general_advice: Optional[str] = Field(default=None, description="Dietary or lifestyle instructions")
    next_visit: Optional[str] = Field(default=None, description="Follow-up review timeline")
    raw_text_transcript: str = Field(description="Verbatim transcription of all legible text on page")

SYSTEM_INSTRUCTION = """
You are an expert clinical pharmacologist and medical transcriptionist deciphering doctor handwriting.
Examine this medical prescription slip and extract every detail:
1. Header: Doctor name, qualifications, clinic/hospital name, prescription date.
2. Patient details: Name, age, gender, and recorded vitals (BP, pulse, weight, temperature).
3. Clinical notes: Diagnosis, symptoms, chief complaints.
4. Medications: Every drug with name, form, dosage, frequency (1-0-1, TDS, BD, OD), timing (AC/PC), duration, and instructions.
5. Lab/Diagnostic tests recommended.
6. Dietary advice and follow-up review timeline.
7. Verbatim text transcript of the entire page.

Do NOT guess illegible words. Leave unreadable fields as null.
"""

def extract_prescription_data(image_bytes: bytes, mime_type: str = "image/jpeg") -> PrescriptionExtractionResponse:
    # Ensure Gemini receives a supported MIME type
    valid_mime = mime_type if mime_type in ["image/jpeg", "image/png", "image/webp"] else "image/jpeg"

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=[
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=valid_mime,
            ),
            "Extract all medical data from this prescription image into the strict JSON schema."
        ],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=PrescriptionExtractionResponse,
            temperature=0.1,
        ),
    )

    return PrescriptionExtractionResponse.model_validate_json(response.text)