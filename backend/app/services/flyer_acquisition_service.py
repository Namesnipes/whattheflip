# backend/app/services/flyer_acquisition_service.py
import requests
import os
import tempfile
from PIL import Image
from io import BytesIO
import time
import logging

# --- Configuration ---
# TODO: Consider moving these to a config file or environment variables if they change often
FLIPP_BASE_URL = "https://flyers-ng.flippback.com/api/flipp/data"
TILE_BASE_URL = "https://f.wishabi.net/"
DEFAULT_REQUEST_DELAY_S = 0.1 # Small delay between tile requests to be polite
DEFAULT_TILE_ZOOM_LEVEL = 4 # Common zoom level for tiles
REQUEST_TIMEOUT_S = 30
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
# --- End Configuration ---

logger = logging.getLogger(__name__)

def find_flyer_path_from_flipp(postal_code: str, merchant_name: str, category: str = "Groceries") -> tuple[str | None, str | None]:
    """Fetches initial data from Flipp and finds the ID and path of the target flyer."""
    url = f"{FLIPP_BASE_URL}?locale=en&postal_code={postal_code}&sid=5672125193598641" # SID might need to be dynamic or configured
    logger.info(f"Fetching initial flyer data from {url} for merchant '{merchant_name}' in '{postal_code}'")
    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(url, timeout=REQUEST_TIMEOUT_S, headers=headers)
        response.raise_for_status()
        data = response.json()
        logger.info("Flipp data fetched successfully.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching initial Flipp data: {e}")
        return None, None
    except ValueError: # Includes JSONDecodeError
        logger.error("Error decoding JSON response from Flipp.")
        return None, None

    flyers = data.get("flyers", [])
    if not flyers:
        logger.warning("No flyers found in the Flipp response.")
        return None, None

    logger.info(f"Searching for '{merchant_name}' flyer with category '{category}'...")
    for flyer in flyers:
        flyer_merchant = flyer.get("merchant", "").strip()
        flyer_categories = [cat.strip() for cat in flyer.get("categories", [])]

        if flyer_merchant.lower() == merchant_name.lower() and category in flyer_categories:
            flyer_id = flyer.get("id")
            flyer_path = flyer.get("path")
            if flyer_id and flyer_path:
                logger.info(f"Found matching flyer! ID: {flyer_id}, Path: {flyer_path}")
                return str(flyer_id), flyer_path
            else:
                logger.warning(f"Found matching flyer for '{merchant_name}' but missing ID or Path. ID: {flyer_id}, Path: {flyer_path}")

    logger.warning(f"No flyer found for '{merchant_name}' with category '{category}' in postal code '{postal_code}'.")
    return None, None

def _download_single_tile(url: str, target_path: str) -> bool:
    """Downloads a single tile image. Returns True on success, False on failure (especially 404)."""
    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(url, stream=True, timeout=15, headers=headers)
        if response.status_code == 404:
            return False # Explicitly return False for 404
        response.raise_for_status()
        with open(target_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        return True
    except requests.exceptions.RequestException as e:
        if not (isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 404):
             logger.warning(f"Error downloading tile {url}: {e}")
        return False
    except IOError as e:
        logger.error(f"Error saving image tile to {target_path}: {e}")
        return False

def download_and_stitch_flyer_image(flyer_path: str, zoom_level: int = DEFAULT_TILE_ZOOM_LEVEL) -> Image.Image | None:
    """
    Downloads all tiles for a flyer page and stitches them together.
    Returns a PIL Image object or None if an error occurs.
    """
    if not flyer_path:
        logger.error("Invalid flyer path provided for stitching.")
        return None

    logger.info(f"Starting tile discovery for path: {flyer_path} at zoom level {zoom_level}")

    downloaded_tiles = {}  # Dictionary to store { (x, y): temp_path }
    max_x_found = -1
    max_y_found = -1
    tile_width = -1
    tile_height = -1
    found_any_tile = False

    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info(f"Using temporary directory for tiles: {temp_dir}")
        y_coord = 0
        while True:  # Loop through rows (y-coordinate in filename)
            x_coord = 0
            row_found_tile = False
            current_row_max_x = -1
            while True:  # Loop through columns (x-coordinate in filename)
                tile_filename = f"{zoom_level}_{x_coord}_{y_coord}.jpg"
                tile_url = f"{TILE_BASE_URL}{flyer_path}{tile_filename}"
                temp_filepath = os.path.join(temp_dir, f"tile_{x_coord}_{y_coord}.jpg")

                if _download_single_tile(tile_url, temp_filepath):
                    downloaded_tiles[(x_coord, y_coord)] = temp_filepath
                    row_found_tile = True
                    found_any_tile = True
                    current_row_max_x = x_coord
                    if max_y_found < y_coord: max_y_found = y_coord

                    if tile_width == -1:
                        try:
                            with Image.open(temp_filepath) as img:
                                tile_width, tile_height = img.size
                            logger.info(f"Detected tile dimensions: {tile_width}x{tile_height}")
                        except Exception as e:
                            logger.error(f"Error reading dimensions from {temp_filepath}: {e}. Aborting stitch.")
                            return None

                    if DEFAULT_REQUEST_DELAY_S > 0:
                        time.sleep(DEFAULT_REQUEST_DELAY_S)
                    x_coord += 1
                else:
                    break # Stop searching this row (assume end of row)
            
            if row_found_tile:
                if current_row_max_x > max_x_found: max_x_found = current_row_max_x
                y_coord += 1
            else:
                if found_any_tile:
                    logger.info(f"No tiles found for filename y-coordinate {y_coord}. Assuming end of flyer.")
                    break
                else:
                    if y_coord == 0 and x_coord == 0:
                        logger.error(f"Failed to find the very first tile ({zoom_level}_0_0.jpg). Cannot proceed.")
                        return None
                    logger.warning(f"No tiles found for y-coordinate {y_coord}, and no tiles found yet. Continuing search...")
                    y_coord += 1
                    if y_coord > 15: # Safety break for initial empty rows
                        logger.error("Searched too many initial rows without finding tiles. Stopping.")
                        return None

        if not downloaded_tiles or tile_width <= 0 or tile_height <= 0:
            logger.error("No tiles were downloaded or tile dimensions invalid. Cannot stitch.")
            return None

        grid_width_tiles = max_x_found + 1
        grid_height_tiles = max_y_found + 1
        total_pixel_width = grid_width_tiles * tile_width
        total_pixel_height = grid_height_tiles * tile_height

        logger.info(f"Stitching {len(downloaded_tiles)} tiles. Grid: {grid_width_tiles}x{grid_height_tiles} tiles. Canvas: {total_pixel_width}x{total_pixel_height} px.")
        combined_image = Image.new('RGB', (total_pixel_width, total_pixel_height), color='white')

        for (x, y), temp_path in downloaded_tiles.items():
            try:
                with Image.open(temp_path) as tile_img:
                    paste_x = x * tile_width
                    paste_y = (max_y_found - y) * tile_height # Y=0 is bottom row in filename, top in PIL
                    combined_image.paste(tile_img, (paste_x, paste_y))
            except Exception as e:
                logger.error(f"Error opening or pasting tile {temp_path} (filename coords: {x},{y}): {e}")
        
        logger.info("Image stitching complete.")
        return combined_image

async def get_flyer_image_data_and_id(postal_code: str, merchant_name: str, category: str = "Groceries", zoom_level: int = DEFAULT_TILE_ZOOM_LEVEL) -> tuple[str | None, bytes | None]:
    """
    Main function to get flyer ID and its stitched image data as bytes.
    Returns (flipp_flyer_id, image_bytes) or (None, None) on failure.
    """
    flipp_flyer_id, flyer_path = find_flyer_path_from_flipp(postal_code, merchant_name, category)
    if not flyer_path or not flipp_flyer_id:
        logger.warning(f"Could not find flyer path or ID for {merchant_name} in {postal_code}.")
        return None, None

    stitched_image_pil = download_and_stitch_flyer_image(flyer_path, zoom_level)
    if not stitched_image_pil:
        logger.error(f"Failed to download and stitch flyer for {merchant_name}, path {flyer_path}.")
        return None, None

    try:
        img_byte_arr = BytesIO()
        stitched_image_pil.save(img_byte_arr, format='PNG') # Save as PNG
        img_bytes = img_byte_arr.getvalue()
        logger.info(f"Successfully converted stitched image to PNG bytes for flyer ID {flipp_flyer_id}.")
        return flipp_flyer_id, img_bytes
    except Exception as e:
        logger.error(f"Error converting PIL image to bytes: {e}")
        return None, None
    finally:
        if 'stitched_image_pil' in locals() and stitched_image_pil:
            stitched_image_pil.close()
