from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from ..models.flyer import FlyerItem # Pydantic model for input data
from . import models # SQLAlchemy models (models.FlyerItemDB)

def create_flyer_items(db: Session, items: List[FlyerItem]):
    """Adds multiple flyer items (from Pydantic models) to the database."""
    db_items = [
        models.FlyerItemDB(
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
    # Refreshing multiple items might be inefficient if not needed immediately
    # for db_item in db_items:
    #     db.refresh(db_item)
    print(f"[*] Successfully added {len(db_items)} items to the database.")
    return db_items # Return the list of created DB objects

def get_flyer_items_by_store(db: Session, store_name: str, limit: int = 100, days_limit: int = 7) -> List[models.FlyerItemDB]:
    """
    Retrieves flyer items for a specific store, optionally limited by date.
    Fetches items added within the last 'days_limit' days.
    """
    query_date_threshold = datetime.utcnow() - timedelta(days=days_limit)
    # Use parentheses for line continuation instead of backslashes
    return (db.query(models.FlyerItemDB)
              .filter(models.FlyerItemDB.store == store_name)
              .filter(models.FlyerItemDB.extracted_at >= query_date_threshold)
              .order_by(models.FlyerItemDB.extracted_at.desc())
              .limit(limit)
              .all())
