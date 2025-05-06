from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class MealPlanRequest(BaseModel):
    store_name: str = Field(..., description="The store name to fetch flyer items for (e.g., 'Walmart').")
    # Optional: Add date filters later if needed
    # start_date: Optional[str] = None
    # end_date: Optional[str] = None

class MealPlanResponse(BaseModel):
    meal_plan: Dict[str, str] = Field(..., description="A dictionary mapping day (e.g., 'Day 1') to the planned dinner.")
    shopping_list: List[str] = Field(..., description="A list of all ingredients required for the meal plan.")
    # Optional: Include the raw Gemini response for debugging
    # raw_response: Optional[str] = None
