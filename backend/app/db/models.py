from sqlalchemy import Column, Integer, String, Float, DateTime, func
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
    # Consider adding a unique constraint based on name, store, price, and date if needed later
