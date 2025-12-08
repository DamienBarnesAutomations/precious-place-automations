# services/ingredients.py

import uuid
from datetime import datetime
from services import conversion
from sheets import queries # Accesses the sheet read/write functions
import logging

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
        "Quantity": stock,
        "Unit": unit,
        "Cost Per Unit": cost,
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


async def update_ingredient_price(ingredient_id: str, new_price: float) -> bool:
    """
    Updates the price of an existing ingredient and logs the change to Price_History.
    
    Returns True on success, False if the ingredient ID is not found.
    """
    # 1. Find the existing ingredient record to get the OLD price
    
    # NOTE: We use get_all_records() and filter manually for simplicity, 
    # as gspread's find() returns only the cell, not the record dictionary.
    
    all_ingredients = queries.get_all_records(INGREDIENTS_SHEET)
    current_record = next((i for i in all_ingredients if i.get('ID') == ingredient_id), None)
    
    if not current_record:
        # Ingredient ID not found in the sheet
        return False 

    # Safely retrieve the old price, converting it to float
    try:
        old_price = float(current_record.get('Current_Cost_per_Unit', 0.0))
    except (ValueError, TypeError):
        old_price = 0.0
    
    
    # 2. Update the 'Ingredients' sheet with the new price
    updates = {
        "Current_Cost_per_Unit": new_price
    }
    # P2.5: update_row_by_id handles finding the row by ID and updating Last_Updated
    update_success = queries.update_row_by_id(INGREDIENTS_SHEET, ingredient_id, updates)
    
    
    # 3. Log the change to the 'Price_History' sheet
    if update_success:
        price_history_log = {
            "Ingredient_ID": ingredient_id,
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Old_Price": old_price,
            "New_Price": new_price
        }
        # P2.6: Use append_row to add the log record
        queries.append_row(PRICE_HISTORY_SHEET, price_history_log)
        
    return update_success
    
async def get_ingredient_stock(ingredient_id: str) -> dict | None:
    """
    Retrieves the name, current stock, and unit of measure for a given ingredient ID.
    
    Returns a dictionary of the required info or None if the ID is not found.
    """
    # 1. Get all ingredient records
    all_ingredients = queries.get_all_records(INGREDIENTS_SHEET)
    
    # 2. Search for the specific ingredient ID
    current_record = next((i for i in all_ingredients if i.get('ID') == ingredient_id), None)
    
    if not current_record:
        return None 

    # 3. Extract and return the required fields
    try:
        stock_info = {
            "name": current_record.get('Name'),
            # Convert stock to float for accurate display/future calculations
            "stock": float(current_record.get('Current_Stock', 0.0)),
            "unit": current_record.get('Unit_of_Measure')
        }
        return stock_info
    except (ValueError, TypeError) as e:
        # Handle cases where stock might be non-numeric (data integrity issue)
        print(f"Error converting stock value for {ingredient_id}: {e}")
        return None
        
        
async def adjust_ingredient_stock(ingredient_id: str, quantity: float, unit: str) -> bool:
    """
    Adjusts the stock level of an ingredient, converting the input unit to the stored unit.
    
    Returns True on successful update, False if the ingredient is not found or conversion fails.
    """
    logging.info(f"Starting stock adjustment for {ingredient_id}: {quantity} {unit}")
    
    # 1. Get the current ingredient record to find the stored unit and current stock
    all_ingredients = queries.get_all_records(INGREDIENTS_SHEET)
    current_record = next((i for i in all_ingredients if i.get('ID') == ingredient_id), None)
    
    if not current_record:
        logging.warning(f"Stock adjustment failed: Ingredient ID {ingredient_id} not found.")
        return False 
    
    try:
        current_stock = float(current_record.get('Current_Stock', 0.0))
        stored_unit = current_record.get('Unit_of_Measure')
    except (ValueError, TypeError):
        logging.error(f"Stock adjustment failed: Current_Stock value for {ingredient_id} is non-numeric.")
        return False

    # 2. Convert the input quantity to the ingredient's stored unit
    
    # P3.1.9 - Call the ConversionService
    # Note: convert_unit_to_base converts to the BASE unit (e.g., kg or L), 
    # but the ingredient might be stored in a different unit (e.g., grams).
    # A full conversion service should handle conversion between any two known units.
    
    # --- SIMPLIFIED CONVERSION (Requires P3.1.9 Logic) ---
    # For now, we will perform a direct conversion assuming the service is fully implemented
    # and has a utility to convert between arbitrary known units (A -> B).
    
    # Since we only have convert_unit_to_base, we'll implement the full A->B conversion here temporarily
    
    
    # *** TEMPORARY LOGIC PENDING FULL P3.1.9 IMPLEMENTATION ***
    # This logic assumes the conversion service can determine the correct conversion
    
    # Find factor to go from input unit to stored unit
    # In a fully realized P3.1.9, this function would handle the whole conversion graph (Input -> Base -> Stored)
    
    # For now, let's assume a function that returns the quantity in the target unit.
    
    # *** REVERTING TO THE PENDING ARCHITECTURE ***
    
    
    # The simplest path is to ensure ALL ingredients are stored in their BASE unit
    # (e.g., kg or L) to make conversion simple. Let's rely on the service to do the job.
    
    # Convert input quantity to its base unit
    input_base_quantity, input_base_unit = await conversion.convert_unit_to_base(quantity, unit)
    
    # Convert current stock to its base unit
    current_base_stock, current_base_unit = await conversion.convert_unit_to_base(current_stock, stored_unit)

    # CHECK 1: Ensure units are the same type (e.g., cannot add kg to L)
    if input_base_unit != current_base_unit:
        logging.error(f"Conversion mismatch: Cannot adjust {stored_unit} (Base: {current_base_unit}) with {unit} (Base: {input_base_unit}).")
        return False
        
    # Find conversion factor back from base unit to the stored unit (stored_unit)
    # This is the tricky part. We must convert the BASE unit quantity back to the STOCKED unit (e.g., kg to g)
    
    # Since our conversion utility only goes one way (unit -> base), we need to adapt.
    # We will assume a simple division by the Factor_to_Base for the reverse conversion.
    
    try:
        # Get the factor to convert the stored unit TO the base unit
        stored_unit_factor = conversion.CONVERSION_FACTORS[stored_unit.lower()]['factor_to_base']
        
        # Convert the base quantity back to the stored unit
        quantity_in_stored_unit = input_base_quantity / stored_unit_factor
        
    except KeyError:
        logging.error(f"Stored unit '{stored_unit}' not found in conversion factors. Cannot proceed.")
        return False
        
    # 3. Calculate the new stock level
    new_stock = current_stock + quantity_in_stored_unit
    
    # 4. Update the Ingredients sheet
    updates = {
        "Current_Stock": new_stock
    }
    
    update_success = queries.update_row_by_id(INGREDIENTS_SHEET, ingredient_id, updates)
    
    logging.info(f"Stock adjustment complete for {ingredient_id}. Old Stock: {current_stock}, Added: {quantity_in_stored_unit} {stored_unit}, New Stock: {new_stock}")
    
    return update_success