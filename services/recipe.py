# services/recipe.py

from sheets import queries
from typing import Dict, Any, Optional
import logging

# Define Sheet and Column Constants (These must be consistent with P7.1.D1)
RECIPES_MASTER_SHEET = 'Recipes_Master'
RECIPE_ID_KEY = 'Recipe_ID'
RECIPE_NAME_KEY = 'Name'
RECIPE_YIELD_KEY = 'Yield'
RECIPE_UNIT_KEY = 'Unit'
RECIPE_IS_ACTIVE_KEY = 'Is_Active'

# Constants for ID generation
RECIPE_ID_CONFIG_KEY = 'NEXT_RECIPE_ID'
RECIPE_ID_PREFIX = 'REC'

async def create_new_recipe(name: str, yield_quantity: float, yield_unit: str, user_id: int | str | None = None) -> tuple[bool, str]:
    """
    Creates a new entry in the Recipes_Master sheet.

    Returns: (success_bool, status_message)
    """
    logging.info(f"START CREATE RECIPE: {name} (Yield: {yield_quantity} {yield_unit}) initiated by User: {user_id}")

    # 1. Generate Unique Recipe_ID
    recipe_id = await queries.get_next_unique_id(RECIPE_ID_CONFIG_KEY, RECIPE_ID_PREFIX)
    if not recipe_id:
        logging.error("CREATE RECIPE FAILED: Could not generate unique Recipe ID.")
        return False, "Failed to create new recipe ID. Please try again."

    # 2. Prepare Data for Sheet
    new_recipe_data = {
        RECIPE_ID_KEY: recipe_id,
        RECIPE_NAME_KEY: name.strip(),
        RECIPE_YIELD_KEY: f"{yield_quantity:.2f}",
        RECIPE_UNIT_KEY: yield_unit.strip(),
        RECIPE_IS_ACTIVE_KEY: "TRUE" # Default new recipes to active
    }

    # 3. Append Row to Sheet
    try:
        success = await queries.append_row(RECIPES_MASTER_SHEET, new_recipe_data, user_id=user_id)
        
        if success:
            logging.info(f"END CREATE RECIPE SUCCESS: Recipe '{name}' successfully created with ID: {recipe_id}")
            return True, f"✅ Recipe **{name}** added! Yield: {yield_quantity} {yield_unit}. Now add ingredients."
        else:
            # Note: The ID is reserved even if this write fails, preventing duplicates.
            logging.error(f"CREATE RECIPE FAILED: DB write failed for Recipe ID: {recipe_id}.")
            return False, "Failed to save the new recipe to the database."

    except Exception as e:
        logging.error(f"CREATE RECIPE FATAL ERROR for {name}: {e}")
        return False, "An unexpected error occurred while saving the recipe."