# services/ingredients.py

import uuid
from datetime import datetime
from sheets import queries # Accesses the sheet read/write functions

# --- Configuration Constants ---
INGREDIENTS_SHEET = "Ingredients"
PRICE_HISTORY_SHEET = "Price_HISTORY"
CONFIG_SHEET = "Config"
NEXT_ING_ID_KEY = "NEXT_ING_ID"

# --- Utility Functions (P3.1.4 Logic) ---

def _get_current_counter_value(key: str) -> int:
    """Retrieves the current integer value of an ID counter from the Config sheet."""
    config_records = queries.get_all_records(CONFIG_SHEET)
    
    current_value = 0
    # Search for the specified key
    for record in config_records:
        if record.get('Key') == key:
            # Assumes the value is a string like "ING001". We extract the number.
            try:
                # We skip the first 3 chars ("ING") and convert to integer
                current_value = int(record.get('Value', '000')[3:])
            except (ValueError, IndexError):
                # Handle cases where the format might be incorrect or the string is too short
                current_value = 0
            break
    return current_value


def _update_counter_value(key: str, new_value: str) -> bool:
    """
    Updates the value of an ID counter in the Config sheet.
    
    This function uses update_row_by_id, relying on the 'Key' being in the first column (ID equivalent).
    """
    try:
        updates = {"Value": new_value}
        # P2.5: Use update_row_by_id to find the key and update the 'Value' column
        return queries.update_row_by_id(CONFIG_SHEET, key, updates)
    except Exception as e:
        print(f"Failed to update config key {key}: {e}")
        return False


def _generate_and_commit_new_id(key_prefix: str, config_key: str) -> str:
    """Handles the transactional logic for generating and committing a new sequential ID."""
    
    # 1. Get the current counter value
    current_id_value = _get_current_counter_value(config_key)
    
    # 2. Calculate the next ID and format it (e.g., ING001)
    next_id_number = current_id_value + 1
    new_formatted_id = f"{key_prefix}{next_id_number:03}"
    
    # 3. Update the Config sheet with the new formatted ID value
    # NOTE: In a real system, steps 1 & 3 must be atomic/transactional.
    if _update_counter_value(config_key, new_formatted_id):
        return new_formatted_id
    else:
        # Fallback: If update fails, generate a safe UUID instead of failing completely.
        print("Warning: Failed to update sequential ID. Using UUID.")
        return f"{key_prefix}-{uuid.uuid4().hex[:6].upper()}"


# --- Core Service Functions ---

async def add_new_ingredient(name: str, stock: float, unit: str, cost: float) -> str:
    """
    Creates a new ingredient record in the Ingredients sheet after generating an ID.
    """
    # 1. Generate and commit the new sequential ID (P3.1.4)
    # Assumes key_prefix is "ING" and the config key is "NEXT_ING_ID"
    new_id = _generate_and_commit_new_id("ING", NEXT_ING_ID_KEY)
    
    # 2. Prepare the data row (matching sheet headers)
    new_ingredient_data = {
        "ID": new_id,
        "Name": name,
        "Current_Stock": stock,
        "Unit_of_Measure": unit,
        "Current_Cost_per_Unit": cost,
        # Last_Updated is handled by the append_row function in the utility layer,
        # but since append_row doesn't manage timestamps automatically (only update_row_by_id does), 
        # we MUST include it here.
        "Last_Updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S") 
    }

    # 3. Append the data to the Ingredients sheet (P2.6)
    if queries.append_row(INGREDIENTS_SHEET, new_ingredient_data):
        return new_id
    else:
        # Log failure and return a generic failure message
        print(f"Failed to append ingredient {new_id} to sheet.")
        return "ERROR_SAVE_FAILED"


# Placeholder for P3.1.6
async def update_ingredient_price(ingredient_id: str, new_price: float) -> bool:
    """Placeholder: Updates the price of an existing ingredient and logs the change."""
    return True