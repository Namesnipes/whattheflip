import os
from dotenv import load_dotenv
import google.generativeai as genai
import google.ai.generativelanguage as glm # Import the correct module for types
import json
import mimetypes # To detect file type
import re # For parsing the meal plan response
from typing import List # Import List
import fitz # Import PyMuPDF

# Load environment variables (especially GOOGLE_API_KEY)
load_dotenv()

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment variables.")

genai.configure(api_key=GOOGLE_API_KEY)

# Define the flyer item schema for Gemini function calling
flyer_item_schema = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "The name of the produce item as advertised (e.g., 'Tomatoes on the Vine', 'Russet Potatoes')."
        },
        "price": {
            "type": "number",
            "format": "float",
            "description": "The total selling price advertised for the item based on its selling unit (e.g., price for 1 pack, price per lb)."
        },
        "sellingUnit": {
            "type": "string",
            "description": "The primary unit by which the item is sold or priced (e.g., 'pack' for a clamshell, 'bag' for a bag of potatoes, 'lb' or 'kg' for loose items priced by weight, 'each' for items sold individually, 'bunch').",
            "enum": [
                "pack",
                "bag",
                "lb",
                "kg",
                "each",
                "oz",
                "g",
                "count",
                "bunch"
            ]
        },
        "sellingValue": {
            "type": "number",
            "description": "The number of 'sellingUnit's the advertised price applies to. Typically 1 for most items. For multi-buy deals like '3 for $5', this would be 3. Should be null if not explicitly stated or clearly implied.",
            "nullable": True
        },
        "measuredQuantityValue": {
            "type": "number",
            "description": "The specific numerical amount of the measured quantity (e.g., 454 for 454g, 5 for 5 lbs). Null if the selling unit is the measurement (like 'lb') or if not stated.",
            "nullable": True
        },
        "measuredQuantityUnit": {
            "type": "string",
            "description": "The unit for the 'measuredQuantityValue' (e.g., 'g', 'oz', 'lb', 'kg', 'count'). Null if 'measuredQuantityValue' is null.",
            "nullable": True,
            "enum": [
                "g",
                "oz",
                "lb",
                "kg",
                "count",
                "mL",
                "L"
            ]
        },
        "store": {
            "type": "string",
            "description": "The name of the store where the item is being sold (e.g., 'Save on Foods', 'Walmart')."
        },
        "notes": {
            "type": "string",
            "description": "Any other relevant details extracted, such as country of origin, variety, organic status, packaging description ('clamshell'), grade ('No. 1 Grade'), special offers ('My Offers').",
            "nullable": True
        }
    },
    "required": [
        "name",
        "price",
        "sellingUnit",
        "store",
        "measuredQuantityUnit",
        "measuredQuantityValue"
    ]
}

# Define the overall structure Gemini should return (a list of items)
flyer_extraction_schema = {
    "type": "array",
    "description": "A list of produce items extracted from flyers. Includes details like price, how it's sold (selling unit), the measured quantity, store, and any relevant notes. Unit price should be calculated programmatically from price and measured quantity.",
    "items": flyer_item_schema
}

# Generation configuration for Gemini
generation_config = {
    "temperature": 0.2, # Lower temperature for more deterministic extraction
    "top_p": 1,
    "top_k": 32,
    "max_output_tokens": 8192,
    # "response_schema": flyer_extraction_schema # Use function calling for structured output instead
}

# Safety settings (adjust as needed)
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

# Tool definition for Gemini function calling
extract_flyer_items_tool = genai.types.Tool(
    function_declarations=[
        genai.types.FunctionDeclaration(
            name='extract_flyer_items',
            description='Extracts all grocery items and their details from a flyer image.',
            # Correctly define parameters directly within the FunctionDeclaration
            parameters={
                "type_": glm.Type.OBJECT, # Use glm.Type
                "properties": {
                    'items': {
                        "type_": glm.Type.ARRAY, # Use glm.Type
                        "description": "List of extracted flyer items",
                        "items": {
                            "type_": glm.Type.OBJECT, # Use glm.Type
                            "properties": {
                                # Map schema properties to FunctionDeclaration parameter definitions
                                prop: {
                                    # Use glm.Type for type definitions
                                    "type_": glm.Type.STRING if details['type'] == 'string' else glm.Type.NUMBER if details['type'] == 'number' else glm.Type.BOOLEAN,
                                    "description": details.get('description', ''),
                                    "nullable": details.get('nullable', False) # Add nullable if present in schema
                                }
                                for prop, details in flyer_item_schema['properties'].items()
                            },
                            "required": flyer_item_schema['required']
                        }
                    }
                },
                "required": ['items']
            }
        )
    ]
)


def extract_flyer_data_from_image(file_path: str, store_name: str) -> dict:
    """Extracts structured flyer data from an image or PDF using Gemini Pro Vision."""
    print(f"[*] Starting flyer data extraction for {store_name} from {file_path}")
    parts = [] # List to hold all parts (prompt + images/pdf)

    try:
        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            # Fallback if guess fails
            if file_path.lower().endswith('.pdf'):
                mime_type = 'application/pdf'
            elif file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                 mime_type = f'image/{file_path.split(".")[-1].lower().replace("jpg", "jpeg")}'
            else:
                 raise ValueError(f"Could not determine MIME type for file: {file_path}")
        print(f"[*] Detected MIME type: {mime_type}")

        if mime_type == 'application/pdf':
            print("[*] Processing PDF file...")
            doc = fitz.open(file_path)
            image_parts = []
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                # Increase resolution (dpi) for better quality if needed
                pix = page.get_pixmap(dpi=150) # Adjust DPI as necessary
                img_bytes = pix.tobytes("png") # Convert to PNG bytes
                image_parts.append({
                    "mime_type": "image/png",
                    "data": img_bytes
                })
            doc.close()
            if not image_parts:
                 return {"error": "PDF processed, but no pages could be converted to images."}
            print(f"[*] Converted {len(image_parts)} PDF pages to images.")
            # Prepare prompt for multi-image input
            prompt = f"Analyze the provided {store_name} flyer document (sent as multiple images, one per page). Extract all grocery items according to the 'extract_flyer_items' function schema. Populate all required fields: {', '.join(flyer_item_schema['required'])}. Call the 'extract_flyer_items' function with the extracted data."
            parts.append(prompt)
            # Add image parts, potentially adding page numbers in the prompt if context is lost
            parts.extend(image_parts)

        elif mime_type.startswith('image/'):
            print("[*] Processing single image file...")
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
            file_data_part = {
                "mime_type": mime_type,
                "data": file_bytes
            }
            # Prepare prompt for single image
            prompt = f"Analyze the provided {store_name} flyer image ({mime_type}). Extract all grocery items according to the 'extract_flyer_items' function schema. Populate all required fields: {', '.join(flyer_item_schema['required'])}. Call the 'extract_flyer_items' function with the extracted data."
            parts.append(prompt)
            parts.append(file_data_part)
        else:
            # Handle other potential file types or raise error
             return {"error": f"Unsupported file type: {mime_type}"}


    except FileNotFoundError:
        print(f"[!] Error: File not found at {file_path}")
        return {"error": "File not found"}
    except Exception as e:
        print(f"[!] Error reading or processing file {file_path}: {e}")
        return {"error": f"Failed to read or process file: {e}"}

    # Use gemini-1.5-pro-latest
    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro-latest",
        generation_config=generation_config,
        safety_settings=safety_settings,
        tools=[extract_flyer_items_tool]
    )

    try:
        print("[*] Sending request to Gemini API...")
        # Force the function call using ANY mode and specifying the allowed function
        response = model.generate_content(
            parts, # Send the combined list of parts (prompt + images)
            tool_config=glm.ToolConfig(
                function_calling_config=glm.FunctionCallingConfig(
                    mode=glm.FunctionCallingConfig.Mode.ANY, # Use ANY (or REQUIRED if it must call it)
                    allowed_function_names=["extract_flyer_items"] # Specify the function to call
                )
            )
        )
        print("[*] Received response from Gemini API.")

        # Check for function call in response
        if response.candidates and response.candidates[0].content.parts:
            part = response.candidates[0].content.parts[0]
            # Check if the part actually contains a function call
            if hasattr(part, 'function_call') and part.function_call.name == 'extract_flyer_items':
                function_call = part.function_call
                # Convert the function call arguments (which are Struct) to a Python dict
                try:
                    # Attempt direct conversion if the library handles it nicely
                    extracted_data = type(function_call).to_dict(function_call)['args']
                except Exception as convert_err:
                     print(f"[!] Error converting function call args to dict: {convert_err}")
                     # Fallback or alternative conversion method might be needed
                     extracted_data = {'items': []} # Default to empty list on error

                print(f"[*] Successfully extracted {len(extracted_data.get('items', []))} items via function call.")
                # TODO: Add validation against Pydantic model FlyerItemList here
                return extracted_data
            else:
                # Handle cases where Gemini returned text instead of the expected function call
                text_response = ""
                if hasattr(part, 'text'):
                    text_response = part.text
                print("[!] Gemini responded with text instead of the expected function call.")
                print(f"Response Text: {text_response}")
                return {"error": "Gemini did not call the expected function.", "details": text_response}
        else:
            # Handle cases where no function call was made or response is blocked/empty
            error_message = "Gemini did not return a valid response or function call."
            finish_reason = 'UNKNOWN'
            safety_ratings = []
            if response.candidates:
                 finish_reason = response.candidates[0].finish_reason
                 safety_ratings = response.candidates[0].safety_ratings
            print(f"[!] Finish Reason: {finish_reason}")
            print(f"[!] Safety Ratings: {safety_ratings}")

            if response.prompt_feedback.block_reason:
                error_message += f" Blocked due to: {response.prompt_feedback.block_reason}"
            print(f"[!] {error_message}")

            # Try to get text even if no parts or function call
            try:
                response_text = response.text
                print(f"Response Text: {response_text}")
                return {"error": error_message, "details": response_text}
            except Exception:
                 return {"error": error_message}


    except Exception as e:
        print(f"[!] An error occurred during Gemini API call: {e}")
        return {"error": f"Gemini API request failed: {e}"}

# --- Meal Plan Generation ---

# Configuration for Gemini Flash (adjust as needed)
flash_generation_config = {
    "temperature": 0.7, # Higher temperature for more creative meal planning
    "top_p": 1,
    "top_k": 32,
    "max_output_tokens": 8192,
}

# Define the expected structure for the meal plan response (for parsing)
# This is a basic example; more robust parsing might be needed
MEAL_PLAN_DAY_PATTERN = re.compile(r"Day\s+(\d+):\s*(.*)", re.IGNORECASE)
SHOPPING_LIST_HEADER_PATTERN = re.compile(r"Shopping List:", re.IGNORECASE)

def parse_meal_plan_response(text_response: str) -> dict:
    """Parses the raw text response from Gemini into a structured meal plan and shopping list."""
    meal_plan = {}
    shopping_list = []
    in_shopping_list_section = False

    lines = text_response.strip().split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for shopping list header
        if SHOPPING_LIST_HEADER_PATTERN.search(line):
            in_shopping_list_section = True
            continue

        if in_shopping_list_section:
            # Simple list parsing (assumes items start with '-' or '*')
            if line.startswith(('-', '*')):
                shopping_list.append(line[1:].strip())
            # Add more robust parsing if needed
        else:
            # Check for meal plan day
            day_match = MEAL_PLAN_DAY_PATTERN.match(line)
            if day_match:
                day_num = day_match.group(1)
                meal_desc = day_match.group(2).strip()
                meal_plan[f"Day {day_num}"] = meal_desc
            # Handle potential introductory text before Day 1 if needed

    return {"meal_plan": meal_plan, "shopping_list": shopping_list}


async def generate_meal_plan_from_items(items: List[dict], store_name: str) -> dict:
    """Generates a meal plan using Gemini Flash based on a list of flyer items."""
    print(f"[*] Starting meal plan generation using {len(items)} items from {store_name}.")

    if not items:
        return {"error": "No flyer items provided to generate meal plan."}

    # Format items for the prompt
    item_list_str = "\n".join([
        f"- {item['name']}: ${item['price']:.2f} / {item.get('sellingValue') or 1} {item['sellingUnit']}" +
        (f" ({item.get('measuredQuantityValue')} {item.get('measuredQuantityUnit')})" if item.get('measuredQuantityValue') and item.get('measuredQuantityUnit') else "") +
        (f" (Notes: {item.get('notes')})" if item.get('notes') else "")
        for item in items
    ])

    prompt = f"""
Here is the food items list from a {store_name} flyer in CAD:
{item_list_str}

Please plan a healthy but cheap one-person dinner-only meal plan for 5 days, pulling from this week's sales along with other ingredients that are required but may not be shown in the flyer.

Structure the response as follows:
First, list the meals for each day clearly, like:
Day 1: [Meal Description]
Day 2: [Meal Description]
...
Day 5: [Meal Description]

After the 5-day plan, add a clear header "Shopping List:" and then list all the ingredients used for the entire meal plan as a bulleted list (e.g., using '- ' or '* '). The intent is to be able to shop them at the beginning of the workweek and have food to make dinner for all 5 days.
"""

    try:
        # Use gemini-1.5-flash-latest (or the specific version you intend)
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash-latest",
            generation_config=flash_generation_config,
            safety_settings=safety_settings,
            # No function calling needed here, we'll parse the text response
        )

        print("[*] Sending request to Gemini API for meal plan...")
        # Use generate_content_async for async compatibility if needed, or run sync in thread
        # For simplicity here, using the sync version (FastAPI runs it in a threadpool)
        response = model.generate_content(prompt)
        print("[*] Received response from Gemini API.")

        if response.text:
            print("[*] Parsing Gemini response...")
            parsed_data = parse_meal_plan_response(response.text)
            if not parsed_data["meal_plan"] or not parsed_data["shopping_list"]:
                 print("[!] Warning: Could not fully parse meal plan or shopping list from response.")
                 # Return raw response for debugging if parsing fails
                 return {"error": "Failed to parse meal plan structure from Gemini response.", "raw_response": response.text}
            print("[*] Successfully generated and parsed meal plan.")
            return parsed_data
        else:
            # Handle blocked response or empty text
            error_message = "Gemini did not return any text content."
            if response.prompt_feedback.block_reason:
                error_message += f" Blocked due to: {response.prompt_feedback.block_reason}"
            print(f"[!] {error_message}")
            return {"error": error_message}

    except Exception as e:
        print(f"[!] An error occurred during Gemini API call for meal plan: {e}")
        return {"error": f"Gemini API request failed: {e}"}

# Example usage (for testing this module directly)
if __name__ == "__main__":
    # Assumes the stitched flyer image from poc.py is in the parent 'test' directory
    # Adjust the path if your structure is different
    script_dir = os.path.dirname(__file__) # Gets the directory of the current script (services)
    project_root = os.path.dirname(os.path.dirname(script_dir)) # Navigate up two levels to project root
    test_image_path = os.path.join(project_root, 'test', 'real_flyer.pdf')

    if not os.path.exists(test_image_path):
        print(f"[!] Test image not found at expected location: {test_image_path}")
        print("Please ensure the 'combined_walmart_flyer_stitched.png' exists in the 'test' directory.")
    else:
        print(f"[*] Testing flyer extraction with image: {test_image_path}")
        result = extract_flyer_data_from_image(test_image_path, "Walmart")
        print("\n--- Extraction Result ---")
        print(json.dumps(result, indent=2))
        print("--- End Result ---")
