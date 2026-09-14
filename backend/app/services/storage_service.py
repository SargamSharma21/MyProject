# backend/app/services/storage_service.py
import os
import uuid
import aiofiles

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
PRESCRIPTIONS_DIR = os.path.join(UPLOAD_DIR, "prescriptions")

# Ensure storage directory exists
os.makedirs(PRESCRIPTIONS_DIR, exist_ok=True)

async def save_file_to_vault(file_bytes: bytes, original_filename: str) -> str:
    """
    Saves original PDF or Image to server storage with a unique UUID prefix.
    Returns the relative storage key.
    """
    ext = original_filename.split(".")[-1] if "." in original_filename else "bin"
    unique_filename = f"{uuid.uuid4()}.{ext}"
    file_path = os.path.join(PRESCRIPTIONS_DIR, unique_filename)

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(file_bytes)

    # Return relative storage key (matches S3 object key convention)
    return f"prescriptions/{unique_filename}"

def get_absolute_file_path(storage_key: str) -> str:
    """Resolves a storage key to the physical file location on disk."""
    return os.path.join(UPLOAD_DIR, storage_key)