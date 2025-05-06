import { useState, useEffect } from 'react';
import './App.css';

// --- Interfaces ---
// Interface for the structure of a flyer from the Flipp API
interface FlippFlyer {
  id: number; // Changed from flyer_id to id
  merchant: string;
  flyer_run_id: number;
  thumbnail_url: string;
  categories: string[];
  // Add other relevant fields if needed
}

// Interface for the overall API response
interface FlippApiResponse {
  flyers: FlippFlyer[];
  // Add other top-level fields if needed
}

// Keep MealPlan interface if meal plan generation from Flipp data is intended later
interface MealPlan {
  meal_plan: { [day: string]: string };
  shopping_list: string[];
}

// Interface for the response from the /flyer/fetch-and-store/ endpoint
interface FetchedFlyerInfo {
  flipp_flyer_id: number;
  merchant_name: string;
  image_path: string; // Path to the image on the server
  postal_code: string;
  message: string;
}

// Interface for the meal plan generation request
interface MealPlanGenerationRequest {
  store_name: string;
}

function App() {
  // State for Flipp Flyers
  const [groceryFlyers, setGroceryFlyers] = useState<FlippFlyer[]>([]);
  const [isFetchingFlipp, setIsFetchingFlipp] = useState<boolean>(false);
  const [flippError, setFlippError] = useState<string | null>(null);

  // State for Meal Plan Generation / Flyer Processing
  const [mealPlan, setMealPlan] = useState<MealPlan | null>(null);
  const [isProcessing, setIsProcessing] = useState<boolean>(false); // Renamed from isGenerating
  const [processingError, setProcessingError] = useState<string | null>(null); // Renamed from generationError
  const [processingMessage, setProcessingMessage] = useState<string | null>(null); // For general status updates
  const [selectedFlyerId, setSelectedFlyerId] = useState<number | null>(null); // To track selected flyer for processing
  const [selectedFlyer, setSelectedFlyer] = useState<FlippFlyer | null>(null);

  // Fetch Flipp Flyers on component mount
  useEffect(() => {
    const fetchFlippFlyers = async () => {
      setIsFetchingFlipp(true);
      setFlippError(null);
      const postalCode = "V1P0A1"; // Kelowner postal code for testing
      const flippUrl = `https://flyers-ng.flippback.com/api/flipp/data?locale=en&postal_code=${postalCode}&sid=5672125193598641`;

      console.log("Fetching flyers from Flipp API...");

      try {
        const response = await fetch(flippUrl);

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data: FlippApiResponse = await response.json();

        console.log("Flipp API Response:", data); // Log the full response

        // Filter for flyers that include "Groceries" in their categories
        const filteredFlyers = data.flyers.filter(flyer =>
          flyer.categories && flyer.categories.includes("Groceries")
        );

        console.log("Filtered Grocery Flyers:", filteredFlyers); // Log the filtered results
        setGroceryFlyers(filteredFlyers);

        if (filteredFlyers.length === 0) {
          setFlippError("No grocery flyers found for this postal code.");
        }
      } catch (err) {
        console.error("Flipp API Fetch Error:", err);
        setFlippError(err instanceof Error ? err.message : 'An unknown error occurred while fetching flyers');
        if (err instanceof Error && err.message.toLowerCase().includes('failed to fetch')) {
          setFlippError('Failed to fetch flyers. This might be a CORS issue. Consider using a backend proxy.');
        }
      } finally {
        setIsFetchingFlipp(false);
      }
    };

    fetchFlippFlyers();
  }, []); // Empty dependency array means run once on mount

  // --- Flyer Selection and Processing Logic ---
  const handleFlyerSelection = async (flyerId: number | null) => {
    console.log("handleFlyerSelection called with flyerId:", flyerId);
    if (flyerId == null) {
      setProcessingError("Invalid flyer ID provided.");
      return;
    }

    const currentFlyer = groceryFlyers.find(f => f.id === flyerId);
    if (!currentFlyer) {
      setProcessingError("Selected flyer not found in the list.");
      return;
    }

    if (isProcessing && selectedFlyerId === flyerId) {
      return;
    }

    setProcessingError(null);
    setProcessingMessage("Starting flyer processing..."); // Initial message
    setIsProcessing(true);
    setMealPlan(null);
    setSelectedFlyerId(flyerId);
    setSelectedFlyer(currentFlyer); // Store the whole flyer object

    console.log(`Processing flyer ID: ${flyerId}, Store: ${currentFlyer.merchant}`);

    try {
      // Step 1: Call /flyer/fetch-and-store/
      setProcessingMessage(`Fetching and preparing flyer for ${currentFlyer.merchant}...`);
      const fetchStoreResponse = await fetch("/api/flyer/fetch-and-store/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          merchant_name: currentFlyer.merchant,
          postal_code: "V1P0A1", // TODO: Make postal code dynamic if needed
          // category: "Groceries" // Optional, defaults in backend
        }),
      });

      if (!fetchStoreResponse.ok) {
        const errorData = await fetchStoreResponse.json().catch(() => ({ message: `Fetching flyer failed with status: ${fetchStoreResponse.status}` }));
        throw new Error(errorData.detail || errorData.message || `Failed to fetch or store flyer. Status: ${fetchStoreResponse.status}`);
      }

      const fetchedFlyerInfo: FetchedFlyerInfo = await fetchStoreResponse.json();
      console.log("Flyer fetched/stored successfully:", fetchedFlyerInfo.message);
      setProcessingMessage(`Flyer ready. Extracting items from ${currentFlyer.merchant} flyer...`);

      // Step 2: Call /flyer/extract/ using the image_path from Step 1
      const formData = new FormData();
      formData.append("store_name", currentFlyer.merchant);
      formData.append("image_path", fetchedFlyerInfo.image_path);
      // No need to append file if image_path is used

      const extractResponse = await fetch("/api/flyer/extract/", {
        method: "POST",
        body: formData,
      });

      if (!extractResponse.ok) {
        const errorData = await extractResponse.json().catch(() => ({ message: `Extraction failed with status: ${extractResponse.status}` }));
        throw new Error(errorData.detail || errorData.message || `Failed to extract items. Status: ${extractResponse.status}`);
      }

      const extractionResult = await extractResponse.json();
      console.log("Extraction successful:", extractionResult.message);
      setProcessingMessage(`Items extracted. Generating meal plan for ${currentFlyer.merchant}...`);

      // Step 3: Generate meal plan using /mealplan/generate/
      console.log(`Generating meal plan for store: ${currentFlyer.merchant}`);
      const mealPlanRequestData: MealPlanGenerationRequest = { store_name: currentFlyer.merchant };

      const mealplanResponse = await fetch("/api/mealplan/generate/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(mealPlanRequestData),
      });

      if (!mealplanResponse.ok) {
        const errorData = await mealplanResponse.json().catch(() => ({ message: `Meal plan generation failed with status: ${mealplanResponse.status}` }));
        throw new Error(errorData.message || `Failed to generate meal plan. Status: ${mealplanResponse.status}`);
      }

      const mealPlanResult: MealPlan = await mealplanResponse.json();
      setMealPlan(mealPlanResult);
      console.log("Meal plan generated successfully.");
      setProcessingMessage("Meal plan complete!");

    } catch (err) {
      console.error("Error during flyer processing or meal plan generation:", err);
      setProcessingError(err instanceof Error ? err.message : "An unknown error occurred.");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="app-container">
      <h1>WhatTheFlip Meal Planner</h1>

      {/* Flyer Grid Section */}
      <div className="card flyer-grid-section">
        <h2>Grocery Flyers</h2>
        {isFetchingFlipp && (
          <div className="loading-message">
            <span className="loader"></span> Loading flyers...
          </div>
        )}
        {flippError && <div className="error-message">{flippError}</div>}

        {!isFetchingFlipp && !flippError && groceryFlyers.length > 0 && (
          <div className="flyer-grid">
            {groceryFlyers.map((flyer) => {
              console.log("Mapping flyer:", flyer.id, flyer); // <-- Log flyer.id
              return (
                <div
                  key={flyer.id} // Use flyer.id for the key
                  className={`flyer-card ${selectedFlyerId === flyer.id ? 'selected' : ''} ${isProcessing && selectedFlyerId === flyer.id ? 'processing' : ''}`}
                  onClick={() => !isProcessing ? handleFlyerSelection(flyer.id) : undefined} // Pass flyer.id to the handler
                  style={{ cursor: isProcessing ? 'default' : 'pointer' }}
                >
                  <img src={flyer.thumbnail_url} alt={`${flyer.merchant} Flyer`} className="flyer-card-image"/>
                  <p className="flyer-card-merchant">{flyer.merchant}</p>
                  {isProcessing && selectedFlyerId === flyer.id && ( // Use flyer.id for comparison
                    <div className="loading-indicator">
                      <span className="loader-small"></span> Processing...
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
        {!isFetchingFlipp && !flippError && groceryFlyers.length === 0 && (
          <p>No grocery flyers found.</p>
        )}
      </div> 

      {/* Meal Plan Display Section */}
      {processingError && <div className="error-message">{processingError}</div>}
      {isProcessing && selectedFlyerId !== null && !mealPlan && (
        <div className="loading-message">
          <span className="loader"></span> 
          {processingMessage || (selectedFlyer ? `Processing ${selectedFlyer.merchant} flyer and generating plan...` : 'Processing flyer and generating plan...')}
        </div>
      )}
      {mealPlan && selectedFlyer && (
        <div className="card">
           <h2>Your 5-Day Meal Plan (Based on {selectedFlyer.merchant} Flyer)</h2>
           <div className="meal-plan-days">
             <h3>Dinner Plan</h3>
             <ul className="item-list">
               {Object.entries(mealPlan.meal_plan).map(([day, meal]) => (
                 <li key={day}>
                   <span className="meal-day">{day}</span>
                   <span>{meal}</span>
                 </li>
               ))}
             </ul> 
           </div>
           <div className="shopping-list">
             <h3>Shopping List</h3>
             <ul className="item-list">
               {mealPlan.shopping_list.map((item, index) => (
                 <li key={index}>{item}</li>
               ))}
             </ul>
           </div>
        </div>
      )}
    </div>
  );
}

export default App;
