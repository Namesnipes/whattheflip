from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db import crud, models as db_models # Renamed to avoid conflict
from app.db.database import get_db
from app.models.mealplan import MealPlanRequest, MealPlanResponse
from app.services import gemini_service

router = APIRouter(
    prefix="/mealplan",
    tags=["mealplan"],
)

@router.post("/generate/", response_model=MealPlanResponse)
async def generate_meal_plan(
    request: MealPlanRequest,
    db: Session = Depends(get_db)
):
    """
    Generates a 5-day meal plan based on recently extracted flyer items for a given store.
    """
    print(f"[*] Received request to generate meal plan for store: {request.store_name}")

    # 1. Fetch recent flyer items from DB
    # Using default limit of 100 items from last 7 days
    db_items = crud.get_flyer_items_by_store(db=db, store_name=request.store_name)
    if not db_items:
        raise HTTPException(status_code=404, detail=f"No recent flyer items found for store '{request.store_name}'. Extract flyer data first.")

    print(f"[*] Found {len(db_items)} relevant items in DB.")

    # Convert DB models to dictionaries for Gemini service
    items_for_gemini = [
        {
            "name": item.name,
            "price": item.price,
            "sellingUnit": item.sellingUnit,
            "sellingValue": item.sellingValue,
            "measuredQuantityValue": item.measuredQuantityValue,
            "measuredQuantityUnit": item.measuredQuantityUnit,
            "store": item.store,
            "notes": item.notes,
        } for item in db_items
    ]

    # 2. Call Gemini service to generate meal plan
    # Run the synchronous Gemini call in FastAPI's threadpool
    meal_plan_result = await gemini_service.generate_meal_plan_from_items(
        items=items_for_gemini,
        store_name=request.store_name
    )

    # 3. Handle response from Gemini service
    if "error" in meal_plan_result:
        print(f"[!] Error generating meal plan: {meal_plan_result['error']}")
        # Include raw response in error detail if available
        error_detail = meal_plan_result['error']
        if "raw_response" in meal_plan_result:
            error_detail += f" | Raw Response: {meal_plan_result['raw_response'][:500]}..." # Limit length
        raise HTTPException(status_code=500, detail=error_detail)

    # 4. Return the successful response
    return MealPlanResponse(
        meal_plan=meal_plan_result["meal_plan"],
        shopping_list=meal_plan_result["shopping_list"]
    )
