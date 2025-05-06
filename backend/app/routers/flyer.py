from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends
from sqlalchemy.orm import Session
from pydantic import ValidationError
from typing import List

from ..services.gemini_service import extract_flyer_data_from_image
from ..models.flyer import FlyerItemList, FlyerItem
from ..db import crud
from ..db.database import get_db
import shutil
import os
import uuid

router = APIRouter(
    prefix="/flyer",
    tags=["flyer"]
)

# Define a temporary directory for uploads
UPLOAD_DIR = "temp_uploads"

@router.on_event("startup")
def startup_event():
    # Create the temporary upload directory if it doesn't exist
    os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/extract/", response_model=dict, responses={400: {"description": "Error processing flyer"}, 500: {"description": "Internal server error"}})
async def extract_flyer_endpoint(
    store_name: str = Form("Walmart"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Receives a flyer image, extracts item data using Gemini,
    validates the data, saves it to the database, and returns a status message.
    """
    # Generate a unique filename to avoid collisions
    file_extension = os.path.splitext(file.filename)[1]
    temp_filename = f"{uuid.uuid4()}{file_extension}"
    temp_file_path = os.path.join(UPLOAD_DIR, temp_filename)

    try:
        # Save the uploaded file temporarily
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Call the Gemini service
        extracted_data = extract_flyer_data_from_image(temp_file_path, store_name)

        # Check if the service returned an error
        if "error" in extracted_data:
            raise HTTPException(status_code=400, detail=f"Failed to extract flyer data: {extracted_data['error']}")

        # Validate the extracted data using Pydantic model
        try:
            validated_data = FlyerItemList(**extracted_data)
            if not validated_data.items:
                raise HTTPException(status_code=400, detail="No items extracted from the flyer.")
        except ValidationError as e:
            print(f"[!] Pydantic validation error: {e}")
            raise HTTPException(status_code=400, detail=f"Extracted data validation failed: {e}")

        # Save validated items to the database
        try:
            created_db_items = crud.create_flyer_items(db=db, items=validated_data.items)
            return {"message": f"Successfully extracted and saved {len(created_db_items)} items."}
        except Exception as db_exc:
            print(f"[!] Database error: {db_exc}")
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error occurred: {db_exc}")

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"[!] Unexpected error in /extract endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
    finally:
        # Ensure the temporary file is deleted
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as remove_err:
                print(f"[!] Error removing temp file {temp_file_path}: {remove_err}")
        if file and not file.file.closed:
            await file.close()


@router.get("/items/{store_name}", response_model=List[FlyerItem], responses={404: {"description": "No items found for this store"}})
def read_flyer_items(store_name: str, db: Session = Depends(get_db)):
    """
    Retrieves flyer items for a specific store from the database.
    """
    print(f"[*] Received request to get items for store: {store_name}")
    # Use the existing CRUD function to get items
    db_items = crud.get_flyer_items_by_store(db=db, store_name=store_name)
    if not db_items:
        print(f"[!] No items found for store: {store_name}")
        # Returning an empty list is fine as the frontend handles it
    else:
        print(f"[*] Found {len(db_items)} items for store: {store_name}")
    # FastAPI automatically converts SQLAlchemy models to Pydantic response_model if fields match
    return db_items