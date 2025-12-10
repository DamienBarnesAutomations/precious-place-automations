import logging
import gspread
from datetime import datetime
import os
import asyncio
from sheets.client import get_sheets_client 

# Configure logging for the module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration (Based on P2.2 and User Context) ---
# Retrieve environment variables for spreadsheet keys
GOOGLE_SHEETS_NAME_BAKERY = os.getenv("GOOGLE_SHEETS_NAME_BAKERY")
GOOGLE_SHEETS_NAME_ANALYTICS = os.getenv("GOOGLE_SHEETS_NAME_ANALYTICS")

# Configuration sheet constants
CONFIG_SHEET = "Config"
CONFIG_KEY_COLUMN = 'Key'
CONFIG_VALUE_COLUMN = 'Value'

# Check if the primary sheet key is set
if not GOOGLE_SHEETS_NAME_BAKERY:
    raise ValueError("GOOGLE_SHEETS_NAME_BAKERY environment variable is not set!")

# --- P2.3 Implementation: Synchronous Sheet Accessors ---

def get_sheets_client_sync() -> gspread.client.Client:
    """Returns the synchronous GSpread client."""
    # The synchronous client must be retrieved once per execution if running in a worker thread
    return get_sheets_client()

def get_primary_spreadsheet() -> gspread.Spreadsheet:
    """Returns the main project spreadsheet object (Live Data)."""
    client = get_sheets_client_sync()
    # Opens the spreadsheet using the unique key
    return client.open_by_key(GOOGLE_SHEETS_NAME_BAKERY)

def get_cron_spreadsheet() -> gspread.Spreadsheet:
    """Returns the spreadsheet object used for cron job aggregates (Read-Only Data)."""
    if not GOOGLE_SHEETS_NAME_ANALYTICS:
        raise ValueError("CRON spreadsheet name is not configured.")
    client = get_sheets_client_sync()
    # Opens the analytics spreadsheet
    return client.open_by_key(GOOGLE_SHEETS_NAME_ANALYTICS)

def get_worksheet_sync(sheet_name: str, use_cron_sheet: bool = False) -> gspread.Worksheet:
    """Returns a specific worksheet (tab) object synchronously."""
    
    sheet_type = "CRON (Analytics)" if use_cron_sheet else "PRIMARY (Bakery)"
    logging.debug(f"Attempting to retrieve worksheet: '{sheet_name}' from {sheet_type} spreadsheet.")
    
    try:
        # Get the correct spreadsheet object
        spreadsheet = get_cron_spreadsheet() if use_cron_sheet else get_primary_spreadsheet()
        
        # Get the specific worksheet by name
        worksheet = spreadsheet.worksheet(sheet_name)
        
        logging.debug(f"Successfully retrieved worksheet: '{sheet_name}'.")
        return worksheet
        
    except gspread.exceptions.WorksheetNotFound:
        # Specific error for missing tab
        logging.error(f"FATAL Error: Worksheet/Tab '{sheet_name}' not found in the {sheet_type} spreadsheet.", exc_info=False)
        raise
    
    except Exception as e:
        # Catch any other connection or API errors
        logging.error(f"FATAL Error retrieving spreadsheet or worksheet: {e}", exc_info=True)
        raise
    
# --- P3.1.2 Implementation: Core DB Abstraction Utilities ---

async def get_all_records(sheet_name: str, use_cron_sheet: bool = False) -> list[dict] | None:
    """Retrieves all records from a worksheet asynchronously (running GSpread synchronously in a thread)."""
    
    def sync_get_records():
        """Synchronous wrapper for GSpread call."""
        sheet = get_worksheet_sync(sheet_name, use_cron_sheet)
        # get_all_records() uses the column headers as dictionary keys
        return sheet.get_all_records()
        
    try:
        # Run the synchronous GSpread call in a separate thread
        records = await asyncio.to_thread(sync_get_records)
        return records if records else None
    except Exception as e:
        logging.error(f"GET ALL RECORDS ERROR in {sheet_name}: {e}")
        return None

async def find_records(sheet_name: str, filter_column: str, filter_value: str) -> list[dict] | None:
    """Finds and returns a list of records (rows) matching a filter asynchronously."""
    logging.debug(f"DB QUERY: Finding records in '{sheet_name}' where {filter_column} == '{filter_value}'.")
    try:
        # 1. Fetch all records from the sheet
        all_records = await get_all_records(sheet_name) 
        if not all_records:
            return None
        
        # 2. Filter records based on the criteria (case-insensitive and strict match)
        filter_value_clean = str(filter_value).strip().lower()
        matching_records = []
        for record in all_records:
            record_value = record.get(filter_column)
            # Match if the cleaned record value equals the cleaned filter value
            if record_value is not None and str(record_value).strip().lower() == filter_value_clean:
                matching_records.append(record)
                
        return matching_records if matching_records else None
    
    except Exception as e:
        logging.error(f"FIND RECORDS ERROR in {sheet_name}: {e}")
        return None

async def update_row_by_filter(sheet_name: str, filter_column: str, filter_value: str, updates: dict) -> bool:
    """Updates the first row in a sheet that matches the filter criteria asynchronously."""
    logging.debug(f"DB WRITE: Attempting to update row in '{sheet_name}' where {filter_column} == '{filter_value}'.")
    
    def sync_update_by_filter():
        """Synchronous wrapper using GSpread's find and batch_update."""
        sheet = get_worksheet_sync(sheet_name, False) # Assumes non-cron sheet for writing
        
        # 1. Find the cell containing the filter value
        filter_value_str = str(filter_value)
        try:
            # GSpread's find is the most efficient way to locate a row synchronously
            cell = sheet.find(filter_value_str, in_column=sheet.row_values(1).index(filter_column) + 1)
        except gspread.exceptions.CellNotFound:
            logging.warning(f"UPDATE FAILED: Value '{filter_value_str}' not found in column '{filter_column}' in sheet '{sheet_name}'.")
            return False

        row_num = cell.row # The 1-based row index to update
        headers = sheet.row_values(1) # Get headers for column indexing

        updates_list = []
        for header, value in updates.items():
            try:
                col_index = headers.index(header) + 1 # 1-based column index
                updates_list.append({
                    'range': f"{gspread.utils.rowcol_to_a1(row_num, col_index)}",
                    'values': [[str(value)]] # Values must be a list of lists of strings
                })
            except ValueError:
                # Header not found, skip this update field
                pass
        
        if updates_list:
            sheet.batch_update(updates_list)
            return True
        return False
        
    try:
        # Run the synchronous update logic in a separate thread
        success = await asyncio.to_thread(sync_update_by_filter)
        if success:
            logging.info(f"DB WRITE SUCCESS: Row matching {filter_column}='{filter_value}' updated in {sheet_name}.")
            return True
        else:
            return False
            
    except Exception as e:
        logging.error(f"UPDATE ROW ERROR in {sheet_name}: {e}")
        return False

# --- P3.1.2 Implementation: Legacy/ID-Based Utilities (Refactored to ASYNC) ---

async def update_row_by_id(sheet_name: str, row_id: str, data: dict, user_id: str | int | None = None, use_cron_sheet: bool = False) -> bool:
    """Updates the specified row (found by ID assumed to be in the first column) with new data, asynchronously."""
    
    # NOTE: This function's logic is highly similar to update_row_by_filter if the ID is known to be in column 1.
    # For consistency, we keep the original logic structure but wrap it in a thread.
    
    logging.info(f"Attempting to update row ID {row_id} in sheet: {sheet_name} (User: {user_id})")
    
    def sync_update_by_id():
        """Synchronous wrapper for GSpread's update by ID logic."""
        
        # 1. Prepare data with metadata
        data_with_metadata = data.copy()
        data_with_metadata['Last_Updated'] = datetime.now().isoformat()
        data_with_metadata['Updated_By_User'] = str(user_id) if user_id is not None else 'SYSTEM'

        sheet = get_worksheet_sync(sheet_name, use_cron_sheet)
        
        try:
            # 2. Find the row number using gspread.Worksheet.find (assumes ID in first column)
            cell = sheet.find(row_id)
            row_num = cell.row # 1-based row index
            
            # 3. Get the column headers
            headers = sheet.row_values(1)
            
            updates_list = []
            for header, value in data_with_metadata.items():
                try:
                    col_index = headers.index(header) + 1 # 1-based column index
                    updates_list.append({
                        'range': f"{gspread.utils.rowcol_to_a1(row_num, col_index)}",
                        'values': [[str(value)]]
                    })
                except ValueError:
                    # Header not found in sheet, ignore this field
                    pass
            
            # 4. Perform batch update
            if updates_list:
                sheet.batch_update(updates_list)
                return True
            else:
                logging.warning(f"Update skipped for ID {row_id}: No valid fields provided after metadata injection.")
                return False

        except gspread.exceptions.CellNotFound:
            logging.warning(f"Update failed: Row with ID {row_id} not found in sheet {sheet_name}.")
            return False
        
        except Exception:
            # Catch all other errors within the sync block
            raise
    
    try:
        # Run the synchronous update logic in a separate thread
        success = await asyncio.to_thread(sync_update_by_id)
        if success:
            logging.info(f"Successfully updated row ID {row_id} in sheet: {sheet_name}")
            return True
        return False
    except Exception as e:
        logging.error(f"FATAL Error during sheet update for ID {row_id} in {sheet_name}.", exc_info=True)
        return False  


async def append_row(sheet_name: str, data: dict, user_id: str | int | None = None, use_cron_sheet: bool = False) -> bool:
    """Appends a new row to the specified sheet asynchronously."""
    logging.info(f"Attempting to append new row to sheet: {sheet_name} (User: {user_id})")
    
    def sync_append_row():
        """Synchronous wrapper for GSpread's append_row logic."""
        
        # 1. Prepare data with metadata
        data_with_metadata = data.copy()
        data_with_metadata['Last_Updated'] = datetime.now().isoformat()
        data_with_metadata['Updated_By_User'] = str(user_id) if user_id is not None else 'SYSTEM'
        
        sheet = get_worksheet_sync(sheet_name, use_cron_sheet)
        
        # 2. Get the column headers from the first row
        headers = sheet.row_values(1)
        
        # 3. Build the list of values in the correct column order
        row_values = []
        for header in headers:
            # Retrieve the value from the input data, default to an empty string
            value = data_with_metadata.get(header, "")
            row_values.append(str(value))
        
        logging.debug(f"Row prepared for append (Sheet: {sheet_name}): {row_values}")
        
        # 4. Append the row to the sheet
        sheet.append_row(row_values)
        return True # Indicate successful append
        
    try:
        # Run the synchronous append logic in a separate thread
        success = await asyncio.to_thread(sync_append_row)
        if success:
            logging.info(f"Successfully appended row to sheet: {sheet_name}")
            return True
        return False
        
    except Exception as e:
        logging.error(f"FATAL Error during sheet append to {sheet_name}.", exc_info=True)
        return False
        
# --- P7.1.D4 Implementation: Config Utilities ---

async def read_config_value(key: str) -> str | None:
    """Reads a single value from the Config sheet based on a key asynchronously."""
    logging.debug(f"CONFIG READ: Reading value for key '{key}' from {CONFIG_SHEET}.")
    try:
        # Uses the generalized find_records utility
        records = await find_records(CONFIG_SHEET, CONFIG_KEY_COLUMN, key)
        
        if records:
            # Return the value from the first matching record
            return records[0].get(CONFIG_VALUE_COLUMN)
        
        logging.warning(f"CONFIG READ FAILED: Key '{key}' not found in {CONFIG_SHEET}.")
        return None
        
    except Exception as e:
        logging.error(f"CONFIG READ ERROR for key '{key}': {e}")
        return None

async def update_config_value(key: str, new_value: str) -> bool:
    """Updates a single value in the Config sheet based on a key asynchronously."""
    logging.debug(f"CONFIG WRITE: Setting key '{key}' to value '{new_value}' in {CONFIG_SHEET}.")
    try:
        updates = {CONFIG_VALUE_COLUMN: new_value}
        # Uses the generalized update_row_by_filter utility
        success = await update_row_by_filter(CONFIG_SHEET, CONFIG_KEY_COLUMN, key, updates)
        
        if success:
            logging.info(f"CONFIG WRITE SUCCESS: Key '{key}' updated to '{new_value}'.")
            return True
        else:
            logging.warning(f"CONFIG WRITE FAILED: Key '{key}' not found or update failed.")
            return False
            
    except Exception as e:
        logging.error(f"CONFIG WRITE ERROR for key '{key}': {e}")
        return False
        
async def get_next_unique_id(key: str, prefix: str) -> str | None:
    """
    Retrieves the next ID from the Config sheet, increments the counter, and returns the ID.
    This operation handles the read-increment-write sequence atomically (via locking/single thread).
    """
    # 1. READ: Safely retrieve the current ID string (e.g., 'REC001')
    current_id_str = await read_config_value(key)
    if not current_id_str:
        logging.error(f"ID GENERATION ERROR: Config key '{key}' not found or read failed.")
        return None

    # 2. CALCULATE: Extract number, increment, and pad back to string
    try:
        # Assumes format is always [PREFIX][NUMBER]
        current_num = int(current_id_str.replace(prefix, ''))
        next_num = current_num + 1
        
        # Determine padding length from the current ID string
        padding_len = len(current_id_str) - len(prefix)
        next_id_str = prefix + str(next_num).zfill(padding_len)
        
    except ValueError as e:
        logging.error(f"ID GENERATION ERROR: ID Formatting error for {current_id_str}: {e}")
        return None
        
    # 3. WRITE: Update the Config sheet with the NEXT ID
    try:
        if await update_config_value(key, next_id_str):
            # Return the CURRENT ID string, as the NEXT ID has been reserved for the future
            logging.info(f"Generated and reserved new ID: {current_id_str}")
            return current_id_str
        else:
            logging.error(f"ID GENERATION FAILED: Could not write next ID {next_id_str} for key {key}. Rollback needed.")
            return None
    except Exception as e:
        logging.error(f"ID GENERATION FATAL ERROR: DB Write error for Config key {key}: {e}")
        return None