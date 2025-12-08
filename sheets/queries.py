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
    return client.open(GOOGLE_SHEETS_NAME_BAKERY)

def get_cron_spreadsheet() -> gspread.Spreadsheet:
    """Returns the spreadsheet object used for cron job aggregates (Read-Only Data)."""
    if not GOOGLE_SHEETS_NAME_ANALYTICS:
        raise ValueError("CRON spreadsheet name is not configured.")
    client = get_sheets_client()
    return client.open(GOOGLE_SHEETS_NAME_ANALYTICS)

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


def update_row_by_id(sheet_name: str, id_value: str, updates: dict, use_cron_sheet: bool = False) -> bool:
    """
    Updates specific columns in a row identified by ID, including the Last_Updated timestamp.
    """
    sheet = get_worksheet(sheet_name, use_cron_sheet)
    
    try:
        # 1. Find the row number
        row_num = _find_row_index_by_id(sheet, id_value)
        
        # 2. Get all column headers
        headers = sheet.row_values(1)
        
        # 3. Prepare updates, ensuring Last_Updated is included
        updates['Last_Updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cells_to_update = []
        for header, new_value in updates.items():
            if header in headers:
                col_index = headers.index(header) + 1 # Convert 0-based index to 1-based column number
                
                cells_to_update.append(gspread.models.Cell(row_num, col_index, str(new_value)))
        
        # 4. Batch update
        if cells_to_update:
            sheet.update_cells(cells_to_update)
            return True
        return False
        
    except ValueError as e:
        # Re-raise the error if the ID was not found
        raise e
    except Exception as e:
        print(f"Error during sheet update for {id_value}: {e}")
        return False   


# sheets/queries.py (Add this function)

def append_row(sheet_name: str, data: dict, use_cron_sheet: bool = False) -> bool:
    """
    Appends a new row to the specified sheet.
    
    The 'data' dictionary must map column headers to values.
    The values are inserted in the exact order of the sheet's column headers.
    """
    logging.info(f"Attempting to append new row to sheet: {sheet_name} (Cron Sheet: {use_cron_sheet})")
    
    try:
        sheet = get_worksheet(sheet_name, use_cron_sheet)
        
        # 1. Get the column headers from the first row
        headers = sheet.row_values(1)
        
        # 2. Build the list of values in the correct column order
        row_values = []
        for header in headers:
            # Retrieve the value from the input data, default to an empty string if key is missing
            value = data.get(header, "")
            
            # Append the string representation of the value
            row_values.append(str(value))
        
        logging.debug(f"Row prepared for append (Sheet: {sheet_name}): {row_values}")
        
        # 3. Append the row to the sheet
        sheet.append_row(row_values)
        
        logging.info(f"Successfully appended row to sheet: {sheet_name}")
        return True
    
    except Exception as e:
        # Use logging.error for exceptions, providing the traceback information
        logging.error(f"FATAL Error during sheet append to {sheet_name}.", exc_info=True)
        logging.error(f"Failed to append row. Data intended for sheet: {data}. Error: {e}")
        return False