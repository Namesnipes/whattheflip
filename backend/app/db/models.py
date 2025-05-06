from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from .database import Base

class FlyerItemDB(Base):
    __tablename__ = "flyer_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    price = Column(Float, nullable=False)
    sellingUnit = Column(String, nullable=False)
    sellingValue = Column(Float, nullable=True)
    measuredQuantityValue = Column(Float, nullable=True) # Made nullable=True as per Pydantic model
    measuredQuantityUnit = Column(String, nullable=True) # Made nullable=True as per Pydantic model
    store = Column(String, index=True, nullable=False)
    notes = Column(String, nullable=True)
    extracted_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CachedFlyerImage(Base):
    __tablename__ = "cached_flyer_images"

    id = Column(Integer, primary_key=True, index=True)
    flipp_flyer_id = Column(Integer, unique=True, index=True, nullable=False)
    merchant_name = Column(String, index=True, nullable=False)
    image_path = Column(String, nullable=False, unique=True) # Path to the locally stored stitched image
    postal_code = Column(String, index=True, nullable=False)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
