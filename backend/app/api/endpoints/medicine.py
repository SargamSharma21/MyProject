from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
import os
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# Adjust these two imports to match your project's database and models
from app.database import SessionLocal # or your get_db dependency
from app.models import MedicineInfo   # or DrugCatalog / whatever your model name is

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class DrugSafetySchema(BaseModel):
    brand_name: str = Field(description="Brand or trade name")
    generic_name: str = Field(description="Active pharmacological salt")
    uses: str = Field(description="Primary clinical indications")
    side_effects: str = Field(description="Common adverse reactions")
    contraindications: str = Field(description="When not to take")
    food_interactions: str = Field(description="Food or alcohol interactions")

@router.get("/search")
def search_medicines(
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db)
):
    query_str = q.strip()
    print(f"\n--- [SEARCH START] Received query: '{query_str}' ---")

    # 1. Search local PostgreSQL
    try:
        cached_results = db.query(MedicineInfo).filter(
            (MedicineInfo.brand_name.ilike(f"%{query_str}%")) |
            (MedicineInfo.generic_name.ilike(f"%{query_str}%"))
        ).all()
    except Exception as db_err:
        print(f"[DB Query Error]: {db_err}")
        cached_results = []

    if cached_results:
        print(f"[DB HIT] Found {len(cached_results)} results in database.")
        return [
            {
                "brand_name": med.brand_name,
                "generic_name": med.generic_name,
                "uses": med.uses,
                "side_effects": med.side_effects,
                "contraindications": med.contraindications,
                "food_interactions": med.food_interactions,
            }
            for med in cached_results
        ]

    # 2. Database Miss -> Call Gemini
    print(f"[DB MISS] Not in database. Calling Gemini 2.5 Flash for '{query_str}'...")
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=f"Provide detailed clinical pharmacology data for '{query_str}' including brand, generic salt, uses, side effects, contraindications, and food interactions.",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=DrugSafetySchema,
                temperature=0.1,
            ),
        )
        print(f"[Gemini Raw Output]: {response.text}")
        fresh_drug = DrugSafetySchema.model_validate_json(response.text)

        # 3. Save to PostgreSQL for zero-latency future hits
        new_entry = MedicineInfo(
            brand_name=fresh_drug.brand_name,
            generic_name=fresh_drug.generic_name,
            uses=fresh_drug.uses,
            side_effects=fresh_drug.side_effects,
            contraindications=fresh_drug.contraindications,
            food_interactions=fresh_drug.food_interactions,
        )
        db.add(new_entry)
        db.commit()
        db.refresh(new_entry)
        print(f"[DB SAVED] Successfully cached '{fresh_drug.brand_name}' into PostgreSQL.")

        return [{
            "brand_name": fresh_drug.brand_name,
            "generic_name": fresh_drug.generic_name,
            "uses": fresh_drug.uses,
            "side_effects": fresh_drug.side_effects,
            "contraindications": fresh_drug.contraindications,
            "food_interactions": fresh_drug.food_interactions,
        }]

    except Exception as e:
        print(f"[Gemini Call Failed]: {e}")
        # Return fallback error item so the frontend displays the exact error instead of a blank card
        return [{
            "brand_name": query_str,
            "generic_name": "Lookup Error",
            "uses": f"Failed to fetch safety profile: {str(e)}",
            "side_effects": "Check backend terminal for traceback details.",
            "contraindications": "N/A",
            "food_interactions": "N/A",
        }]