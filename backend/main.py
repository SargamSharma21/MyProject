# backend/main.py
import os
import json
import uuid
from pathlib import Path
from pydantic import BaseModel, Field
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import or_, text
from google import genai
from google.genai import types

from app.database import get_db, engine
from app import models
from app.models import Prescription, Profile, User, PrescriptionMedicine, DrugCatalog
from app.services.image_processor import preprocess_prescription_image, convert_pdf_to_image_bytes
from app.services.ocr_service import extract_prescription_data, PrescriptionExtractionResponse
from app.services.storage_service import save_file_to_vault, get_absolute_file_path

# 1. Automatically ensure PostgreSQL tables exist
models.Base.metadata.create_all(bind=engine)

# 2. Setup upload directories
UPLOAD_DIR = Path("uploads/prescriptions")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="RxVault Core Engine",
    description="Medical Prescription Extraction, Vault & Safety API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount /static so images are streamable by the mobile frontend
app.mount("/static", StaticFiles(directory="uploads"), name="static")


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT 1")).scalar()
    return {"status": "healthy", "database_connected": bool(result)}


def get_or_create_default_profile(db: Session) -> str:
    profile = db.query(Profile).first()
    if profile:
        return str(profile.id)
    
    test_user = User(email="test@rxvault.com", hashed_password="hashed_pw_placeholder")
    db.add(test_user)
    db.commit()
    db.refresh(test_user)

    test_profile = Profile(user_id=test_user.id, name="Primary User", relationship_type="Self")
    db.add(test_profile)
    db.commit()
    db.refresh(test_profile)
    return str(test_profile.id)


# --- 1. OCR SCAN & VAULT ARCHIVE ---
@app.post("/api/v1/prescriptions/upload-and-scan")
async def upload_and_scan_prescription(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/heic", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, WEBP, or PDF files are accepted.")

    raw_file_bytes = await file.read()

    # Save to storage service
    storage_key = await save_file_to_vault(raw_file_bytes, file.filename)

    # Save a direct copy to uploads/prescriptions for static serving
    file_ext = Path(file.filename or "image.jpg").suffix or ".jpg"
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    saved_file_path = UPLOAD_DIR / unique_filename
    with open(saved_file_path, "wb") as f:
        f.write(raw_file_bytes)

    # Convert PDF if needed
    if file.content_type == "application/pdf":
        try:
            image_bytes = convert_pdf_to_image_bytes(raw_file_bytes)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to render PDF: {str(e)}")
    else:
        image_bytes = raw_file_bytes

    # Image enhancement
    try:
        cleaned_image = preprocess_prescription_image(image_bytes)
    except Exception:
        cleaned_image = image_bytes

    # Gemini OCR Extraction
    try:
        extraction: PrescriptionExtractionResponse = extract_prescription_data(cleaned_image)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Extraction failed: {str(e)}")

    profile_id = get_or_create_default_profile(db)
    
    # Save structured record to PostgreSQL
    db_prescription = Prescription(
        profile_id=profile_id,
        storage_key=storage_key,
        file_name=file.filename or unique_filename,
        mime_type=file.content_type or "image/jpeg",
        doctor_name=getattr(extraction, "doctor_name", None),
        clinic_name=getattr(extraction, "clinic_name", None),
        prescription_date=getattr(extraction, "prescription_date", None),
        image_path=f"/static/prescriptions/{unique_filename}",
        medicines_payload=json.loads(extraction.model_dump_json()).get("medicines", []),
        status="PROCESSED"
    )
    db.add(db_prescription)
    db.commit()
    db.refresh(db_prescription)

    # Populate prescription medicines table
    for med in extraction.medicines:
        db_med = PrescriptionMedicine(
            prescription_id=db_prescription.id,
            drug_name=med.name,
            dosage=med.dosage,
            form=med.form,
            frequency_code=med.frequency,
            timing=med.timing,
            duration_days=med.duration_days or 5,
            is_confirmed=False
        )
        db.add(db_med)
    db.commit()

    return {
        "status": "success",
        "prescription_id": str(db_prescription.id),
        "image_url": db_prescription.image_path,
        "extracted_data": extraction
    }


# --- 2. PRESCRIPTION VAULT HISTORY ---
@app.get("/api/v1/prescriptions/history")
def get_prescription_history(db: Session = Depends(get_db)):
    records = db.query(Prescription).order_by(Prescription.created_at.desc()).all()
    return [
        {
            "id": str(r.id),
            "doctor_name": r.doctor_name or "Unknown Doctor",
            "clinic_name": r.clinic_name or "Medical Clinic",
            "prescription_date": r.prescription_date or "N/A",
            "image_url": r.image_path,
            "medicines": r.medicines_payload or [],
            "created_at": r.created_at.strftime("%b %d, %Y") if r.created_at else ""
        }
        for r in records
    ]


@app.get("/api/v1/prescriptions/{prescription_id}/file")
def get_prescription_document(prescription_id: str, db: Session = Depends(get_db)):
    rx = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not rx:
        raise HTTPException(status_code=404, detail="Prescription record not found")

    file_path = get_absolute_file_path(rx.image_path.replace("/static/prescriptions/", ""))
    if not os.path.exists(file_path):
        # Fallback to direct uploads folder
        file_path = Path("uploads") / rx.image_path.lstrip("/static/")
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Document file missing from disk")

    return FileResponse(path=str(file_path))


# --- 3. DRUG SAFETY SEARCH WITH GEMINI HYBRID CACHE ---
class DrugSafetySchema(BaseModel):
    brand_name: str = Field(description="Brand or trade name")
    generic_name: str = Field(description="Active pharmacological salt")
    uses: str = Field(description="Primary clinical indications")
    side_effects: str = Field(description="Common adverse reactions")
    contraindications: str = Field(description="When not to take")
    food_interactions: str = Field(description="Food or alcohol interactions")


@app.get("/api/v1/medicines/search")
def search_medicines(
    q: str = "",
    db: Session = Depends(get_db)
):
    query_str = q.strip()
    if len(query_str) < 2:
        raise HTTPException(status_code=400, detail="Search query must be at least 2 characters.")

    # A. Search local DB cache first
    try:
        results = db.query(DrugCatalog).filter(
            or_(
                DrugCatalog.brand_name.ilike(f"%{query_str}%"),
                DrugCatalog.generic_name.ilike(f"%{query_str}%")
            )
        ).limit(10).all()

        if results:
            return [
                {
                    "id": str(med.id),
                    "brand_name": med.brand_name,
                    "generic_name": med.generic_name,
                    "uses": med.uses,
                    "side_effects": med.side_effects,
                    "contraindications": med.contraindications,
                    "food_interactions": med.food_interactions,
                }
                for med in results
            ]
    except Exception:
        db.rollback()

    # B. Cache miss -> Query Gemini
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=f"Provide detailed clinical drug information for '{query_str}': brand name, generic salt, uses, side effects, contraindications, and food/alcohol precautions.",
            config=types.GenerateContentConfig(
                system_instruction="You are a clinical pharmacologist. Provide accurate, concise drug information according to the strict JSON schema. Do not add markdown or conversational filler.",
                response_mime_type="application/json",
                response_schema=DrugSafetySchema,
                temperature=0.1,
            ),
        )
        
        fresh_drug = DrugSafetySchema.model_validate_json(response.text)

        # C. Cache record into PostgreSQL
        new_entry = DrugCatalog(
            brand_name=fresh_drug.brand_name,
            generic_name=fresh_drug.generic_name,
            uses=fresh_drug.uses,
            side_effects=fresh_drug.side_effects,
            contraindications=fresh_drug.contraindications,
            food_interactions=fresh_drug.food_interactions
        )
        db.add(new_entry)
        db.commit()
        db.refresh(new_entry)

        return [{
            "id": str(new_entry.id),
            "brand_name": new_entry.brand_name,
            "generic_name": new_entry.generic_name,
            "uses": new_entry.uses,
            "side_effects": new_entry.side_effects,
            "contraindications": new_entry.contraindications,
            "food_interactions": new_entry.food_interactions,
        }]

    except Exception as e:
        db.rollback()
        if 'fresh_drug' in locals() and fresh_drug:
            return [{
                "id": "temp-gemini",
                "brand_name": fresh_drug.brand_name,
                "generic_name": fresh_drug.generic_name,
                "uses": fresh_drug.uses,
                "side_effects": fresh_drug.side_effects,
                "contraindications": fresh_drug.contraindications,
                "food_interactions": fresh_drug.food_interactions,
            }]
        return [{
            "id": "err",
            "brand_name": query_str,
            "generic_name": "Lookup Failed",
            "uses": f"Unable to fetch data: {str(e)}",
            "side_effects": "Check backend terminal logs.",
            "contraindications": "N/A",
            "food_interactions": "N/A"
        }]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)