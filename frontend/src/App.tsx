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

// Interface for the expected response from our backend processing endpoint
interface ProcessFlyerResponse extends MealPlan {
  // Potentially add other fields returned by the backend after processing
  status: string; // e.g., 'success', 'error'
  message?: string; // Optional message from backend
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
  const [selectedFlyerId, setSelectedFlyerId] = useState<number | null>(null); // To track selected flyer for processing

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
    console.log("handleFlyerSelection called with flyerId:", flyerId); // <-- Add log here
    if (flyerId == null) {
      setProcessingError("Invalid flyer selected.");
      return;
    }

    // If already processing this flyer, don't do anything
    if (isProcessing && selectedFlyerId === flyerId) {
      return;
    }

    // Clear previous errors/results and set processing state
    setProcessingError(null);
    setIsProcessing(true);
    setMealPlan(null); // Clear previous meal plan
    setSelectedFlyerId(flyerId);

    console.log(`Processing flyer ID: ${flyerId}...`);

    try {
      // ** TODO: Replace with actual backend API call **
      // This endpoint should handle fetching flyer details, extracting items,
      // and generating the meal plan/shopping list.
      // const backendUrl = `/api/flyers/${flyerId}/process`; // Example backend endpoint
      // const response = await fetch(backendUrl, { method: 'POST' }); // Or GET, depending on backend design

      // Simulate backend call and processing delay
      await new Promise(resolve => setTimeout(resolve, 2000));

      // Simulate a successful response from the backend
      const demoResponse: ProcessFlyerResponse = {
        status: 'success',
        meal_plan: {
          "Monday": `Pasta based on Flyer ${flyerId} deals`,
          "Tuesday": `Chicken stir-fry from Flyer ${flyerId}`,
          "Wednesday": `Tacos using Flyer ${flyerId} items`,
          "Thursday": `Soup and Salad (Flyer ${flyerId})`,
          "Friday": `Pizza night (Flyer ${flyerId} ingredients)`
        },
        shopping_list: [
          `Item A from Flyer ${flyerId}`, `Item B from Flyer ${flyerId}`,
          `Item C from Flyer ${flyerId}`, `Milk`, `Eggs`
        ]
      };

      // if (!response.ok) {
      //   const errorData = await response.json().catch(() => ({ message: `HTTP error! status: ${response.status}` }));
      //   throw new Error(errorData.message || `Backend error! status: ${response.status}`);
      // }
      // const result: ProcessFlyerResponse = await response.json();

      const result = demoResponse; // Using simulated response

      if (result.status === 'success') {
        setMealPlan({ meal_plan: result.meal_plan, shopping_list: result.shopping_list });
      } else {
        throw new Error(result.message || 'Backend processing failed.');
      }

    } catch (err) {
      console.error("Error processing flyer:", err);
      setProcessingError(err instanceof Error ? err.message : "Failed to process flyer. Please try again.");
    } finally {
      setIsProcessing(false);
      // Optionally clear selectedFlyerId here or keep it to indicate the last processed flyer
      // setSelectedFlyerId(null);
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
      {isProcessing && !mealPlan && selectedFlyerId !== null && (
        <div className="loading-message">
          <span className="loader"></span> Processing flyer and generating plan...
        </div>
      )}
      {mealPlan && (
        <div className="card">
           <h2>Your 5-Day Meal Plan (Based on Flyer {selectedFlyerId})</h2>
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
