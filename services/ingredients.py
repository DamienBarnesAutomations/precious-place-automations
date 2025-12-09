import uuid
from datetime import datetime
from services import conversion
from sheets import queries # Accesses the sheet read/write functions
import logging

# --- Configuration Constants ---
INGREDIENTS_SHEET = "Ingredients"
PRICE_HISTORY_SHEET = "Price_History"
UNITS_SHEET = "Units"
CONFIG_SHEET = "Config"
NEXT_ING_ID_KEY = "NEXT_ING_ID"
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
PRICE_HISTORY_INGREDIENT_ID - 'ingredients_Id'
OLD_COST_PER_UNIT = 'old_cost_per_unit'
NEW_COST_PER_UNIT = 'new_cost_per_unit'

def get_conversion_rate(from_unit: str, to_unit: str) -> float | None:
    """
    Retrieves the conversion rate between two specified units from the Units table.
    
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
        conversion_rules = queries.get_all_records(UNITS_SHEET)
    except Exception as e:
        logging.error(f"DATABASE READ FAILED: Could not fetch conversion rules from {UNITS_SHEET}. Exception: {e}")
        return None

    # 3. Search for the direct conversion (From -> To)
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

def _get_current_counter_value(key: str) -> int:
    """Retrieves the current integer value of an ID counter from the Config sheet."""
    # Added error handling for database read
    try:
        config_records = queries.get_all_records(CONFIG_SHEET)
    except Exception as e:
        logging.error(f"CONFIG READ FAILED: Could not retrieve config records. Exception: {e}")
        return 0
    
    current_value = 0
    # Search for the specified key
    for record in config_records:
        if record.get('Key') == key:
            # Assumes the value is a string like "ING001". We extract the number.
            try:
                # We skip the first 3 chars ("ING") and convert to integer
                # Added check for minimum length
                value_str = record.get('Value', '000')
                if len(value_str) >= 3:
                    current_value = int(value_str[3:])
            except (ValueError, IndexError):
                # Handle cases where the format might be incorrect or the string is too short
                logging.warning(f"CONFIG DATA ERROR: Invalid format for key '{key}'. Value: '{record.get('Value')}'")
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
        # Replaced print() with logging.error
        logging.error(f"CONFIG WRITE FAILED: Failed to update config key {key}. Exception: {e}")
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
        # Replaced print() with logging.warning and returned a unique ID on failure
        logging.warning("ID UPDATE FAILED: Failed to update sequential ID. Returning UUID fallback.")
        return f"{key_prefix}-{uuid.uuid4().hex[:6].upper()}"


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
        new_id = _generate_and_commit_new_id("ING", NEXT_ING_ID_KEY)
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


def _find_ingredient_by_name(name: str) -> dict | None:
    """
    Utility function to search for an ingredient record by name (case-insensitive).
    
    Returns the full ingredient record (dict) if found, otherwise None.
    """
    logging.debug(f"START LOOKUP: Searching for ingredient by name: '{name}'.")
    
    # Safely retrieve all ingredient records from the database sheet
    try:
        all_ingredients = queries.get_all_records(INGREDIENTS_SHEET)
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


async def update_ingredient_cost_per_unit(ingredient_name: str, new_price: float, user_id: str | int | None = None) -> bool:
    """
    Updates the unit cost of an existing ingredient and logs the price change.
    
    Returns True on success, False on failure (lookup, write, or data error).
    """
    # Log the start of the price update attempt
    logging.info(f"START PRICE UPDATE: Attempting to set cost for '{ingredient_name}' to {new_price} €.")
    
    # 1. Find the existing ingredient record by name
    try:
        # Calls the internal lookup utility (P3.1.F1 equivalent)
        ingredient = await _find_ingredient_by_name(ingredient_name)
    except Exception as e:
        # Catch exception from _find_ingredient_by_name's internal database call
        logging.error(f"DATABASE READ FAILED: Error during lookup for '{ingredient_name}'. Exception: {e}")
        return False

    if not ingredient:
        # Abort if the ingredient is not found
        logging.warning(f"PRICE UPDATE ABORTED: Ingredient name '{ingredient_name}' not found in the sheet.")
        return False
    
    # Safely retrieve the ingredient ID and old price for logging/comparison
    try:
        i_id = ingredient[INGREDIENT_ID]
        # Attempt to cast old price to float, defaulting to 0.0 if conversion fails
        old_price = float(ingredient.get(INGREDIENT_COST_PER_UNIT, 0.0)) 
    except (ValueError, KeyError, TypeError) as e:
        # Log data integrity issue but proceed with update using 0.0 as the old price
        logging.error(f"DATA INTEGRITY ERROR: Cannot read old price for ID {i_id}. Defaulting to 0.0. Exception: {e}")
        old_price = 0.0 
    
    # 2. Update the 'Ingredients' sheet with the new price
    updates = {
        # Format float to string for consistent sheet storage
        INGREDIENT_COST_PER_UNIT: f"{new_price:.4f}" 
    }
    
    # update_row_by_id handles finding the row by ID and updating Last_Updated metadata
    try:
        update_success = queries.update_row_by_id(INGREDIENTS_SHEET, i_id, updates, user_id=user_id)
    except Exception as e:
        # Log a critical failure during the main database write
        logging.error(f"DATABASE WRITE FAILED: Could not update ingredient ID {i_id} in {INGREDIENTS_SHEET}. Exception: {e}")
        update_success = False

    # 3. Log the change to the 'Price_History' sheet only if the main update succeeded
    if update_success:
        # Log successful update to the main table
        logging.info(f"INGREDIENT UPDATE SUCCESS: Updated cost for ID {i_id} from {old_price:.4f} € to {new_price:.4f} €.")
        
        # Call the logging function (P3.1.F5)
        try:
            # FIX: Correctly call the async log_price_history function
            if await log_price_history(i_id, old_price, new_price, user_id):
                # Log successful history logging
                logging.info(f"HISTORY LOG SUCCESS: Price change logged to {PRICE_HISTORY_SHEET}.") 
            else:
                # Log failure if the logging service function returns False
                logging.warning(f"HISTORY LOG FAILED: Failed to log price change for ID {i_id} to {PRICE_HISTORY_SHEET} (log function returned False).")
        except Exception as e:
            # Log an error if the logging API call throws an exception
            logging.error(f"HISTORY LOG EXCEPTION: Failed to log price change for ID {i_id}. Exception: {e}")
    else:
        # Log final failure if the main update failed
        logging.error(f"PRICE UPDATE FAILED: Main database update failed for ID {i_id}.")
    
    # Log the completion and return the success status
    logging.info(f"END PRICE UPDATE: Completed for '{ingredient_name}'. Success: {update_success}")
    return update_success
    
    
        
async def adjust_ingredient_quantity(name: str, new_quantity: float, user_id: str | int | None = None) -> bool:
    """
    Updates the stock quantity of an existing ingredient by replacing the current value.
    
    This function handles straight replacement and does NOT perform stock addition or unit conversion.
    
    Returns True on successful update, False on failure (ingredient not found or DB error).
    """
    logging.info(f"START STOCK REPLACE: Attempting to set stock for '{name}' to {new_quantity:.4f}.")
    
    # 1. Find the existing ingredient record by name
    try:
        existing_record = _find_ingredient_by_name(name)
    except Exception as e:
        logging.error(f"DATABASE READ FAILED: Error during lookup for '{name}'. Exception: {e}")
        return False

    if not existing_record:
        logging.warning(f"STOCK REPLACE ABORTED: Ingredient name '{name}' not found in the sheet.")
        return False 
    
    # Safely retrieve the ingredient ID
    try:
        ingredient_id = existing_record[INGREDIENT_ID]
    except KeyError as e:
        logging.error(f"DATA INTEGRITY ERROR: Missing ID key in record for '{name}'. Exception: {e}")
        return False
    
    # 2. Prepare the update data for the Ingredients sheet
    updates = {
        INGREDIENT_Quantity: f"{new_quantity:.4f}" # Format float for consistent sheet storage
    }
    
    # 3. Commit the change to the database
    # update_row_by_id also handles updating the 'Last_Updated' timestamp automatically (P2.5)
    try:
        update_success = queries.update_row_by_id(INGREDIENTS_SHEET, ingredient_id, updates)
    except Exception as e:
        logging.error(f"DATABASE WRITE FAILED: Could not update stock for ID {ingredient_id}. Exception: {e}")
        return False
    
    if update_success:
        logging.info(f"END STOCK REPLACE: Stock for ID {ingredient_id} successfully replaced with {new_quantity:.4f}.")
    else:
        logging.error(f"DATABASE WRITE FAILED: update_row_by_id returned failure for ID {ingredient_id}.")
    
    return update_success
    
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
        existing_record = _find_ingredient_by_name(name)
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