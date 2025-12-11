from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from services import recipe
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
    logging.info(f"User: {update.effective_user}")
    user_id = update.effective_user.username if update.effective_user else None
    logging.info(f"User {user_id} entering Recipe Manager Mode.")
    context.user_data['mode'] = 'RECIPE_MANAGER'

    
    # Send the welcome message using HTML for formatting
    await update.message.reply_html(
        RECIPE_MANAGER_WELCOME_MESSAGE,
        disable_web_page_preview=True
    )
    
    # Return the new conversation state
    return RECIPE_MANAGER_MODE # Return RECIPE_MANAGER_MODE

async def exit_recipe_manager_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Exits the Recipe Manager Mode conversation flow.
    """
    user_id = update.effective_user.username

    logging.info(f"USER {user_id}: Attempting to exit Recipe Manager Mode.")

    try:
        # 1. Clean up the user data context
        context.user_data.pop('mode', None)
        
        # 2. Send confirmation message
        await update.message.reply_text("👋 Exited Recipe Manager Mode. Commands like `/add` or `/showstock` are available again.")
        
        # 3. Return ConversationHandler.END to terminate the conversation flow
        logging.info(f"USER {user_id}: Successfully exited Recipe Manager Mode.")
        return ConversationHandler.END
        
    except Exception as e:
        logging.error(f"USER {user_id}: ERROR exiting Recipe Manager Mode. Exception: {e}")
        # Even if an error occurs, the mode should terminate to prevent a stuck state
        await update.message.reply_text("⚠️ There was an issue exiting the mode, but the conversation is being terminated anyway.")
        return ConversationHandler.END


async def handle_add_new_recipe(update: Update, data: dict) -> str:
    """
    Handles the ADD RECIPE pattern, extracts data, and calls the service to create the record.
    """
    # 1. Retrieve data from regex match (assuming the match object is available in context.match)
       
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
    success, message = await recipe.create_new_recipe(
        name=recipe_name, 
        yield_quantity=yield_quantity, 
        yield_unit=yield_unit, 
        user_id=user_id
    )

    # 3. Reply to the user
    await update.message.reply_html(message)

    # Keep the user in Recipe Manager Mode
    return RECIPE_MANAGER_MODE # Return None to stay in the current state (RECIPE_MANAGER_MODE)

async def handle_add_ingredient_to_recipe(update: Update, data: dict) -> int:
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
    success, message = await recipe.add_recipe_component(
        recipe_name=recipe_name,
        ing_name=ingredient_name,
        req_quantity=required_quantity,
        req_unit=required_unit,
        user_id=user_id
    )

    await update.message.reply_html(message)

    return RECIPE_MANAGER_MODE # Stay in Recipe Manager Mode
    
async def dispatch_nlp_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    
    user_id = update.effective_user.username
    text = update.message.text.strip()
    reply = ""

    logging.debug(f"USER {user_id} - DISPATCH: Received message '{text}'")

    try:
        # 1. Try to match the BUY/ADD pattern (handles new/existing purchase logic via service)
        if match := ADD_RECIPE_REGEX.match(text):
            reply = await handle_add_new_recipe(update, match.groupdict())

        # 2. Try to match the ADJUST pattern (direct stock replacement)
        elif match := ADD_INGREDIENT_REGEX.match(text):
            # NOTE: Assuming the regex uses named groups 'name', 'quantity', and 'action' (e.g., 'set', 'replace')
            reply = await handle_add_ingredient_to_recipe(update, match.groupdict())
           
        # 5. No match found
        else:
            reply = (
    "🧐 <b>Unrecognized Action.</b> Please use one of the following formats:\n\n"
    "<b>Available Commands:</b>\n"
    
      
    "Type <code>STOP</code> to exit Manager Mode."
    )


    except Exception as e:
        # Catch unexpected errors during regex matching or dispatch
        logging.critical(f"USER {user_id} - CRITICAL DISPATCH ERROR for message '{text}'. Exception: {e}", exc_info=True)
        reply = "💥 A critical system error occurred while processing your request. Please inform the system administrator."

    # Send the final reply
    await update.message.reply_text(reply, parse_mode="HTML")
    
    # Stay in the manager mode state
    return RECIPE_MANAGER_MODE



    

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
            MessageHandler(filters.TEXT & ~filters.COMMAND, dispatch_nlp_action)
           
        ]
    },
    fallbacks=[MessageHandler(filters.Regex(r'(?i)^STOP$'), exit_recipe_manager_mode)],
)