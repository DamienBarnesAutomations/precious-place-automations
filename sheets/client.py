import os
import gspread
from google.oauth2.service_account import Credentials

# The name of the file containing the service account JSON data.
# This MUST match the 'Filename' you set in Render's Secret Files!
SERVICE_ACCOUNT_FILE = "sheets_key.json"

def get_sheets_client():
    """
    Authenticates with Google Sheets using the Service Account JSON key.
    
    The key file is loaded from the secure location where Render makes it available.
    """
    
    # 1. Define the scopes (permissions) required
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]

    # 2. Check if the secret file exists (it should exist on Render)
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(
            f"Service account file '{SERVICE_ACCOUNT_FILE}' not found. "
            "Ensure it is uploaded as a Secret File on Render with this exact filename."
        )

    # 3. Create credentials object
    credentials = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

    print("✅ SUCCESS: Google Sheets Service Account Key loaded correctly!")
     
    # 4. Return the gspread client object
    return gspread.client.Client(auth=credentials)

# Example usage (you'll use this in your services):
# sheets_client = get_sheets_client()
# spreadsheet = sheets_client.open("Your Bakery Project Spreadsheet Name")
# worksheet = spreadsheet.worksheet("Ingredients")