# backend/seed_drugs.py
from app.database import SessionLocal
from app.models import DrugCatalog

drugs = [
    {
        "brand_name": "Augmentin 625 Duo",
        "generic_name": "Amoxicillin and Clavulanic Acid",
        "uses": "Bacterial infections of the respiratory tract, ear, sinus, skin, and urinary tract.",
        "side_effects": "Diarrhea, nausea, vomiting, abdominal discomfort, mild skin rash.",
        "contraindications": "Do not take if you have severe kidney impairment, cholestatic jaundice, or penicillin allergy.",
        "food_interactions": "Take immediately before a meal to minimize gastrointestinal discomfort."
    },
    {
        "brand_name": "Pan 40",
        "generic_name": "Pantoprazole 40mg",
        "uses": "Gastric acid reduction, GERD, acid reflux, and healing of peptic ulcers.",
        "side_effects": "Headache, diarrhea, dizziness, flatulence, abdominal pain.",
        "contraindications": "Do not take if allergic to substituted benzimidazoles; use cautiously in osteoporosis.",
        "food_interactions": "Best taken 30 to 60 minutes before breakfast on an empty stomach."
    },
    {
        "brand_name": "Dolo 650",
        "generic_name": "Paracetamol / Acetaminophen",
        "uses": "Fever reduction and relief of mild-to-moderate body aches, dental pain, or headaches.",
        "side_effects": "Very safe when taken at prescribed doses. Overdose can cause severe liver failure.",
        "contraindications": "Do not take if you have chronic active liver disease or acute alcohol toxicity.",
        "food_interactions": "Avoid consuming alcohol while taking this medicine to protect your liver."
    },
    {
        "brand_name": "Azithral 500",
        "generic_name": "Azithromycin 500mg",
        "uses": "Broad-spectrum macrolide antibiotic for throat infections, pneumonia, and bronchitis.",
        "side_effects": "Nausea, vomiting, diarrhea, temporary changes in taste.",
        "contraindications": "Do not take if you have a history of cholestatic jaundice or QT interval prolongation.",
        "food_interactions": "Can be taken with or without food, but food reduces stomach irritation."
    },
    {
        "brand_name": "Montair LC",
        "generic_name": "Montelukast + Levocetirizine",
        "uses": "Allergic rhinitis, sneezing, runny nose, and maintenance therapy for asthma.",
        "side_effects": "Drowsiness, fatigue, dry mouth, headache.",
        "contraindications": "Do not take if you have severe end-stage renal impairment (eGFR < 10 ml/min).",
        "food_interactions": "Avoid alcohol as it multiplies drowsiness effects. Best taken in the evening."
    },
    {
        "brand_name": "Metformin 500",
        "generic_name": "Metformin Hydrochloride",
        "uses": "Type 2 diabetes management to improve insulin sensitivity and lower blood glucose.",
        "side_effects": "Metallic taste, nausea, loose stools, lactic acidosis (rare).",
        "contraindications": "Do not take with severe kidney disease (eGFR < 30) or metabolic acidosis.",
        "food_interactions": "Take with or after main meals to avoid stomach cramps."
    }
]

def seed():
    db = SessionLocal()
    for d in drugs:
        exists = db.query(DrugCatalog).filter(DrugCatalog.brand_name == d["brand_name"]).first()
        if not exists:
            db.add(DrugCatalog(**d))
    db.commit()
    db.close()
    print("Database seeded with clinical drugs successfully!")

if __name__ == "__main__":
    seed()