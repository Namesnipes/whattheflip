from fastapi import FastAPI
from .routers import flyer, mealplan # Import the flyer and mealplan routers

app = FastAPI(
    title="WhatTheFlip API",
    description="API for extracting flyer data and generating meal plans.",
    version="0.1.0",
)

# Include the routers
app.include_router(flyer.router)
app.include_router(mealplan.router) # Add the meal plan router

@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to the WhatTheFlip API!"}

# Optional: Add CORS middleware if the frontend will be on a different origin
# from fastapi.middleware.cors import CORSMiddleware
# origins = [
#     "http://localhost:5173", # Default Vite dev server port
#     "http://localhost:3000", # Default Create React App dev server port
#     # Add your frontend deployment URL here
# ]
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
