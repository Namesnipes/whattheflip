from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from ..models.flyer import FlyerItem # Pydantic model for input data
from . import models as db_models # Renamed to avoid conflict with Pydantic models
from ..models import flyer as pydantic_flyer_models # Pydantic models for request/response

# --- FlyerItem CRUD operations ---

def create_flyer_items(db: Session, items: List[pydantic_flyer_models.FlyerItem]) -> List[db_models.FlyerItemDB]:
    """
    Creates multiple flyer items in the database from a list of Pydantic models.
    """
    db_items = [
        db_models.FlyerItemDB(
            name=item.name,
            price=item.price,
            sellingUnit=item.sellingUnit,
            sellingValue=item.sellingValue,
            measuredQuantityValue=item.measuredQuantityValue,
            measuredQuantityUnit=item.measuredQuantityUnit,
            store=item.store,
            notes=item.notes
        )
        for item in items
    ]
    db.add_all(db_items)
    db.commit()
    print(f"[*] Successfully added {len(db_items)} items to the database.")
    return db_items # Return the list of created DB objects

def get_flyer_items_by_store(db: Session, store_name: str, limit: int = 100, days_recent: int = 7) -> List[db_models.FlyerItemDB]:
    """
    Retrieves flyer items for a specific store, optionally filtered by how recently they were created.
    Sorts by creation date descending.
    """
    query_date_threshold = datetime.utcnow() - timedelta(days=days_recent)
    return (db.query(db_models.FlyerItemDB)
              .filter(db_models.FlyerItemDB.store == store_name)
              .filter(db_models.FlyerItemDB.extracted_at >= query_date_threshold)
              .order_by(db_models.FlyerItemDB.extracted_at.desc())
              .limit(limit)
              .all())

# --- CachedFlyerImage CRUD operations ---

def create_cached_flyer_image(db: Session, flipp_flyer_id: int, merchant_name: str, image_path: str, postal_code: str) -> db_models.CachedFlyerImage:
    """Creates a new cached flyer image record in the database."""
    db_cached_flyer = db_models.CachedFlyerImage(
        flipp_flyer_id=flipp_flyer_id,
        merchant_name=merchant_name,
        image_path=image_path,
        postal_code=postal_code
        # fetched_at is handled by server_default
    )
    db.add(db_cached_flyer)
    db.commit()
    db.refresh(db_cached_flyer)
    return db_cached_flyer

def get_cached_flyer_image_by_flipp_id(db: Session, flipp_flyer_id: int) -> Optional[db_models.CachedFlyerImage]:
    """Retrieves a cached flyer image by its Flipp flyer ID."""
    return db.query(db_models.CachedFlyerImage).filter(db_models.CachedFlyerImage.flipp_flyer_id == flipp_flyer_id).first()

def get_cached_flyer_image_by_merchant_and_postal(db: Session, merchant_name: str, postal_code: str, days_valid: int = 7) -> Optional[db_models.CachedFlyerImage]:
    """
    Retrieves the most recent valid cached flyer image for a given merchant and postal code.
    A flyer is considered valid if fetched within the last `days_valid` days.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days_valid)
    return (
        db.query(db_models.CachedFlyerImage)
        .filter(
            db_models.CachedFlyerImage.merchant_name == merchant_name,
            db_models.CachedFlyerImage.postal_code == postal_code,
            db_models.CachedFlyerImage.fetched_at >= cutoff_date
        )
        .order_by(db_models.CachedFlyerImage.fetched_at.desc())
        .first()
    )

def delete_cached_flyer_image(db: Session, flipp_flyer_id: int) -> bool:
    """Deletes a cached flyer image by its Flipp flyer ID. Returns True if deleted, False otherwise."""
    db_cached_flyer = get_cached_flyer_image_by_flipp_id(db, flipp_flyer_id)
    if db_cached_flyer:
        db.delete(db_cached_flyer)
        db.commit()
        return True
    return False
