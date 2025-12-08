# services/ingredients.py

import uuid
from datetime import datetime
from sheets import queries 
# NOTE: We need to ensure we import the ConversionService later (P3.1.9)

# --- Configuration Constants ---
INGREDIENTS_SHEET = "Ingredients"
PRICE_HISTORY_SHEET = "Price_History"
CONFIG_SHEET = "Config"
NEXT_ING_ID_KEY = "NEXT_ING_ID"

# --- Utility Functions (Will be developed in P3.1.4) ---

def _get_current_counter_value(key: str) -> int:
    """Retrieves the current integer value of an ID counter from the Config sheet."""
    config_records = queries.get_all_records(CONFIG_SHEET)
    
    current_value = 0
    # Search for the specified key
    for record in config_records:
        if record.get('Key') == key:
            # Assumes the value is a string like "ING001". We extract the number.
            try:
                # We expect the format to be XXXNNN (e.g., ING001), so we skip the first 3 chars
                current_value = int(record.get('Value', '0')[3:])
            except ValueError:
                current_value = 0
            break
    return current_value

def _update_counter_value(key: str, new_value: str) -> bool:
    """Updates the value of an ID counter in the Config sheet."""
    # This function relies on P2.5 (update_row_by_id) which is confirmed done.
    try:
        updates = {"Value": new_value}
        
        # NOTE: We need a simpler way to update the Config sheet that doesn't rely on an 'ID' column,
        # but on the 'Key' column. For now, we assume the 'Key' column is column A, 
        # allowing us to use update_row_by_id directly on the 'Key'.
        return queries.update_row_by_id(CONFIG_SHEET, key, updates)
    except Exception as e:
        print(f"Failed to update config key {key}: {e}")
        return False

# --- Core Service Functions (Placeholders for P3.1.2 onward) ---

async def add_new_ingredient(name: str, stock: float, unit: str, cost: float) -> str:
    """
    Placeholder: Creates a new ingredient record and updates the ID counter.
    """
    # Logic will be implemented in P3.1.4
    return "PlaceholderID"

async def update_ingredient_price(ingredient_id: str, new_price: float) -> bool:
    """
    Placeholder: Updates the price of an existing ingredient and logs the change.
    """
    # Logic will be implemented in P3.1.6
    return True