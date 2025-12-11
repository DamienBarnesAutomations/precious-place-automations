import uuid
from datetime import datetime
from sheets import queries # Accesses the sheet read/write functions
import logging

# --- Configuration Constants ---
INGREDIENTS_SHEET = "Ingredients"
PRICE_HISTORY_SHEET = "Price_History"
UNITS_SHEET = "Units"
NEXT_ING_ID_KEY = "NEXT_ING_ID"
ID_PREFIX = "ING"
PRICE_HISTORY_SHEET = "Price_History"

#INGREDIENTS TABLE COLUMNS
INGREDIENT_ID = 'ID'
INGREDIENT_NAME = 'Name'
INGREDIENT_UNIT = 'Unit'
INGREDIENT_Quantity = 'Quantity'
INGREDIENT_COST_PER_UNIT = 'Cost Per Unit'

#UNITS TABLE COLUMNS
UNITS_FROM_UNIT = 'From_Unit'
UNITS_To_Unit = 'To_Unit'
UNITS_Conversion_Rate = 'Conversion_Rate'

#PRICE HISTORY TABLE COLUMNS
PRICE_HISTORY_INGREDIENT_ID = 'ingredients_Id'
OLD_COST_PER_UNIT = 'old_cost_per_unit'
NEW_COST_PER_UNIT = 'new_cost_per_unit'

async def get_conversion_rate(from_unit: str, to_unit: str) -> float | None:
    """
    Retrieves the conversion rate between two specified units from the Units table (asynchronously).
    
    If no direct conversion is found, it attempts the reverse conversion.
    
    Returns the rate (float) if found, otherwise None.
    """
    logging.debug(f"START CONVERSION LOOKUP: Checking rate from '{from_unit}' to '{to_unit}'.")
    
    # 1. Standardize inputs
    from_unit_clean = from_unit.strip().lower()
    to_unit_clean = to_unit.strip().lower()
    
    # Check for same unit identity (rate is 1.0)
    if from_unit_clean == to_unit_clean:
        logging.debug("UNIT MATCH: Units are identical, returning rate 1.0.")
        return 1.0

    # 2. Get all conversion rules from the database (UNITS_SHEET)
    try:
        # Await the asynchronous query function
        conversion_rules = await queries.get_all_records(UNITS_SHEET) 
    except Exception as e:
        logging.error(f"DATABASE READ FAILED: Could not fetch conversion rules from {UNITS_SHEET}. Exception: {e}")
        return None

    # 3. Search for the direct conversion (From -> To)
    # ... (Rest of your existing logic for finding direct conversion remains the same) ...
    for rule in conversion_rules:
        # Data integrity check: Ensure all required columns exist in the record
        if all(key in rule for key in [UNITS_FROM_UNIT, UNITS_To_Unit, UNITS_Conversion_Rate]):
            rule_from = rule[UNITS_FROM_UNIT].strip().lower()
            rule_to = rule[UNITS_To_Unit].strip().lower()

            if rule_from == from_unit_clean and rule_to == to_unit_clean:
                try:
                    # Safely convert the rate to a float
                    rate = float(rule[UNITS_Conversion_Rate])
                    logging.info(f"DIRECT RATE FOUND: {rule_from} -> {rule_to} = {rate}.")
                    return rate
                except ValueError:
                    # Handle cases where the rate value in the sheet is not a valid number
                    logging.warning(f"DATA INTEGRITY WARNING: Invalid rate value found for {rule_from} to {rule_to}. Skipping record.")
                    continue

    # 4. Search for the reverse conversion (To -> From) and calculate the inverse rate
    # ... (Rest of your existing logic for finding inverse conversion remains the same) ...
    for rule in conversion_rules:
        if all(key in rule for key in [UNITS_FROM_UNIT, UNITS_To_Unit, UNITS_Conversion_Rate]):
            rule_from = rule[UNITS_FROM_UNIT].strip().lower()
            rule_to = rule[UNITS_To_Unit].strip().lower()

            # Reverse check: Find rule where the TO unit is the rule's FROM and the FROM unit is the rule's TO
            if rule_from == to_unit_clean and rule_to == from_unit_clean:
                try:
                    direct_rate = float(rule[UNITS_Conversion_Rate])
                    if direct_rate == 0:
                        raise ZeroDivisionError("Rate is zero.")
                        
                    # Calculate inverse rate: 1 / (Direct Rate)
                    inverse_rate = 1.0 / direct_rate
                    logging.info(f"INVERSE RATE FOUND: {rule_from} -> {rule_to} rule used. Calculated inverse rate is {inverse_rate}.")
                    return inverse_rate
                except (ValueError, ZeroDivisionError) as e:
                    # Handle invalid number format or division by zero
                    logging.warning(f"DATA INTEGRITY WARNING: Invalid or zero rate found for reverse lookup ({rule_from} to {rule_to}). Exception: {e}")
                    continue
                    
    # 5. No conversion rule found
    logging.warning(f"RATE NOT FOUND: No conversion rule found between {from_unit_clean} and {to_unit_clean}.")
    return None


# --- Core Service Functions ---

async def log_price_history(ingredient_id: str, old_cost_per_unit: float, new_cost_per_unit: float, user_id: str | int | None = None) -> bool:
    # Log the start of the history logging operation
    logging.info(f"START LOGGING: Price history for ID: {ingredient_id}. Old: {old_cost_per_unit:.4f}, New: {new_cost_per_unit:.4f}")

    try:
        # Prepare the data dictionary using the specified column names
        log_data = {
            # Use the ingredient ID passed to the function
            PRICE_HISTORY_INGREDIENT_ID: ingredient_id,
            # Format the old cost to 4 decimal places for consistency
            OLD_COST_PER_UNIT: f"{old_cost_per_unit:.4f}",
            # Format the new cost to 4 decimal places for consistency
            NEW_COST_PER_UNIT: f"{new_cost_per_unit:.4f}",
        }
        
        # Append the row to the Price_History sheet. 
        # queries.append_row automatically injects Timestamp and User_ID.
        success = queries.append_row(PRICE_HISTORY_SHEET, log_data, user_id=user_id)

        if success:
            # Log successful completion
            logging.info(f"SUCCESS LOGGING: Price history appended for ID: {ingredient_id}.")
            return True
        else:
            # Log failure if the lower-level append_row function returns False
            logging.error(f"DATABASE WRITE FAILED: queries.append_row returned False for ID: {ingredient_id}.")
            return False

    except Exception as e:
        # Catch any other unexpected exceptions (e.g., network issues, data formatting)
        logging.error(f"UNEXPECTED ERROR: Failed to log price history for ID {ingredient_id}.", exc_info=True)
        return False

async def get_ingredient_id_by_name(name: str) -> str | None:
    """
    Searches the Ingredients sheet for an ingredient by name (case-insensitive).
    
    Returns the Ingredient ID (e.g., 'ING001') if found, otherwise returns None.
    """
    search_name = name.strip().lower()
    logging.info(f"Searching for ingredient by name: '{search_name}'")
    
    # 1. Get all ingredient records
    # P2.4: Use the existing queries function
    all_ingredients = queries.get_all_records(INGREDIENTS_SHEET)
    
    # 2. Search for the specific ingredient by name
    # We iterate and compare the lowercased name from the sheet
    current_record = next(
        (i for i in all_ingredients if i[INGREDIENT_NAME].strip().lower() == search_name),
        None
    )
    
    if current_record:
        ingredient_id = current_record[INGREDIENT_ID]
        logging.info(f"Match found for '{search_name}': ID is {ingredient_id}")
        return ingredient_id
    else:
        logging.warning(f"No match found for ingredient name: '{search_name}'")
        return None

async def add_new_ingredient(name: str, stock: float, unit: str, cost: float, user_id: str | int | None = None) -> str:
    """
    Creates a new ingredient record in the Ingredients sheet after generating an ID.
    
    Returns the new ID on success or 'ERROR_SAVE_FAILED' on failure.
    """
    logging.info(f"START ADD: Attempting to add new ingredient '{name}' with cost {cost} €.")
    
    # 1. Generate and commit the new sequential ID (P3.1.4)
    try:
        # Generate the next available sequential ID (e.g., ING001)
        new_id = queries.get_next_unique_id(NEXT_ING_ID_KEY, ID_PREFIX)
        if not new_id:
            logging.error("ID GENERATION FAILED: _generate_and_commit_new_id returned empty string.")
            return "ERROR_SAVE_FAILED"
    except Exception as e:
        logging.error(f"ID GENERATION FAILED: Exception during ID generation/commit. Exception: {e}")
        return "ERROR_SAVE_FAILED"
    
    # 2. Prepare the data row (matching sheet headers)
    # Ensure all values are safely converted and formatted
    try:
        new_ingredient_data = {
            INGREDIENT_ID: new_id,
            INGREDIENT_NAME: name,
            INGREDIENT_Quantity: f"{stock:.4f}", # Format floats for consistent sheet storage
            INGREDIENT_UNIT: unit,
            INGREDIENT_COST_PER_UNIT: f"{cost:.4f}", # Use the calculated unit cost
            
        }
        logging.debug(f"Prepared data for new ingredient {new_id}: {new_ingredient_data}")
        
    except Exception as e:
        logging.error(f"DATA PREPARATION FAILED: Error creating data dict for '{name}'. Exception: {e}")
        return "ERROR_SAVE_FAILED"


    # 3. Append the data to the Ingredients sheet (P2.6)
    try:
        if queries.append_row(INGREDIENTS_SHEET, new_ingredient_data, user_id):
            logging.info(f"END ADD: Successfully added new ingredient with ID: {new_id}.")
            return new_id
        else:
            # append_row returned False (e.g., API failure)
            logging.error(f"DATABASE WRITE FAILED: append_row returned failure for ID {new_id}.")
            return "ERROR_SAVE_FAILED"
    except Exception as e:
        # Catch unexpected exceptions during the API call
        logging.error(f"DATABASE WRITE EXCEPTION: Failed to append ingredient {new_id}. Exception: {e}")
        return "ERROR_SAVE_FAILED"


async def _find_ingredient_by_name(name: str) -> dict | None:
    """
    Utility function to search for an ingredient record by name (case-insensitive).
    
    Returns the full ingredient record (dict) if found, otherwise None.
    """
    logging.debug(f"START LOOKUP: Searching for ingredient by name: '{name}'.")
    
    # Safely retrieve all ingredient records from the database sheet
    try:
        all_ingredients = await queries.get_all_records(INGREDIENTS_SHEET)
    except Exception as e:
        logging.error(f"DATABASE READ FAILED: Could not retrieve all records from {INGREDIENTS_SHEET}. Exception: {e}")
        return None
        
    # Clean and lowercase the input name once for efficient comparison
    clean_search_name = name.strip().lower()
    
    # Iterate through records to find a case-insensitive match
    for record in all_ingredients:
        # Check if the required name column exists in the record
        logging.info(f"LOOKUP SUCCESS: Found ingredient '{record}'.")
        if INGREDIENT_NAME in record:
            # Clean and lowercase the name from the sheet for comparison
            record_name = record[INGREDIENT_NAME].strip().lower()
            
            if record_name == clean_search_name:
                logging.info(f"LOOKUP SUCCESS: Found ingredient '{name}' with ID {record.get(INGREDIENT_ID, 'N/A')}.")
                return record
        else:
            # Log a warning if a record is missing the required name column
            logging.warning(f"DATA INTEGRITY WARNING: Found record missing the '{INGREDIENT_NAME}' column.")
            
    # If the loop finishes without finding a match
    logging.info(f"LOOKUP COMPLETE: Ingredient with name '{name}' not found.")
    return None
    
async def calculate_converted_quantity(input_quantity: float, input_unit: str, target_unit: str) -> float | None:
    """
    Calculates the quantity equivalent of input_quantity in the target_unit.
    Returns the converted float quantity or None if conversion fails.
    """
    input_unit = input_unit.strip().lower()
    target_unit = target_unit.strip().lower()

    if input_unit == target_unit:
        return input_quantity
    
    try:
        # Assumes get_conversion_rate exists and returns (Input Unit -> Target Unit) rate
        # e.g., get_conversion_rate('kg', 'g') returns 1000
        rate = await get_conversion_rate(input_unit, target_unit) 
        
        if rate is None:
            logging.error(f"CONVERSION FAILED: No rate found between {input_unit} and {target_unit}.")
            return None

        converted_quantity = input_quantity * rate
        logging.info(f"CONVERSION SUCCESS: Rate {rate} applied. {input_quantity} {input_unit} -> {converted_quantity:.4f} {target_unit}.")
        return converted_quantity

    except Exception as e:
        logging.error(f"FATAL CONVERSION ERROR: {e}", exc_info=True)
        return None
        
async def atomic_combined_update(name: str, stock_qty_input: float, stock_unit_input: str, price_cost_input: float, user_id: str | int | None = None
) -> tuple[bool, str]:
    """
    Updates both stock and cost of an ingredient in a single database call (atomic).
    """
    logging.info(f"START ATOMIC UPDATE: Ing:{name}, Stock:{stock_qty_input} {stock_unit_input}, Cost:{price_cost_input} €.")

    # 1. Find the existing ingredient record
    ingredient_record = await _find_ingredient_by_name(name) 
    if not ingredient_record:
        return False, f"❌ Ingredient **{name}** not found. Cannot update."
    
    i_id = ingredient_record.get(INGREDIENT_ID)
    current_unit = ingredient_record.get(INGREDIENT_UNIT)
    old_price = float(ingredient_record.get(INGREDIENT_COST_PER_UNIT, 0.0))

    # --- 2. Calculate New Stock Quantity ---
    new_stock_qty = await calculate_converted_quantity(stock_qty_input, stock_unit_input, current_unit)
    if new_stock_qty is None:
        return False, f"❌ Stock Conversion Failed: Could not convert {stock_unit_input} for stock update."

    # --- 3. Calculate New Cost Per Stored Unit ---
    # Convert input quantity to stored units to calculate the new price per base unit
    total_purchased_units_stored = await calculate_converted_quantity(stock_qty_input, stock_unit_input, current_unit)
    if total_purchased_units_stored is None or total_purchased_units_stored == 0:
        return False, f"❌ Price Conversion Failed: Could not calculate unit cost (conversion error or zero quantity)."

    new_cost_per_stored_unit = price_cost_input / total_purchased_units_stored

    # --- 4. Prepare Atomic Update Data ---
    updates = {
        STOCK_QUANTITY_KEY: f"{new_stock_qty:.4f}",
        INGREDIENT_COST_PER_UNIT: f"{new_cost_per_stored_unit:.4f}"
    }

    # --- 5. Execute Single Atomic Update and Log History ---
    
    update_success = False
    try:
        # update_row_by_id performs the single atomic update on the Ingredients Master
        update_success = await queries.update_row_by_id(INGREDIENTS_SHEET, i_id, updates, user_id=user_id)
    except Exception as e:
        logging.error(f"DATABASE WRITE FAILED: Atomic update failed for ID {i_id}. Exception: {e}")

    # 6. Log history only if the atomic update succeeded
    if update_success:
        # Log the change to the Price History sheet
        await log_price_history(i_id, old_price, new_cost_per_stored_unit, user_id)
        # Log the change to the Stock History sheet (assuming this function exists)
        await log_stock_history(i_id, new_stock_qty, stock_unit_input, user_id, "COMBINED_SET") 

        return True, (
            f"✅ **Atomic Update Success for {name}**\n"
            f"📦 Stock set to: `{new_stock_qty:.4f} {current_unit}`\n"
            f"💶 Price set to: `{new_cost_per_stored_unit:.4f} per {current_unit}`"
        )
    else:
        return False, f"❌ Failed to execute atomic combined update for {name}."


async def update_ingredient_cost_per_unit(name: str, input_quantity: float, input_unit: str, new_price: float, user_id: str | int | None = None) -> bool:
    """
    Updates the unit cost of an existing ingredient by first calculating the cost
    per the ingredient's stored unit, and then logging the price change.
    
    Returns True on success, False on failure (lookup, write, or data error).
    """
    logging.info(f"START PRICE UPDATE: Attempting to set cost for '{name}' based on input: {input_quantity} {input_unit} @ {new_price} €.")
    
    # 1. Find the existing ingredient record
    try:
        # Assuming _find_ingredient_by_name is the correct lookup utility
        ingredient = await _find_ingredient_by_name(name)
    except Exception as e:
        logging.error(f"DATABASE READ FAILED: Error during lookup for '{name}'. Exception: {e}")
        return False

    if not ingredient:
        logging.warning(f"PRICE UPDATE ABORTED: Ingredient name '{name}' not found in the sheet.")
        return False
    
    # 2. Safely retrieve necessary ingredient data
    try:
        i_id = ingredient[INGREDIENT_ID]
        current_unit = ingredient[INGREDIENT_UNIT]  # Get the currently stored unit for conversion
        old_price = float(ingredient.get(INGREDIENT_COST_PER_UNIT, 0.0))  
    except (ValueError, KeyError, TypeError) as e:
        logging.error(f"DATA INTEGRITY ERROR: Cannot read ingredient data for ID {i_id}. Exception: {e}")
        old_price = 0.0 

    # --- 3. Calculate the new cost per STORED unit using the utility ---
    
    # 3a. Convert input quantity to stored units to get the total purchased quantity in base unit
    total_purchased_units_stored = await calculate_converted_quantity(input_quantity, input_unit, current_unit)
    
    if total_purchased_units_stored is None or total_purchased_units_stored == 0:
        logging.error(f"PRICE CALCULATION FAILED: Conversion failed or input quantity is zero for ID {i_id}.")
        return False
        
    # 3b. Calculate the final cost per ONE stored unit
    new_cost_per_stored_unit = new_price / total_purchased_units_stored
    logging.info(f"CALCULATION SUCCESS: New cost per {current_unit}: {new_cost_per_stored_unit:.4f} €.")

    # 4. Update the 'Ingredients' sheet with the final calculated price
    updates = {
        INGREDIENT_COST_PER_UNIT: f"{new_cost_per_stored_unit:.4f}" 
    }
    
    try:
        # update_row_by_id handles finding the row by ID and updating metadata
        update_success = await queries.update_row_by_id(INGREDIENTS_SHEET, i_id, updates, user_id=user_id)
    except Exception as e:
        logging.error(f"DATABASE WRITE FAILED: Could not update ingredient ID {i_id}. Exception: {e}")
        update_success = False

    # 5. Log the change to the 'Price_History' sheet only if the main update succeeded
    if update_success:
        logging.info(f"INGREDIENT UPDATE SUCCESS: Updated cost for ID {i_id} from {old_price:.4f} € to {new_cost_per_stored_unit:.4f} €.")
        
        # Call the logging function (P3.1.F5)
        try:
            await log_price_history(i_id, old_price, new_cost_per_stored_unit, user_id)
            logging.info(f"HISTORY LOG SUCCESS: Price change logged.") 
        except Exception as e:
            logging.error(f"HISTORY LOG EXCEPTION: Failed to log price change for ID {i_id}. Exception: {e}")
    else:
        logging.error(f"PRICE UPDATE FAILED: Main database update failed for ID {i_id}.")
        
    logging.info(f"END PRICE UPDATE: Completed for '{name}'. Success: {update_success}")
    return update_success
    
async def set_ingredient_stock(name: str, input_quantity: float, input_unit: str, user_id: str | int | None = None) -> tuple[bool, str]:
    """
    Sets the stock of an existing ingredient to an absolute value, handling unit conversion.
    
    Returns a tuple: (success_bool, status_message).
    """
    logging.info(f"START SET STOCK: Setting stock for '{name}' to {input_quantity} {input_unit} (User: {user_id}).")
    
    # 1. Find the existing ingredient record
    try:
        ingredient = await _find_ingredient_by_name(name)
    except Exception as e:
        logging.error(f"DATABASE READ FAILED: Error during lookup for '{name}'. Exception: {e}")
        return False, "Failed to look up ingredient."

    if not ingredient:
        logging.warning(f"SET STOCK ABORTED: Ingredient '{name}' not found.")
        return False, f"Ingredient '{name}' not found."
    
    # 2. Retrieve necessary data
    try:
        i_id = ingredient[INGREDIENT_ID]
        current_unit = ingredient[INGREDIENT_UNIT]
        current_quantity = float(ingredient.get(INGREDIENT_Quantity, 0.0))
    except (KeyError, ValueError, TypeError) as e:
        logging.error(f"DATA INTEGRITY ERROR: Cannot read required fields for ID {i_id}. Exception: {e}")
        return False, "Database error: Corrupted ingredient data."

    # 3. Calculate the new stock in the STORED unit
    
    # 3a. Check for unit mismatch and perform conversion if needed
    if current_unit.strip().lower() != input_unit.strip().lower():
        logging.info(f"UNIT MISMATCH: Stored unit '{current_unit}' requires conversion from input unit '{input_unit}'.")
        
        try:
            # Get the rate: (Input Unit -> Stored Unit)
            rate = await get_conversion_rate(input_unit, current_unit)
        except Exception as e:
            logging.error(f"CONVERSION SERVICE ERROR: Failed to query units table. Exception: {e}")
            return False, "Error occurred while looking up conversion rate."

        if rate is None:
            logging.error(f"CONVERSION FAILED: No conversion rate found between {input_unit} and {current_unit}. Aborting.")
            return False, f"Unit conversion failed: No rate found between {input_unit} and {current_unit}."
            
        # Convert the input quantity to the stored inventory unit
        new_quantity_in_stored_unit = input_quantity * rate
        logging.info(f"CONVERSION SUCCESS: Converted input Qty: {new_quantity_in_stored_unit:.4f} {current_unit}.")
    else:
        # Units match, no conversion needed
        new_quantity_in_stored_unit = input_quantity
        logging.info("UNIT MATCH: Units are identical. No conversion needed.")

    # 4. Update the 'Ingredients' sheet
    updates = {
        # Set the stock to the calculated absolute value (after conversion)
        INGREDIENT_Quantity: f"{new_quantity_in_stored_unit:.4f}"
    }
    
    try:
        update_success = queries.update_row_by_id(INGREDIENTS_SHEET, i_id, updates, user_id=user_id)
    except Exception as e:
        logging.error(f"DATABASE WRITE FAILED: Could not update ingredient ID {i_id}. Exception: {e}")
        return False, "Failed to save stock update to the ingredient record."

    if update_success:
        logging.info(f"END SET STOCK SUCCESS: Stock for ID {i_id} set from {current_quantity:.4f} {current_unit} to {new_quantity_in_stored_unit:.4f} {current_unit}.")
        return True, f"Stock for **{name}** set to {new_quantity_in_stored_unit:.2f} {current_unit}."
    else:
        logging.error(f"DATABASE WRITE FAILED: Update function returned failure for ID {i_id}.")
        return False, f"Failed to save updates to ingredient '{name}'."
        
async def adjust_ingredient_stock(name: str, action: str, input_quantity: float, input_unit: str, user_id: str | int | None = None) -> tuple[bool, str]:
    """
    Adjusts the stock of an existing ingredient relative to its current value, handling unit conversion.
    
    Returns a tuple: (success_bool, status_message).
    """
    action_clean = action.strip().lower()
    logging.info(f"START ADJUST STOCK: {action_clean} stock for '{name}' by {input_quantity} {input_unit} (User: {user_id}).")
    
    # 1. Find the existing ingredient record
    try:
        ingredient = await _find_ingredient_by_name(name)
    except Exception as e:
        logging.error(f"DATABASE READ FAILED: Error during lookup for '{name}'. Exception: {e}")
        return False, "Failed to look up ingredient."

    if not ingredient:
        logging.warning(f"ADJUST STOCK ABORTED: Ingredient '{name}' not found.")
        return False, f"Ingredient '{name}' not found."
    
    # 2. Retrieve necessary data
    try:
        i_id = ingredient[INGREDIENT_ID]
        current_unit = ingredient[INGREDIENT_UNIT]
        # Get current quantity to calculate the new stock
        current_quantity = float(ingredient.get(INGREDIENT_Quantity, 0.0))
    except (KeyError, ValueError, TypeError) as e:
        logging.error(f"DATA INTEGRITY ERROR: Cannot read required fields for ID {i_id}. Exception: {e}")
        return False, "Database error: Corrupted ingredient data."

    # 3. Calculate the adjustment amount in the STORED unit
    
    # 3a. Convert input quantity to stored unit
    adjustment_amount_in_stored_unit = input_quantity
    
    if current_unit.strip().lower() != input_unit.strip().lower():
        try:
            # Get the rate: (Input Unit -> Stored Unit)
            rate = await get_conversion_rate(input_unit, current_unit)
        except Exception as e:
            logging.error(f"CONVERSION SERVICE ERROR: Failed to query units table. Exception: {e}")
            return False, "Error occurred while looking up conversion rate."

        if rate is None:
            logging.error(f"CONVERSION FAILED: No conversion rate found between {input_unit} and {current_unit}. Aborting.")
            return False, f"Unit conversion failed: No rate found between {input_unit} and {current_unit}."
            
        adjustment_amount_in_stored_unit = input_quantity * rate
        logging.info(f"CONVERSION SUCCESS: Adjusted amount converted to {adjustment_amount_in_stored_unit:.4f} {current_unit}.")
    else:
        logging.info("UNIT MATCH: Adjustment amount used directly.")

    # 4. Apply the adjustment based on the action
    
    if action_clean in ['increase', 'add']:
        new_quantity = current_quantity + adjustment_amount_in_stored_unit
    elif action_clean in ['decrease', 'subtract', 'adjust']:
        new_quantity = current_quantity - adjustment_amount_in_stored_unit
    else:
        logging.error(f"INVALID ACTION: Unknown adjustment action '{action_clean}' provided.")
        return False, f"Invalid stock action: '{action_clean}'. Must be increase or decrease."

    # 5. Check for invalid resulting stock (negative inventory)
    if new_quantity < 0:
        logging.warning(f"ADJUST STOCK ABORTED: Resulting quantity for '{name}' would be negative ({new_quantity:.4f}).")
        return False, "Stock adjustment failed: Resulting quantity cannot be negative."

    # 6. Update the 'Ingredients' sheet
    updates = {
        # Set the stock to the calculated relative value
        INGREDIENT_Quantity: f"{new_quantity:.4f}"
    }
    
    try:
        update_success = queries.update_row_by_id(INGREDIENTS_SHEET, i_id, updates, user_id=user_id)
    except Exception as e:
        logging.error(f"DATABASE WRITE FAILED: Could not update ingredient ID {i_id}. Exception: {e}")
        return False, "Failed to save stock adjustment to the ingredient record."

    if update_success:
        logging.info(f"END ADJUST STOCK SUCCESS: Stock for ID {i_id} changed from {current_quantity:.4f} {current_unit} to {new_quantity:.4f} {current_unit}.")
        return True, f"Stock for **{name}** {action_clean}d to {new_quantity:.2f} {current_unit}."
    else:
        logging.error(f"DATABASE WRITE FAILED: Update function returned failure for ID {i_id}.")
        return False, f"Failed to save updates to ingredient '{name}'."
    
    
        
async def process_ingredient_purchase(name: str, quantity: float, unit: str, total_cost: float, user_id: str | int | None = None) -> tuple[bool, str]:
    """
    Handles a purchase: checks if ingredient exists, adjusts stock/price, or adds new ingredient.
    
    Returns a tuple: (success_bool, status_message).
    """
    # Log the start of the transaction for monitoring, including the user ID
    logging.info(f"START PURCHASE (User: {user_id}): Processing purchase for: {name} | Qty: {quantity} {unit} | Cost: {total_cost} €")

    # 1. Attempt to find the ingredient record by its name
    try:
        # Use internal lookup function (assumed to be synchronous)
        existing_record = await _find_ingredient_by_name(name)
    except Exception as e:
        # Log critical database error during lookup
        logging.error(f"DATABASE ERROR: Failed to lookup ingredient '{name}'. Exception: {e}", exc_info=True)
        return False, "Failed to look up ingredient in the database."
    
    # Calculate the unit cost of the purchased batch
    # This value is used for both new ingredient creation and price comparison.
    try:
        new_unit_cost_batch = total_cost / quantity
    except ZeroDivisionError:
        # Handle case where quantity is zero (cannot calculate unit cost)
        logging.error(f"DATA ERROR: Purchase quantity for '{name}' is zero. Cannot process.")
        return False, "Data error: Purchase quantity must be greater than zero."

    if existing_record:
        # --- Existing Ingredient Flow ---
        logging.info(f"INGREDIENT EXISTS: Found '{name}' with ID {existing_record[INGREDIENT_ID]}")

        try:
            # Safely extract and convert existing inventory values
            ingredient_id = existing_record[INGREDIENT_ID]
            current_unit_cost = float(existing_record[INGREDIENT_COST_PER_UNIT])
            current_quantity = float(existing_record[INGREDIENT_Quantity])
            current_unit = existing_record[INGREDIENT_UNIT]
        except (ValueError, KeyError) as e:
            # Log data integrity issue if required fields are missing or corrupted
            logging.error(f"DATA INTEGRITY ERROR: Corrupted stock or schema for {name}. Exception: {e}")
            return False, "Database error: Stock or cost for this ingredient is invalid."
        
        converted_quantity = quantity 
        updates = {}
        new_price_set = False
        
        # 1a. Check for unit mismatch and perform conversion if needed
        if current_unit.strip().lower() != unit.strip().lower():
            logging.info(f"UNIT MISMATCH: Stored unit '{current_unit}' requires conversion from purchased unit '{unit}'.")
            
            # Query the conversion rate using the service
            try:
                # Assuming get_conversion_rate is an async function
                rate = await get_conversion_rate(unit, current_unit) 
            except Exception as e:
                # Log error if conversion service fails
                logging.error(f"CONVERSION SERVICE ERROR: Failed to query units table. Exception: {e}")
                return False, "Error occurred while looking up conversion rate."

            if rate is None:
                # Log error if conversion rate is not found
                logging.error(f"CONVERSION FAILED: No conversion rate found between {unit} and {current_unit}.")
                return False, f"Unit conversion failed: No rate found between {unit} and {current_unit}."
                
            # Convert the purchased quantity to the stored inventory unit
            converted_quantity = quantity * rate
            logging.info(f"CONVERSION SUCCESS: Converted Qty: {converted_quantity:.4f} {current_unit}.")
        else:
            logging.info("UNIT MATCH: Units are identical. No conversion needed.")

        # --- Stock Update ---
        # Calculate the new total stock quantity
        new_quantity = current_quantity + converted_quantity
        # Format as string for consistent sheet storage
        updates[INGREDIENT_Quantity] = f"{new_quantity:.4f}" 
        
        # --- Price Update Logic (Conditional) ---
        # Calculate the unit cost of the new purchase in the stored unit
        new_unit_cost_per_unit = total_cost / converted_quantity

        # Only update the price if the new batch is more expensive than the current stored cost
        if new_unit_cost_per_unit > current_unit_cost:
            new_price_set = True
            # Format as string for consistent sheet storage
            updates[INGREDIENT_COST_PER_UNIT] = f"{new_unit_cost_per_unit:.4f}"
            
            # Log the price history before the main update (to capture the intent)
            try:
                # FIX: Correctly call the async log_price_history function
                await log_price_history(ingredient_id, current_unit_cost, new_unit_cost_per_unit, user_id)
            except Exception as e:
                # Log error but do not fail the main transaction
                logging.error(f"HISTORY LOG EXCEPTION: Failed to log price change for ID {ingredient_id} prior to update. Exception: {e}")
                
            logging.info(f"PRICE SET: New batch ({new_unit_cost_per_unit:.4f} €) is MORE EXPENSIVE than old ({current_unit_cost:.4f} €). Updating Unit Cost.")
        else:
            logging.info(f"PRICE KEPT: New batch ({new_unit_cost_per_unit:.4f} €) is cheaper or equal. Unit Cost remains unchanged at {current_unit_cost:.4f} €.")
            
        # --- Database Update ---
        # Commit all stock and (if applicable) price changes to the main Ingredients sheet
        try:
            update_success = queries.update_row_by_id(INGREDIENTS_SHEET, ingredient_id, updates, user_id)
        except Exception as e:
            # Log critical failure on the main database write
            logging.error(f"DATABASE UPDATE FAILED: Could not update ingredient ID {ingredient_id}. Exception: {e}")
            return False, "Failed to save updates to the ingredient record."

        if not update_success:
            # Log failure if the lower-level query function returns False
            logging.error(f"DATABASE WRITE FAILED: Update function returned failure for ID {ingredient_id}.")
            return False, f"Failed to save updates to ingredient '{name}'."
            
        status = "STOCK_ADJUSTED_AND_PRICE_UPDATED" if new_price_set else "STOCK_ADJUSTED"
        logging.info(f"END PURCHASE: Adjustment complete for '{name}'. Status: {status}")
        return True, status

    else:
        # --- New Ingredient Flow ---
        logging.info(f"NEW INGREDIENT: Ingredient '{name}' not found. Initiating addition.")
        
        # The unit cost of the purchased batch is the initial unit cost
        initial_unit_cost = new_unit_cost_batch
        
        # Add the new ingredient record (P3.1.4 implementation)
        try:
            # Pass user_id to ensure proper logging in add_new_ingredient
            ingredient_id = await add_new_ingredient(name, quantity, unit, initial_unit_cost, user_id)
        except Exception as e:
            # Log critical failure on the new ingredient addition
            logging.error(f"ADD NEW INGREDIENT FAILED: Could not execute add_new_ingredient for '{name}'. Exception: {e}", exc_info=True)
            return False, "Error occurred while attempting to add new ingredient."
        
        if ingredient_id and ingredient_id != "ERROR_SAVE_FAILED":
            logging.info(f"END PURCHASE: New ingredient added successfully with ID: {ingredient_id}")
            return True, f"NEW_INGREDIENT_ADDED:{ingredient_id}"
        else:
            # Handle the specific save failure status returned by add_new_ingredient
            logging.error(f"DATABASE WRITE FAILED: add_new_ingredient returned failure for '{name}'.")
            return False, f"Failed to add new ingredient '{name}'."

async def revert_last_transaction(user_id: str | int) -> tuple[bool, str]:
    """
    Finds the last transaction logged by the user in Price_History and reverts its effect
    on the Ingredients sheet, if possible.
    
    Returns (success_bool, status_message).
    """
    str_user_id = str(user_id)
    logging.info(f"START ROLLBACK: Attempting to revert last transaction for User: {str_user_id}")
    
    # 1. Find the last relevant transaction logged by this user
    try:
        # P3.1.F4 ensures User_ID is logged in Price_History
        # We need a query that sorts by Timestamp (descending) and filters by User_ID
        all_logs = queries.get_all_records(PRICE_HISTORY_SHEET)
        
        # Filter by User_ID and find the first record (which is the newest by Timestamp column)
        last_log = next(
            (log for log in all_logs if log.get('User_ID') == str_user_id), 
            None
        )
        
    except Exception as e:
        logging.error(f"DATABASE READ FAILED: Could not read Price_History for rollback. Exception: {e}")
        return False, "Database error reading history log."

    if not last_log:
        logging.warning(f"ROLLBACK ABORTED: No recent transaction found for User: {str_user_id}.")
        return False, "No transactions found in your history to delete."

    i_id = last_log.get(INGREDIENT_ID)
    
    # Check if the log is a Stock Adjustment (which impacts the master table)
    # NOTE: Since we don't have an Event_Type, we assume any log implies a purchase/change.
    # We must retrieve the old cost recorded in the log.
    try:
        logged_old_cost = float(last_log.get(OLD_COST_PER_UNIT, 0.0))
        logged_new_cost = float(last_log.get(NEW_COST_PER_UNIT, 0.0))
        
        # We need a way to link the history log to the stock change. 
        # For a simple 'Bought' command, one Price_History log corresponds to one stock change.
        # This implementation requires reading the *entire* Ingredients table to find the current stock
        # and reverse the quantity based on the difference we originally calculated in P3.1.F2.
        
        # --- CRITICAL MISSING DATA ---
        # The Price_History table currently ONLY logs cost changes, not the quantity added/subtracted.
        # To accurately revert stock, we need the: (Quantity_Change, Unit_of_Measure_Purchased)
        # We must update P3.1.F5's log_price_history function *first* to include this data!
        
        logging.critical("ROLLBACK FAILED: Price_History log does not contain QUANTITY CHANGE data required for accurate stock reversal.")
        return False, "System Error: History log is incomplete. Cannot revert stock quantity."

    except (ValueError, KeyError) as e:
        logging.error(f"DATA INTEGRITY ERROR: Corrupted log entry ID {last_log.get('Transaction_ID')}. Exception: {e}")
        return False, "History log entry is corrupted. Cannot revert."
        
async def get_ingredient_status(ingredient_name: str) -> tuple[bool, str]:
    """
    Retrieves and formats the stock and cost status for a given ingredient.

    Returns: (success_bool, status_message)
    """
    logging.info(f"START GET STATUS: {ingredient_name}")

    # 1. Find the Ingredient Record
    # Assuming find_ingredient_by_name uses queries.find_records internally
    ingredient_record = await _find_ingredient_by_name(ingredient_name) 

    if not ingredient_record:
        logging.warning(f"GET STATUS FAILED: Ingredient '{ingredient_name}' not found.")
        return False, f"❌ Ingredient **{ingredient_name}** not found in inventory."
    
    # 2. Extract Data (using assumed constants)
    # Using float(0.0) as default for safety
    name = ingredient_record.get(INGREDIENT_NAME_KEY, "N/A")
    quantity = float(ingredient_record.get(STOCK_QUANTITY_KEY, 0.0))
    unit = ingredient_record.get(UNIT_KEY, "unit")
    last_cost = float(ingredient_record.get(LAST_COST_KEY, 0.0))
    
    # 3. Format the Output
    status_message = (
        f"🔎 **Status Report: {name}**\n\n"
        f"📦 **Current Stock:** `{quantity:.2f} {unit}`\n"
        f"💶 **Last Cost:** `{last_cost:.2f} {unit}` (in Euros, as per memory)\n"
        "\n_Type `Used X [unit] of Y` or `Bought Z [unit] of Y for C` to update._"
    )

    logging.info(f"END GET STATUS SUCCESS: Status retrieved for {name}")
    return True, status_message
    
async def adjust_ingredient_stock(name: str, input_quantity: float, input_unit: str, is_addition: bool, user_id: str | int | None = None) -> tuple[bool, str]:
    """
    Adjusts the stock level of an ingredient by the given quantity (addition or usage).
    """
    action = "ADDITION" if is_addition else "USAGE"
    logging.info(f"START STOCK {action}: Ing:{name}, Qty:{input_quantity} {input_unit}")

    # 1. Find the existing ingredient record
    ingredient_record = await _find_ingredient_by_name(name) 
    if not ingredient_record:
        return False, f"❌ Ingredient **{name}** not found. Cannot adjust stock."
    
    i_id = ingredient_record.get(INGREDIENT_ID)
    current_unit = ingredient_record.get(INGREDIENT_UNIT)
    
    try:
        current_stock = float(ingredient_record.get(STOCK_QUANTITY_KEY, 0.0))
    except ValueError:
        logging.error(f"DATA INTEGRITY ERROR: Current stock is not a number for ID {i_id}")
        return False, f"❌ Data Error: Cannot read current stock for {name}."

    # 2. Calculate the adjustment amount in the ingredient's base unit
    adjustment_in_base = await calculate_converted_quantity(input_quantity, input_unit, current_unit)
    
    if adjustment_in_base is None:
        return False, f"❌ Conversion Failed: Cannot convert {input_unit} to {current_unit} for adjustment."

    # 3. Calculate the new stock level
    if is_addition:
        new_stock = current_stock + adjustment_in_base
    else:
        new_stock = current_stock - adjustment_in_base
        # Optional: Add a check here for negative stock and warn/block if necessary

    # 4. Prepare Atomic Update Data
    updates = {
        STOCK_QUANTITY_KEY: f"{new_stock:.4f}",
    }

    # 5. Execute Single Atomic Update and Log History
    update_success = False
    try:
        update_success = await queries.update_row_by_id(INGREDIENTS_SHEET, i_id, updates, user_id=user_id)
    except Exception as e:
        logging.error(f"DATABASE WRITE FAILED: Stock adjustment failed for ID {i_id}. Exception: {e}")

    # 6. Log history only if the atomic update succeeded
    if update_success:
        # Log the change to the Stock History sheet (assuming this function exists)
        await log_stock_history(i_id, new_stock, input_unit, user_id, action) 

        status_word = "Added" if is_addition else "Used"
        
        return True, (
            f"✅ **Stock Updated for {name}**\n"
            f"{status_word} `{input_quantity:.2f} {input_unit}`. New stock: `{new_stock:.4f} {current_unit}`."
        )
    else:
        return False, f"❌ Failed to execute stock adjustment for {name}."