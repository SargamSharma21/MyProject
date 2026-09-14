-- 1. Enable extensions for UUID generation and fuzzy text matching
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 2. Users & Multi-Profile Hierarchy (FR1)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    relationship VARCHAR(50) DEFAULT 'Self', -- Self, Father, Mother, Child
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Digital Prescription Vault (FR5 & Document Storage Pointer)
CREATE TABLE IF NOT EXISTS prescriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    storage_key VARCHAR(500) NOT NULL,       -- Path in AWS S3 or local storage
    file_name VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,         -- 'image/jpeg' or 'application/pdf'
    raw_ocr_payload JSONB,                   -- Flexible unstructured AI output
    status VARCHAR(20) DEFAULT 'PROCESSED',  -- 'PENDING', 'PROCESSED', 'FAILED'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for searching inside the JSON structure
CREATE INDEX IF NOT EXISTS idx_prescriptions_ocr_gin ON prescriptions USING gin (raw_ocr_payload);

-- 4. Verified Medicine Knowledge Catalog (FR3)
CREATE TABLE IF NOT EXISTS drug_catalog (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    brand_name VARCHAR(150) NOT NULL,
    generic_name VARCHAR(150) NOT NULL,
    uses TEXT NOT NULL,
    side_effects TEXT NOT NULL,
    contraindications TEXT NOT NULL,         -- When NOT to take
    food_interactions TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Trigram index for fast typo-tolerant autocomplete
CREATE INDEX IF NOT EXISTS idx_drug_catalog_trgm ON drug_catalog 
USING gin (brand_name gin_trgm_ops, generic_name gin_trgm_ops);

-- 5. Structured Extracted Medicines & Alarms (FR2.4 & FR4)
CREATE TABLE IF NOT EXISTS prescription_medicines (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prescription_id UUID REFERENCES prescriptions(id) ON DELETE CASCADE,
    drug_name VARCHAR(150) NOT NULL,
    dosage VARCHAR(50),                      -- e.g., 500mg, 10ml
    form VARCHAR(50),                        -- Tablet, Syrup, Capsule
    frequency_code VARCHAR(20),              -- 1-0-1, TDS, BD, OD
    timing VARCHAR(20),                      -- AC (Before Food), PC (After Food)
    duration_days INT DEFAULT 5,
    is_confirmed BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS medicine_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prescription_medicine_id UUID REFERENCES prescription_medicines(id) ON DELETE CASCADE,
    alarm_time TIME NOT NULL,                -- e.g., 09:00:00, 21:00:00
    is_active BOOLEAN DEFAULT TRUE
);

-- Seed verified baseline drug information
INSERT INTO drug_catalog (brand_name, generic_name, uses, side_effects, contraindications, food_interactions)
VALUES 
('Augmentin 625', 'Amoxicillin and Clavulanic Acid', 'Treats bacterial infections of lungs, ear, sinuses, skin, and urinary tract.', 'Diarrhea, nausea, skin rash, stomach cramps.', 'Do not take if you have severe kidney impairment or a penicillin allergy.', 'Take right before a meal to prevent gastrointestinal upset.'),
('Lipitor 20', 'Atorvastatin', 'Lowers LDL cholesterol and triglycerides; reduces stroke and heart attack risk.', 'Muscle soreness, joint pain, mild nausea, diarrhea.', 'Do not take if you have active liver disease or during pregnancy.', 'Avoid drinking large amounts of grapefruit juice while taking this medication.'),
('Pan 40', 'Pantoprazole', 'Reduces excess stomach acid, treats GERD, acid reflux, and peptic ulcers.', 'Headache, diarrhea, dizziness, flatulence.', 'Do not take if you have severe hypomagnesemia without clinical supervision.', 'Take 30 to 60 minutes before breakfast (AC).')
ON CONFLICT DO NOTHING;