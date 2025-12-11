from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
import logging
import re


RECIPE_MANAGER_MODE = 3 # Unique integer state for the mode

ADD_RECIPE_REGEX = re.compile(
    r"(?i)^(add|create|new)\s+recipe\s+" # Match starting phrases
    r"(?P<name>.+?)"                     # Capture recipe name (non-greedy)
    r"(?:\s+|\s*\()??"                   # Match space or optional opening parenthesis
    r"(?:yield|batch size)?\s*:\s*"      # Match optional "yield" or "batch size" text
    r"(?P<yield_quantity>\d+(\.\d+)?)\s*"# Capture numeric yield quantity, optional space
    r"(?P<yield_unit>\w+)\s*(\))?$"      # Capture yield unit, optional closing parenthesis
)

# Define the Recipe Management Mode welcome message
RECIPE_MANAGER_WELCOME_MESSAGE = (
    "👩‍🍳 <b>Recipe Manager Mode</b>\n\n"
    "This mode allows you to create, view, and analyze your recipes.\n\n"
    "<b>Available Commands:</b>\n"
    "• <b>Add Recipe:</b> <code>Add recipe Sourdough Loaf (Yield: 2 loaves)</code>\n"
    "• <b>Add Ingredient:</b> <code>To Sourdough Loaf, add 500g Flour</code>\n"
    "• <b>Check Cost:</b> <code>Cost of Sourdough Loaf</code>\n"
    "• <b>Check Capacity:</b> <code>How many loaves of Sourdough can I make?</code>\n"
    "• <b>Show Recipe:</b> <code>Show recipe Sourdough Loaf</code>\n\n"
    "Type <code>STOP</code> to exit this mode."
)

ADD_INGREDIENT_REGEX = re.compile(
    r"(?i)^(?:to|for)\s+"                   # Match starting preposition (To / For)
    r"(?P<recipe_name>.+?),"                # Capture recipe name (non-greedy)
    r"(?:\s*add|\s*require|\s*use)\s*"      # Match action verb (add/require/use)
    r"(?P<required_quantity>\d+(\.\d+)?)\s*"# Capture numeric quantity (optional space)
    r"(?P<required_unit>\w+)\s+"            # Capture unit (mandatory space)
    r"(?P<ingredient_name>.+?)$"            # Capture ingredient name
)

async def start_recipe_manager_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Starts the Recipe Manager Mode conversation and sends the welcome message.
    """
    user_id = update.effective_user.username if update.effective_user else None
    logging.info(f"User {user_id} entering Recipe Manager Mode.")
    
    # Send the welcome message using HTML for formatting
    await update.message.reply_html(
        RECIPE_MANAGER_WELCOME_MESSAGE,
        disable_web_page_preview=True
    )
    
    # Return the new conversation state
    return RECIPE_MANAGER_MODE # Return RECIPE_MANAGER_MODE


async def handle_add_new_recipe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handles the ADD RECIPE pattern, extracts data, and calls the service to create the record.
    """
    # 1. Retrieve data from regex match (assuming the match object is available in context.match)
    data = context.match.groupdict()
    
    recipe_name = data.get('name', '').strip()
    yield_unit = data.get('yield_unit', '').strip()

    try:
        yield_quantity = float(data.get('yield_quantity'))
    except (ValueError, TypeError):
        return "❌ Input Error: The yield quantity must be a valid number."
    
    if not recipe_name or not yield_unit:
        return "❌ Input Error: Recipe name and yield unit cannot be empty."

    user_id = update.effective_user.id if update.effective_user else None
    
    logging.info(f"ACTION: Add Recipe detected for '{recipe_name}'.")

    # 2. Call the service function
    success, message = await create_new_recipe(
        name=recipe_name, 
        yield_quantity=yield_quantity, 
        yield_unit=yield_unit, 
        user_id=user_id
    )

    # 3. Reply to the user
    await update.message.reply_html(message)

    # Keep the user in Recipe Manager Mode
    return None # Return None to stay in the current state (RECIPE_MANAGER_MODE)

async def handle_add_ingredient_to_recipe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    """
    Handles the ADD INGREDIENT pattern, extracts data, and calls the service to link the ingredient.
    """
    data = context.match.groupdict()
    
    recipe_name = data.get('recipe_name', '').strip()
    ingredient_name = data.get('ingredient_name', '').strip()
    required_unit = data.get('required_unit', '').strip()

    try:
        required_quantity = float(data.get('required_quantity'))
    except (ValueError, TypeError):
        return "❌ Input Error: The required quantity must be a valid number."
    
    user_id = update.effective_user.id if update.effective_user else None
    
    logging.info(f"ACTION: Add Ingredient to Recipe detected: {recipe_name} -> {required_quantity} {required_unit} {ingredient_name}.")

    # Call the service function
    success, message = await add_recipe_component(
        recipe_name=recipe_name,
        ing_name=ingredient_name,
        req_quantity=required_quantity,
        req_unit=required_unit,
        user_id=user_id
    )

    await update.message.reply_html(message)

    return None # Stay in Recipe Manager Mode
    

RECIPE_MANAGER_MODE_CONVERSATION_HANDLER = ConversationHandler(
    entry_points=[
        MessageHandler(
            filters.Regex(r'(?i)^(Manage Recipes)$') & ~filters.COMMAND, start_recipe_manager_mode
        )
    ],
    states={
        RECIPE_MANAGER_MODE: [
            # Handlers for P7.2.C2, P7.2.C3, P7.3.A1, etc., will go here
            # MessageHandler(filters.TEXT & ~filters.COMMAND, recipe_handler.handle_recipe_input),
            MessageHandler(
                filters.Regex(recipe_handler.ADD_RECIPE_REGEX), 
                recipe_handler.handle_add_new_recipe
            ),
            MessageHandler(
                filters.Regex(recipe_handler.ADD_INGREDIENT_REGEX), 
                recipe_handler.handle_add_ingredient_to_recipe
            ),            
            # Simple STOP handler for now
            MessageHandler(
                filters.Regex(r'(?i)^STOP$'), 
                lambda update, context: ConversationHandler.END
            ),
        ]
    },
    fallbacks=[MessageHandler(filters.Regex(r'(?i)^STOP$'), exit_recipe_manager_mode)],
)