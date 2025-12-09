import logging
import gspread
from datetime import datetime
import os
from sheets.client import get_sheets_client 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration (Based on P2.2) ---
GOOGLE_SHEETS_NAME_BAKERY = os.getenv("GOOGLE_SHEETS_NAME_BAKERY")
GOOGLE_SHEETS_NAME_ANALYTICS = os.getenv("GOOGLE_SHEETS_NAME_ANALYTICS")

print("GOOGLE_SHEETS_NAME_BAKERY", GOOGLE_SHEETS_NAME_BAKERY)
print("GOOGLE_SHEETS_NAME_ANALYTICS", GOOGLE_SHEETS_NAME_ANALYTICS)

if not GOOGLE_SHEETS_NAME_BAKERY:
    raise ValueError("GOOGLE_SHEETS_NAME_BAKERY environment variable is not set!")

# --- P2.3 Implementation: Sheet Accessors ---

def get_primary_spreadsheet() -> gspread.Spreadsheet:
    """Returns the main project spreadsheet object (Live Data)."""
    client = get_sheets_client()
    return client.open_by_key(GOOGLE_SHEETS_NAME_BAKERY)

def get_cron_spreadsheet() -> gspread.Spreadsheet:
    """Returns the spreadsheet object used for cron job aggregates (Read-Only Data)."""
    if not GOOGLE_SHEETS_NAME_ANALYTICS:
        raise ValueError("CRON spreadsheet name is not configured.")
    client = get_sheets_client()
    return client.open_by_key(GOOGLE_SHEETS_NAME_ANALYTICS)

def get_worksheet(sheet_name: str, use_cron_sheet: bool = False) -> gspread.Worksheet:
    """Returns a specific worksheet (tab) object from either the primary or cron sheet."""
    
    sheet_type = "CRON (Analytics)" if use_cron_sheet else "PRIMARY (Bakery)"
    logging.info(f"Attempting to retrieve worksheet: '{sheet_name}' from {sheet_type} spreadsheet.")
    
    try:
        if use_cron_sheet:
            spreadsheet = get_cron_spreadsheet()
        else:
            spreadsheet = get_primary_spreadsheet()
        
        # This line can throw a gspread.exceptions.WorksheetNotFound if the tab name is wrong.
        worksheet = spreadsheet.worksheet(sheet_name)
        
        logging.info(f"Successfully retrieved worksheet: '{sheet_name}'.")
        return worksheet
        
    except gspread.exceptions.WorksheetNotFound:
        logging.error(f"FATAL Error: Worksheet/Tab '{sheet_name}' not found in the {sheet_type} spreadsheet.", exc_info=False)
        # Re-raise the exception so the calling function can handle the failure
        raise
    
    except Exception as e:
        # Catch any other connection or API errors
        logging.error(f"FATAL Error retrieving spreadsheet or worksheet: {e}", exc_info=True)
        raise
    
# sheets/queries.py (Add this after the accessors)

def get_all_records(sheet_name: str, use_cron_sheet: bool = False) -> list[dict]:
    """Retrieves all records from a worksheet, returned as a list of dictionaries."""
    sheet = get_worksheet(sheet_name, use_cron_sheet)
    
    # get_all_records() uses the column headers as dictionary keys
    return sheet.get_all_records()
    
# sheets/queries.py (Add this after get_all_records)

# Helper function to find a row by ID - simpler to put it here for now
def _find_row_index_by_id(sheet: gspread.Worksheet, id_value: str) -> int:
    """Finds the 1-based row index for a given ID."""
    try:
        # Assuming ID is in the first column (A)
        cell = sheet.find(id_value)
        return cell.row
    except gspread.exceptions.CellNotFound:
        raise ValueError(f"ID '{id_value}' not found in sheet.")


def update_row_by_id(sheet_name: str, row_id: str, data: dict, user_id: str | int | None = None, use_cron_sheet: bool = False) -> bool:
    """
    Updates the specified row (found by ID) with the new data dictionary,
    automatically updating the Timestamp and User_ID fields.
    
    The 'data' dictionary maps column headers to new values.
    """
    logging.info(f"Attempting to update row ID {row_id} in sheet: {sheet_name} (User: {user_id})")
    
    # 1. Prepare data with metadata
    data_with_metadata = data.copy()
    data_with_metadata['Last_Updated'] = datetime.now().isoformat() # Use a standard 'Last_Updated' field for edits
    data_with_metadata['Updated_By_User'] = str(user_id) if user_id is not None else 'SYSTEM' # Use a different field name for edits

    sheet = get_worksheet(sheet_name, use_cron_sheet)
    
    try:
        # 2. Get all records to find the row index (inefficient but necessary with gspread)
        # Assumes the first column is the ID column
        all_ids = sheet.col_values(1)
        
        # Find the row number (1-based index)
        # Note: all_ids[0] is the header, so the first data row is at index 1
        row_num = next((i for i, id_val in enumerate(all_ids) if id_val == row_id), -1)
        
        if row_num == -1:
            logging.warning(f"Update failed: Row with ID {row_id} not found in sheet {sheet_name}.")
            return False
            
        row_num += 1 # Convert 0-based index to 1-based row number
        
        # 3. Get the column headers
        headers = sheet.row_values(1)
        
        updates_list = []
        for header, value in data_with_metadata.items():
            try:
                col_index = headers.index(header) + 1 # Convert 0-based index to 1-based column number
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
            logging.info(f"Successfully updated row ID {row_id} in sheet: {sheet_name}")
            return True
        else:
            logging.warning(f"Update skipped for ID {row_id}: No valid fields provided after metadata injection.")
            return False

    except Exception as e:
        logging.error(f"FATAL Error during sheet update for ID {row_id} in {sheet_name}.", exc_info=True)
        return False  


# sheets/queries.py (Add this function)

def append_row(sheet_name: str, data: dict, user_id: str | int | None = None, use_cron_sheet: bool = False) -> bool:
    """
    Appends a new row to the specified sheet, automatically adding Timestamp and User_ID.
    
    The 'data' dictionary must map column headers to values.
    """
    logging.info(f"Attempting to append new row to sheet: {sheet_name} (User: {user_id})")
    
    # 1. Prepare data with metadata
    data_with_metadata = data.copy()
    data_with_metadata['Last_Updated'] = datetime.now().isoformat()
    data_with_metadata['Updated_By_User'] = str(user_id) if user_id is not None else 'SYSTEM'
    
    sheet = get_worksheet(sheet_name, use_cron_sheet)
    
    try:
        # 2. Get the column headers from the first row
        headers = sheet.row_values(1)
        
        # 3. Build the list of values in the correct column order
        row_values = []
        for header in headers:
            # Retrieve the value from the input data, default to an empty string if key is missing
            value = data_with_metadata.get(header, "")
            
            # Append the string representation of the value
            row_values.append(str(value))
        
        logging.debug(f"Row prepared for append (Sheet: {sheet_name}): {row_values}")
        
        # 4. Append the row to the sheet
        sheet.append_row(row_values)
        
        logging.info(f"Successfully appended row to sheet: {sheet_name}")
        return True
    
    except Exception as e:
        logging.error(f"FATAL Error during sheet append to {sheet_name}.", exc_info=True)
        logging.error(f"Failed to append row. Data intended for sheet: {data}. Error: {e}")
        return False