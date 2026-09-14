# backend/app/services/image_processor.py
import cv2
import numpy as np
import pypdfium2 as pdfium
import io
from PIL import Image

def convert_pdf_to_image_bytes(pdf_bytes: bytes) -> bytes:
    """Extracts the first page of a PDF and renders it as high-res JPG bytes."""
    try:
        pdf = pdfium.PdfDocument(pdf_bytes)
        if len(pdf) == 0:
            raise ValueError("The provided PDF file is empty.")
        
        first_page = pdf[0]
        # Render at 2x scale (144 dpi) for crisp text extraction
        bitmap = first_page.render(scale=2)
        
        # Method A: Direct PIL conversion with explicit Image module loaded
        pil_image = bitmap.to_pil()
        
        buffer = io.BytesIO()
        pil_image.save(buffer, format="JPEG", quality=95)
        return buffer.getvalue()
        
    except Exception as e:
        # Method B Fallback: Render via raw buffer if PIL loader acts up
        try:
            pdf = pdfium.PdfDocument(pdf_bytes)
            page = pdf[0]
            bitmap = page.render(scale=2)
            # Convert raw bitmap buffer directly to NumPy array for OpenCV
            img_np = bitmap.to_numpy()
            # Bitmap is typically BGRA or BGR; convert if alpha channel exists
            if img_np.shape[2] == 4:
                img_np = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
            success, enc = cv2.imencode(".jpg", img_np)
            if success:
                return enc.tobytes()
        except Exception:
            pass
        raise RuntimeError(f"Failed to render PDF: {str(e)}")

def preprocess_prescription_image(image_bytes: bytes) -> bytes:
    """
    Cleans up scanned documents:
    1. Converts to grayscale.
    2. Uses Bilateral Filtering to remove paper noise while keeping text edges crisp.
    3. Runs Adaptive Thresholding to eliminate shadows and background tint.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        raise ValueError("Could not decode image bytes.")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    filtered = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
    thresh = cv2.adaptiveThreshold(
        filtered, 
        255, 
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 
        blockSize=15, 
        C=8
    )

    success, buffer = cv2.imencode('.jpg', thresh)
    if not success:
        raise ValueError("Failed to encode processed image.")

    return buffer.tobytes()