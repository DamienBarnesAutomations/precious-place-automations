from telegram import Update
from telegram.ext import ContextTypes
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


async def handle_add_new_recipe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
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
    

RECIPE_MANAGER_MODE_CONVERSATION_HANDLER = ConversationHandler(
    entry_points=[
        CommandHandler(r'(?i)^(Manage Recipes)$', start_recipe_manager_mode)
    ],
    states={
        RECIPE_MANAGER_MODE: [
            # Handlers for P7.2.C2, P7.2.C3, P7.3.A1, etc., will go here
            # MessageHandler(filters.TEXT & ~filters.COMMAND, recipe_handler.handle_recipe_input),
            MessageHandler(
                filters.Regex(recipe_handler.ADD_RECIPE_REGEX), 
                recipe_handler.handle_add_new_recipe
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