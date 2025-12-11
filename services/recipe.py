# services/recipe.py

from sheets import queries
from typing import Dict, Any, Optional
import logging
from services import ingredients

# Define Sheet and Column Constants (These must be consistent with P7.1.D1)
RECIPES_MASTER_SHEET = 'Recipes'
RECIPE_ID_KEY = 'Recipe_ID'
RECIPE_NAME_KEY = 'Name'
RECIPE_YIELD_KEY = 'Yield'
RECIPE_UNIT_KEY = 'Unit'
RECIPE_IS_ACTIVE_KEY = 'Is_Active'

# Constants for ID generation
RECIPE_ID_CONFIG_KEY = 'NEXT_RECIPE_ID'
RECIPE_ID_PREFIX = 'REC'

MAP_SHEET = 'Recipe_Ingredients_Map'
MAP_ID_CONFIG_KEY = 'NEXT_MAP_ID'
MAP_ID_PREFIX = 'MAP'

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

async def add_recipe_component(recipe_name: str, ing_name: str, req_quantity: float, req_unit: str, user_id: int | str | None = None) -> tuple[bool, str]:
    """
    Links a single ingredient to a recipe and writes the component to the Map sheet.
    """
    logging.info(f"START ADD COMPONENT: Recipe:{recipe_name}, Ing:{ing_name} ({req_quantity} {req_unit})")

    # 1. Find the Recipe_ID
    # We need a utility to find a recipe record by name (which we don't have yet - MUST create)
    recipe_record = await find_recipe_by_name(recipe_name) # *** NEW UTILITY REQUIRED ***

    if not recipe_record:
        return False, f"Recipe **{recipe_name}** not found. Please create the recipe first."
    
    recipe_id = recipe_record.get(RECIPE_ID_KEY) # RECIPE_ID_KEY assumed from P7.2.C2

    # 2. Find the Ingredient_ID
    # Uses the existing utility from Phase 3
    ingredient_record = await ingredients._find_ingredient_by_name(ing_name)

    if not ingredient_record:
        # PENDING ENHANCEMENT: Prompt user to create missing ingredient (P7.2.C3.E)
        return False, f"Ingredient **{ing_name}** not found in your inventory. Please add it first."

    ingredient_id = ingredient_record.get(ingredients.INGREDIENT_ID) # Using existing constant

    # 3. Generate Unique Map_ID
    map_id = await queries.get_next_unique_id(MAP_ID_CONFIG_KEY, MAP_ID_PREFIX)
    if not map_id:
        return False, "Failed to generate unique Map ID."

    # 4. Prepare Data and Append Row
    new_map_data = {
        'Map_ID': map_id,
        'Recipe_ID': recipe_id,
        'Ingredient_ID': ingredient_id,
        'Required_Quantity': f"{req_quantity:.2f}",
        'Required_Unit': req_unit,
    }

    success = await queries.append_row(MAP_SHEET, new_map_data, user_id=user_id)

    if success:
        return True, f"✅ Added **{req_quantity} {req_unit}** of **{ing_name}** to **{recipe_name}**."
    else:
        return False, "Failed to link ingredient to recipe in the database."
        
async def find_recipe_by_name(name: str) -> dict | None:
    """Finds the recipe record in Recipes_Master by name."""
    # Uses the general query utility for finding records
    records = await queries.find_records(RECIPES_MASTER_SHEET, RECIPE_NAME_KEY, name)
    
    # Return the first matching record or None
    return records[0] if records else None