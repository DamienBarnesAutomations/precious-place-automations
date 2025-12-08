# services/conversion.py

from sheets import queries
from gspread.exceptions import WorksheetNotFound
import logging

# Configuration for the sheet containing all unit conversion data
UNITS_SHEET = "Units"
CONVERSION_FACTORS = {} # Cache to store factors: {'unit_name': {'type': 'Weight', 'base': 'g', 'factor': 1000.0}}

async def _load_conversion_factors():
    """Loads all unit conversion records from the Units sheet into an in-memory cache."""
    global CONVERSION_FACTORS
    
    logging.info("Loading unit conversion factors from the Units sheet...")
    try:
        # P2.4: get_all_records() reads the entire sheet
        records = queries.get_all_records(UNITS_SHEET)
        
        # Build the cache
        CONVERSION_FACTORS = {}
        for record in records:
            unit_name = record.get('Unit_Name', '').strip().lower()
            if unit_name:
                try:
                    # Factor_to_Base is how much you multiply the unit by to get the base unit value
                    factor = float(record.get('Factor_to_Base', 1.0))
                    
                    CONVERSION_FACTORS[unit_name] = {
                        'type': record.get('Type', 'Unknown'),
                        'base_unit': record.get('Base_Unit', unit_name).strip().lower(),
                        'factor_to_base': factor
                    }
                except ValueError:
                    logging.warning(f"Skipping unit '{unit_name}': Factor_to_Base is not a valid number.")

        logging.info(f"Successfully loaded {len(CONVERSION_FACTORS)} conversion factors.")

    except WorksheetNotFound:
        logging.error(f"FATAL: Conversion failed. Worksheet '{UNITS_SHEET}' not found. Please confirm P2.7 is done.")
    except Exception as e:
        logging.error(f"Error during conversion factor load: {e}", exc_info=True)


async def convert_unit_to_base(quantity: float, unit_name: str) -> tuple[float, str]:
    """
    Converts a quantity from a given unit to its standardized base unit (e.g., 1 kg -> 1000 g).
    
    Returns a tuple: (base_quantity, base_unit_name)
    """
    # Ensure factors are loaded before use (simple check)
    if not CONVERSION_FACTORS:
        await _load_conversion_factors()
        
    unit_key = unit_name.strip().lower()
    
    if unit_key not in CONVERSION_FACTORS:
        logging.warning(f"Conversion requested for unknown unit: {unit_name}. Returning original quantity/unit.")
        # If the unit is unknown, return the original quantity and unit
        return quantity, unit_key

    factor_data = CONVERSION_FACTORS[unit_key]
    
    base_quantity = quantity * factor_data['factor_to_base']
    base_unit = factor_data['base_unit']
    
    logging.info(f"Converted {quantity} {unit_name} to {base_quantity} {base_unit}.")
    return base_quantity, base_unit


# Ensure factors are loaded at startup (or whenever needed)
# Since the bot is event-driven, we will call _load_conversion_factors() once 
# when the application starts or just before the first conversion.