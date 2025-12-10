# bot/recipe_handler.py

from telegram import Update
from telegram.ext import ContextTypes
import logging


RECIPE_MANAGER_MODE = 3 # Unique integer state for the mode

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
    

RECIPE_MANAGER_MODE_CONVERSATION_HANDLER = ConversationHandler(
    entry_points=[
        CommandHandler(r'(?i)^(Manage Recipes)$', start_recipe_manager_mode)
    ],
    states={
        RECIPE_MANAGER_MODE: [
            # Handlers for P7.2.C2, P7.2.C3, P7.3.A1, etc., will go here
            # MessageHandler(filters.TEXT & ~filters.COMMAND, recipe_handler.handle_recipe_input),
            
            # Simple STOP handler for now
            MessageHandler(
                filters.Regex(r'(?i)^STOP$'), 
                lambda update, context: ConversationHandler.END
            ),
        ]
    },
    fallbacks=[MessageHandler(filters.Regex(r'(?i)^STOP$'), exit_recipe_manager_mode)],
)