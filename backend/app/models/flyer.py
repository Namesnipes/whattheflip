from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class FlyerItem(BaseModel):
    name: str = Field(..., description="The name of the produce item as advertised (e.g., 'Tomatoes on the Vine', 'Russet Potatoes').")
    price: float = Field(..., description="The total selling price advertised for the item based on its selling unit (e.g., price for 1 pack, price per lb).")
    sellingUnit: Literal["pack", "bag", "lb", "kg", "each", "oz", "g", "count", "bunch", "bottle", "tin", "canister"] = Field(..., description="The primary unit by which the item is sold or priced.")
    sellingValue: Optional[float] = Field(None, description="The number of 'sellingUnit's the advertised price applies to. Typically 1. For multi-buy deals like '3 for $5', this would be 3.")
    measuredQuantityValue: Optional[float] = Field(None, description="The specific numerical amount of the measured quantity (e.g., 454 for 454g, 5 for 5 lbs).")
    measuredQuantityUnit: Optional[str] = Field(None, description="The unit for the 'measuredQuantityValue'. Can be null or any string provided.")
    store: str = Field(..., description="The name of the store where the item is being sold.")
    notes: Optional[str] = Field(None, description="Any other relevant details extracted.")

    # TODO: Add a validator or property to calculate unit price later

class FlyerItemList(BaseModel):
    items: List[FlyerItem] = Field(..., description="A list of produce items extracted from flyers.")

