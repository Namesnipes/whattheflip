from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, ValidationError
from typing import List, Optional
import logging

from ..services import gemini_service, flyer_acquisition_service
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

logger = logging.getLogger(__name__)

# Define a temporary directory for uploads
UPLOAD_DIR = "temp_uploads"
STITCHED_FLYERS_SUBDIR = "stitched_flyers"

@router.on_event("startup")
def startup_event():
    # Create the temporary upload directory if it doesn't exist
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    # Create the subdirectory for stitched flyers
    stitched_flyer_path = os.path.join(UPLOAD_DIR, STITCHED_FLYERS_SUBDIR)
    os.makedirs(stitched_flyer_path, exist_ok=True)
    logger.info(f"Upload directory '{UPLOAD_DIR}' and '{stitched_flyer_path}' ensured.")

# --- Pydantic Models for Fetch & Store Endpoint ---
class FetchFlyerRequest(BaseModel):
    merchant_name: str
    postal_code: str
    category: str = "Groceries" # Default category, can be overridden by request

class FetchedFlyerInfoResponse(BaseModel):
    flipp_flyer_id: int
    merchant_name: str
    image_path: str # Absolute path to the backend-accessible image file
    postal_code: str
    message: str

# --- New Endpoint to Fetch, Stitch, and Store Flyer ---
@router.post("/fetch-and-store/", response_model=FetchedFlyerInfoResponse)
async def fetch_and_store_flyer(
    request_data: FetchFlyerRequest,
    db: Session = Depends(get_db)
):
    logger.info(f"Received request to fetch/store flyer for merchant: {request_data.merchant_name}, postal: {request_data.postal_code}")

    # 1. Check cache by merchant and postal code (for recent flyers)
    cached_flyer = crud.get_cached_flyer_image_by_merchant_and_postal(
        db, request_data.merchant_name, request_data.postal_code
    )
    if cached_flyer:
        logger.info(f"Valid cached flyer found: ID {cached_flyer.flipp_flyer_id}, Path: {cached_flyer.image_path}")
        return FetchedFlyerInfoResponse(
            flipp_flyer_id=cached_flyer.flipp_flyer_id,
            merchant_name=cached_flyer.merchant_name,
            image_path=cached_flyer.image_path,
            postal_code=cached_flyer.postal_code,
            message="Using valid cached flyer image."
        )

    logger.info(f"No valid cached flyer for {request_data.merchant_name} at {request_data.postal_code}. Fetching from source.")
    # 2. If not in cache or outdated, fetch from service
    new_flipp_flyer_id_str, image_bytes = await flyer_acquisition_service.get_flyer_image_data_and_id(
        postal_code=request_data.postal_code,
        merchant_name=request_data.merchant_name,
        category=request_data.category
    )

    if not new_flipp_flyer_id_str or not image_bytes:
        logger.error(f"Failed to fetch flyer data for {request_data.merchant_name} at {request_data.postal_code} from acquisition service.")
        raise HTTPException(status_code=404, detail=f"Flyer for '{request_data.merchant_name}' not found or could not be processed at postal code '{request_data.postal_code}'.")
    
    new_flipp_flyer_id = int(new_flipp_flyer_id_str)

    # 3. Check if this flipp_flyer_id already exists (could be outdated or from different postal code search)
    # If so, remove old file and DB record before saving new one.
    existing_record_for_id = crud.get_cached_flyer_image_by_flipp_id(db, new_flipp_flyer_id)
    if existing_record_for_id:
        logger.info(f"Found existing record for flipp_flyer_id {new_flipp_flyer_id} (path: {existing_record_for_id.image_path}). Replacing it.")
        if os.path.exists(existing_record_for_id.image_path):
            try:
                os.remove(existing_record_for_id.image_path)
                logger.info(f"Deleted old image file: {existing_record_for_id.image_path}")
            except OSError as e:
                logger.warning(f"Could not delete old image file {existing_record_for_id.image_path}: {e}")
        crud.delete_cached_flyer_image(db, new_flipp_flyer_id) # This function handles commit
        logger.info(f"Deleted old DB record for flipp_flyer_id {new_flipp_flyer_id}")

    # 4. Save the new image
    stitched_flyer_dir = os.path.join(UPLOAD_DIR, STITCHED_FLYERS_SUBDIR)
    # Ensure directory exists (should be by startup, but good to be safe)
    os.makedirs(stitched_flyer_dir, exist_ok=True) 
    image_filename = f"{new_flipp_flyer_id}.png" # Use flipp_flyer_id for unique, predictable filename
    saved_image_path = os.path.join(stitched_flyer_dir, image_filename)

    try:
        with open(saved_image_path, "wb") as f:
            f.write(image_bytes)
        logger.info(f"Saved new stitched flyer to {saved_image_path}")
    except IOError as e:
        logger.error(f"Failed to save stitched flyer image to {saved_image_path}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save processed flyer image.")

    # 5. Create new cache record in DB
    try:
        db_cached_flyer = crud.create_cached_flyer_image(
            db=db,
            flipp_flyer_id=new_flipp_flyer_id,
            merchant_name=request_data.merchant_name, # Use merchant name from request
            image_path=saved_image_path, # Store the absolute path
            postal_code=request_data.postal_code
        )
        logger.info(f"Successfully cached new flyer image: ID {db_cached_flyer.flipp_flyer_id}, Path: {db_cached_flyer.image_path}")
    except Exception as e: # Catch potential DB errors, e.g., unique constraints if logic above missed something
        logger.error(f"Failed to create cache record for flyer ID {new_flipp_flyer_id}: {e}")
        # Attempt to clean up saved image if DB entry fails
        if os.path.exists(saved_image_path):
            try: os.remove(saved_image_path) 
            except OSError: pass
        raise HTTPException(status_code=500, detail="Failed to save flyer information to database.")

    return FetchedFlyerInfoResponse(
        flipp_flyer_id=db_cached_flyer.flipp_flyer_id,
        merchant_name=db_cached_flyer.merchant_name,
        image_path=db_cached_flyer.image_path,
        postal_code=db_cached_flyer.postal_code,
        message="Fetched, processed, and cached new flyer image."
    )

@router.post("/extract/", response_model=dict, responses={400: {"description": "Error processing flyer"}, 500: {"description": "Internal server error"}})
async def extract_flyer_endpoint(
    store_name: str = Form("Walmart"),
    image_path: Optional[str] = Form(None), # Added image_path
    file: Optional[UploadFile] = File(None),  # Made file optional
    db: Session = Depends(get_db)
):
    """
    Receives a flyer image (either as an upload or a server path),
    extracts item data using Gemini, validates the data, saves it to the database,
    and returns a status message.
    """
    input_image_path: str = ""
    delete_input_image_after_processing: bool = False

    if image_path:
        logger.info(f"Extracting from provided image_path: {image_path} for store: {store_name}")
        if not os.path.exists(image_path):
            logger.error(f"Provided image_path does not exist: {image_path}")
            raise HTTPException(status_code=400, detail=f"Provided image_path does not exist: {image_path}")
        input_image_path = image_path
        delete_input_image_after_processing = False # Do not delete if path was provided
    elif file:
        logger.info(f"Extracting from uploaded file: {file.filename} for store: {store_name}")
        # Generate a unique filename to avoid collisions for uploaded file
        file_extension = os.path.splitext(file.filename)[1] if file.filename else ".png"
        temp_filename = f"{uuid.uuid4()}{file_extension}"
        temp_upload_path = os.path.join(UPLOAD_DIR, temp_filename)
        
        try:
            with open(temp_upload_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            logger.info(f"Uploaded file saved temporarily to: {temp_upload_path}")
            input_image_path = temp_upload_path
            delete_input_image_after_processing = True # Uploaded temp file should be deleted
        except Exception as e:
            logger.error(f"Could not save uploaded file: {e}")
            raise HTTPException(status_code=500, detail=f"Could not save uploaded file: {e}")
        finally:
            if file.file and not file.file.closed:
                 await file.close() # Ensure uploaded file stream is closed
    else:
        logger.error("No image_path or file provided for extraction.")
        raise HTTPException(status_code=400, detail="You must provide either an image_path or upload a file.")

    if not input_image_path:
        # This case should ideally be caught by the logic above, but as a safeguard:
        logger.error("Input image path was not set prior to extraction attempt.")
        raise HTTPException(status_code=500, detail="Internal error: Image path not determined.")

    try:
        # Call the Gemini service with the determined input_image_path
        logger.info(f"Calling Gemini service for image: {input_image_path}")
        extracted_data = gemini_service.extract_flyer_data_from_image(input_image_path, store_name)

        if "error" in extracted_data:
            logger.error(f"Gemini service error: {extracted_data['error']}")
            raise HTTPException(status_code=400, detail=f"Failed to extract flyer data: {extracted_data['error']}")

        try:
            validated_data = FlyerItemList(**extracted_data)
            if not validated_data.items:
                logger.warning("No items extracted from the flyer by Gemini.")
                # Depending on requirements, this might not be an error, but a valid empty extraction
                # For now, let's treat it as a case where nothing was saved, but not an exception.
                return {"message": "No items were extracted from the flyer."}
        except ValidationError as e:
            logger.error(f"Pydantic validation error: {e}. Extracted data: {extracted_data}")
            raise HTTPException(status_code=400, detail=f"Extracted data validation failed: {e}")

        try:
            created_db_items = crud.create_flyer_items(db=db, items=validated_data.items)
            logger.info(f"Successfully extracted and saved {len(created_db_items)} items for store {store_name}.")
            return {"message": f"Successfully extracted and saved {len(created_db_items)} items."}
        except Exception as db_exc:
            logger.error(f"Database error while saving items for {store_name}: {db_exc}")
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error occurred: {db_exc}")

    except HTTPException as http_exc:
        # Re-raise HTTPExceptions directly
        raise http_exc
    except Exception as e:
        logger.exception(f"Unexpected error in /extract endpoint for image {input_image_path}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
    finally:
        if delete_input_image_after_processing and os.path.exists(input_image_path):
            try:
                os.remove(input_image_path)
                logger.info(f"Deleted temporary uploaded file: {input_image_path}")
            except Exception as remove_err:
                logger.error(f"Error removing temp file {input_image_path}: {remove_err}")

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
    print(f"[*] Found {len(db_items) if db_items else 0} items for store: {store_name}")
    # FastAPI automatically converts SQLAlchemy models to Pydantic response_model if fields match
    return db_items