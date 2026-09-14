# backend/app/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# Change credentials to match your local PostgreSQL setup
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://sargam@localhost:5432/rx_vault_db"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# FastAPI Dependency: provides an isolated DB session per request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()