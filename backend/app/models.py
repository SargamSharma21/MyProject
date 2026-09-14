# backend/app/models.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Boolean, Time, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    profiles = relationship("Profile", back_populates="user", cascade="all, delete-orphan")


class Profile(Base):
    __tablename__ = "profiles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    relationship_type = Column("relationship", String(50), default="Self")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="profiles")
    prescriptions = relationship("Prescription", back_populates="profile", cascade="all, delete-orphan")


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=True)
    doctor_name = Column(String(255), nullable=True)
    clinic_name = Column(String(255), nullable=True)
    prescription_date = Column(String(100), nullable=True)
    image_path = Column(String(500), nullable=False)
    medicines_payload = Column(JSONB, nullable=False, default=list)
    status = Column(String(20), default="PROCESSED")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    profile = relationship("Profile", back_populates="prescriptions")
    medicines = relationship("PrescriptionMedicine", back_populates="prescription", cascade="all, delete-orphan")
    storage_key = Column(String(500), nullable=True)
    file_name = Column(String(255), nullable=True)
    mime_type = Column(String(100), nullable=True)


class PrescriptionMedicine(Base):
    __tablename__ = "prescription_medicines"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prescription_id = Column(UUID(as_uuid=True), ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False)
    drug_name = Column(String(150), nullable=False)
    dosage = Column(String(50), nullable=True)
    form = Column(String(50), nullable=True)
    frequency_code = Column(String(20), nullable=True)
    timing = Column(String(20), nullable=True)
    duration_days = Column(Integer, default=5)
    is_confirmed = Column(Boolean, default=False)
    
    prescription = relationship("Prescription", back_populates="medicines")
    schedules = relationship("MedicineSchedule", back_populates="medicine", cascade="all, delete-orphan")


class MedicineSchedule(Base):
    __tablename__ = "medicine_schedules"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prescription_medicine_id = Column(UUID(as_uuid=True), ForeignKey("prescription_medicines.id", ondelete="CASCADE"), nullable=False)
    alarm_time = Column(Time, nullable=False)
    is_active = Column(Boolean, default=True)
    
    medicine = relationship("PrescriptionMedicine", back_populates="schedules")


class DrugCatalog(Base):
    __tablename__ = "drug_catalog"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_name = Column(String(150), index=True, nullable=False)
    generic_name = Column(String(150), index=True, nullable=False)
    uses = Column(Text, nullable=False)
    side_effects = Column(Text, nullable=False)
    contraindications = Column(Text, nullable=False)
    food_interactions = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())