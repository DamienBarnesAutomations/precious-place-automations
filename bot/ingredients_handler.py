from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from services import ingredients 
import re
from services import conversion
from telegram.helpers import escape_markdown
import logging

# --- Conversation States ---

INGREDIENT_MANAGER_MODE = range(7, 8)[0] # State ID 7


# --- Regular Expressions for NLP Actions  ---

# Regex 1: Handles NEW BUY/ADD
BUY_REGEX = re.compile(
    r"(?i)^(bought|add)\s+"  # Start with "bought" or "add" (case-insensitive)
    r"(?P<quantity>\d+(\.\d+)?)\s+"  # Capture the quantity (e.g., 1 or 1.5)
    r"(?P<unit>\w+)\s+"  # Capture the unit (e.g., kg, L, unit)
    r"(?P<name>.+?)\s+for\s+"  # Capture the ingredient name (non-greedy)
    r"(?:[€$£]\s*)?"  # Optional non-capturing group for currency (€, $, or £), followed by optional space
    r"(?P<cost>\d+(\.\d+)?)$"  # Capture the cost
)

# Regex 2: Handles STOCK ADJUSTMENT 
ADJUSTMENT_REGEX = re.compile(
    r"(?i)^(increase|decrease|adjust)\s+"  # Capture the action (increase/decrease/adjust)
    r"(?P<name>.+?)\s+"  # Capture ingredient name (non-greedy)
    r"(?:quantity|stock)\s+"  # Match "quantity" or "stock" (non-capturing)
    r"by\s+"  # Match the preposition "by"
    r"(?P<quantity>\d+(\.\d+)?)\s*?"  # Capture quantity, and make the trailing space optional (the fix is the \s*?)
    r"(?P<unit>\w+)$"  # Capture the unit
)

# Regex 3: Handles PRICE UPDATE
PRICE_UPDATE_REGEX = PRICE_STATEMENT_REGEX = re.compile(
    r"(?i)^(?P<quantity>\d+(\.\d+)?)\s+"  # Capture quantity (e.g., 1)
    r"(?P<unit>\w+)\s+"  # Capture unit (e.g., kg)
    r"(?P<name>.+?)\s+"  # Capture ingredient name (non-greedy)
    r"(?:is\s+now|now\s+costs)\s+"  # Match the phrase "is now" or "now costs"
    r"(?:[€$£]\s*)?"  # Optional currency symbol (non-capturing)
    r"(?P<cost>\d+(\.\d+)?)$"  # Capture cost
)

SET_STOCK_REGEX = re.compile(
    r"(?i)^(set|reset|change|update)\s+"  # Capture action (set/reset/change/update)
    r"(?P<name>.+?)\s+"  # Capture ingredient name (non-greedy)
    r"(?:quantity|stock)\s+"  # Match "quantity" or "stock" (non-capturing)
    r"to\s+"  # Match the preposition "to"
    r"(?P<quantity>\d+(\.\d+)?)\s+"  # Capture the numeric quantity
    r"(?P<unit>\w+)$"  # Capture the unit
)

# Regex 4: Handles STOCK CHECK
QUANTITY_CHECK_REGEX = re.compile(
    r"(?i)^(what(\'s| is) )?\s*(the\s*)?(stock|quantity)\s+(of|for|for the|of the)\s+(?P<name>.+?)\?*$"
)

async def enter_manager_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Starts the conversation when the user types the entry command.
    Sets the user's state to 'INGREDIENT_MANAGER' and sends the welcome message.
    """
    user_id = update.effective_user.id
    
    logging.info(f"USER {user_id}: Attempting to enter Ingredient Manager Mode.")

    try:
        # 1. Set the user state in user_data
        context.user_data['mode'] = 'INGREDIENT_MANAGER'
        
        # 2. Send the welcome message
        message = (
    "📝 <b>Ingredients Manager Mode</b>\n\n"
    "<b>Available Actions:</b>\n"
    
    "• **Record Purchase / Add Stock:** (Updates stock and cost)\n"
    "  e.g. <b>\"Bought 1 kg Flour for 5\"</b> or <b>\"Add 0.5L Milk for $3.50\"</b>\n\n"
    
    "• **Update Unit Cost:** (Adjusts the ingredient's stored price)\n"
    "  e.g. <b>\"1 kg Flour is now $5\"</b>\n\n"
    
    "• **Check Current Stock:** (Get current inventory level)\n"
    "  e.g. <b>\"What is the stock of Flour?\"</b> or <b>\"Quantity for Eggs\"</b>\n\n"
    
    "• **Set Stock (Absolute):** (Replaces the current stock total)\n"
    "  e.g. <b>\"Set Flour stock to 5 kg\"</b>\n\n"
    
    "• **Adjust Stock (Relative):** (Adds or subtracts from the current total)\n"
    "  e.g. <b>\"Increase Flour stock by 2 kg\"</b> or <b>\"Decrease butter by 100 g\"</b>\n\n"
    
    "Type <code>STOP</code> to exit this mode."
)
        await update.message.reply_text(
            message,
            parse_mode="HTML"
        )
        
        # 3. Return the next state for ConversationHandler
        logging.info(f"USER {user_id}: Successfully entered Ingredient Manager Mode.")
        return INGREDIENT_MANAGER_MODE

    except Exception as e:
        logging.error(f"USER {user_id}: ERROR entering Ingredient Manager Mode. Exception: {e}")
        # Send an error message to the user before returning ConversationHandler.END
        await update.message.reply_text("❌ An unexpected error occurred while starting the manager mode. Please try again.")
        return ConversationHandler.END


async def exit_manager_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Exits the Ingredient Manager Mode conversation flow.
    """
    user_id = update.effective_user.id

    logging.info(f"USER {user_id}: Attempting to exit Ingredient Manager Mode.")

    try:
        # 1. Clean up the user data context
        context.user_data.pop('mode', None)
        
        # 2. Send confirmation message
        await update.message.reply_text("👋 Exited Ingredient Manager Mode. Commands like `/add` or `/showstock` are available again.")
        
        # 3. Return ConversationHandler.END to terminate the conversation flow
        logging.info(f"USER {user_id}: Successfully exited Ingredient Manager Mode.")
        return ConversationHandler.END
        
    except Exception as e:
        logging.error(f"USER {user_id}: ERROR exiting Ingredient Manager Mode. Exception: {e}")
        # Even if an error occurs, the mode should terminate to prevent a stuck state
        await update.message.reply_text("⚠️ There was an issue exiting the mode, but the conversation is being terminated anyway.")
        return ConversationHandler.END
    
    
async def _handle_purchase_action(update: Update, data: dict, user_id: str | int | None = None) -> str:
    """Handles the BUY/ADD pattern using the process_ingredient_purchase service."""
    name = data['name'].strip()
    
    try:
        quantity = float(data['quantity'])
        unit = data['unit'].strip()
        total_cost = float(data['cost'])
    except (ValueError, KeyError) as e:
        logging.error(f"Purchase data error for '{name}': Invalid quantity/cost format. Exception: {e}")
        return "❌ Input error: Quantity or cost must be a valid number."
    
    logging.info(f"ACTION: Purchase detected for {name} | Qty: {quantity} {unit} | Cost: {total_cost} €")

    # Use the robust service function which handles existing/new ingredient logic
    success, status_message = await ingredients.process_ingredient_purchase(
        name, quantity, unit, total_cost, user_id
    )

    if success:
        if status_message.startswith("NEW_INGREDIENT_ADDED:"):
            new_id = status_message.split(":")[1]
            return f"🎉 **New Ingredient Added**\n\n**ID:** `{new_id}`\n**Name:** {name}\n**Stock:** {quantity} {unit}\n**Cost:** {total_cost:.2f} €"
        else: # STOCK_ADJUSTED or STOCK_ADJUSTED_AND_PRICE_UPDATED
            return f"✅ **Purchase Processed**\n\n**Name:** {name}\n**Status:** {status_message.replace('_', ' ')}."
    else:
        logging.error(f"Purchase failed for '{name}'. Status: {status_message}")
        return f"❌ Purchase failed for '{name}'. Reason: {status_message}. Check logs."


async def _handle_price_update_action(update: Update, data: dict) -> str:
    """
    Handles the PRICE STATEMENT pattern (e.g., '1 kg Flour is now 5')
    and passes necessary data to the service layer.
    """
    # 🔑 Retrieve all relevant fields from the regex match data
    user_input_name = data.get('name', '').strip()
    
    # Retrieve quantity and unit, even if they're discarded by the current service function, 
    # as the new regex requires them for matching.
    input_quantity_str = data.get('quantity')
    input_unit = data.get('unit', '').strip()
    
    # Attempt to safely convert the cost (price)
    try:
        new_price = float(data['cost'])
    except (ValueError, KeyError):
        logging.error(f"Price update data error for '{user_input_name}': Invalid cost format or missing 'cost'.")
        return "❌ Input error: New price must be a valid number."
        
    # Attempt to safely convert the input quantity
    try:
        # NOTE: The current service function (update_ingredient_cost_per_unit) might not use this quantity,
        # but it's passed for potential future logic expansion (e.g., calculating price per stored unit).
        input_quantity = float(input_quantity_str)
    except (ValueError, TypeError):
        logging.error(f"Price update data error for '{user_input_name}': Invalid quantity format or missing 'quantity'.")
        return "❌ Input error: Quantity must be a valid number."

    # Retrieve User ID for auditing
    user_id = update.effective_user.id if update.effective_user else None
        
    logging.info(f"ACTION: Price statement detected for {user_input_name}. Input: {input_quantity} {input_unit} now costs {new_price} € (User: {user_id}).")

    # Call the service function, passing all necessary data, including quantity and unit.
    # The service layer (ingredients.py) is responsible for conversion and final update logic.
    if await ingredients.update_ingredient_cost_per_unit(
        name=user_input_name, 
        input_quantity=input_quantity, 
        input_unit=input_unit, 
        new_price=new_price, 
        user_id=user_id
    ):
        return f"💰 Unit cost updated for **{user_input_name}** to {new_price:.2f} € per {input_unit} (based on input)."
    else:
        logging.error(f"Price update failed for '{user_input_name}'. Ingredient not found or DB error.")
        return f"❌ Failed to update price for {user_input_name}. Ingredient not found or a database error occurred."


async def _handle_stock_check_action(update: Update, data: dict) -> str:
    """Handles the STOCK CHECK pattern (P3.1.7 logic)."""
    user_input_name = data['name'].strip()
    
    logging.info(f"ACTION: Stock check detected for {user_input_name}.")

    # Resolve name to ingredient record using the robust utility
    ingredient_record = ingredients._find_ingredient_by_name(user_input_name)
    
    if not ingredient_record:
        logging.warning(f"Stock check failed: Ingredient '{user_input_name}' not found.")
        return f"❌ Ingredient **{user_input_name}** was not found."

    # Extract required info for the reply
    stock = ingredient_record.get(ingredients.INGREDIENT_Quantity, 'N/A')
    unit = ingredient_record.get(ingredients.INGREDIENT_UNIT, 'N/A')
    
    return (
        f"✅ **Stock for {user_input_name}**:\n\n"
        f"**Current Stock:** {stock} {unit}"
    )
    
async def _handle_stock_set_action(update: Update, data: dict) -> str:
    """
    Handles the SET STOCK pattern (e.g., 'Set Flour stock to 5 kg').
    Passes the input directly to the set_ingredient_stock service function.
    """
    user_input_name = data.get('name', '').strip()
    input_unit = data.get('unit', '').strip()

    # Safely convert quantity
    try:
        input_quantity = float(data['quantity'])
    except (ValueError, KeyError):
        logging.error(f"Stock set data error for '{user_input_name}': Invalid quantity format.")
        return "❌ Input error: The stock quantity must be a valid number."
        
    # Check for negative or zero input (cannot set stock to negative)
    if input_quantity < 0:
        return "❌ Stock value cannot be set to a negative amount."

    user_id = update.effective_user.id if update.effective_user else None
        
    logging.info(f"ACTION: Stock set detected for {user_input_name} to {input_quantity} {input_unit} (User: {user_id}).")

    # Call the service function
    success, message = await ingredients.set_ingredient_stock(
        name=user_input_name, 
        input_quantity=input_quantity, 
        input_unit=input_unit, 
        user_id=user_id
    )
    
    if success:
        # The service returns the final formatted message upon success
        return f"✅ **Stock Set Success!** {message}"
    else:
        # The service returns the error status message upon failure
        logging.error(f"Stock set failed for '{user_input_name}'. Error: {message}")
        return f"❌ Failed to set stock for {user_input_name}. {message}"
        
async def _handle_stock_adjustment_action(update: Update, data: dict) -> str:
    """
    Handles the ADJUST STOCK pattern (e.g., 'Increase Flour stock by 2 kg').
    Passes the action and quantity to the service function for relative adjustment.
    """
    user_input_name = data.get('name', '').strip()
    action = data.get('action', '').strip() # Retrieve the action (increase/decrease/adjust)
    input_unit = data.get('unit', '').strip()

    # Safely convert quantity
    try:
        input_quantity = float(data['quantity'])
    except (ValueError, KeyError):
        logging.error(f"Stock adjustment data error for '{user_input_name}': Invalid quantity format.")
        return "❌ Input error: The adjustment quantity must be a valid number."

    # Check for negative or zero input (the action determines the sign, not the quantity value)
    if input_quantity <= 0:
        return "❌ Input error: The quantity to adjust by must be greater than zero."

    user_id = update.effective_user.id if update.effective_user else None

    logging.info(f"ACTION: Stock adjustment detected for {user_input_name}: {action} by {input_quantity} {input_unit} (User: {user_id}).")

    # Call the service function
    success, message = await ingredients.adjust_ingredient_stock(
        name=user_input_name,
        action=action, # Pass the action directly
        input_quantity=input_quantity,
        input_unit=input_unit,
        user_id=user_id
    )

    if success:
        # The service returns the final formatted message upon success
        return f"✅ **Stock Adjusted!** {message}"
    else:
        # The service returns the error status message upon failure
        logging.error(f"Stock adjustment failed for '{user_input_name}'. Error: {message}")
        return f"❌ Failed to adjust stock for {user_input_name}. {message}"


# --- Main Dispatcher ---

async def dispatch_nlp_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Parses the incoming natural language message and calls the appropriate handler function.
    """
    text = update.message.text.strip()
    user_id = update.effective_user.id
    text = update.message.text.strip()
    reply = ""

    logging.debug(f"USER {user_id} - DISPATCH: Received message '{text}'")

    try:
        # 1. Try to match the BUY/ADD pattern (handles new/existing purchase logic via service)
        if match := BUY_REGEX.match(text):
            reply = await _handle_purchase_action(update, match.groupdict(), user_id)

        # 2. Try to match the ADJUST pattern (direct stock replacement)
        elif match := ADJUSTMENT_REGEX.match(text):
            # NOTE: Assuming the regex uses named groups 'name', 'quantity', and 'action' (e.g., 'set', 'replace')
            reply = await _handle_stock_adjustment_action(update, match.groupdict())

        # 3. Try to match the PRICE UPDATE pattern
        elif match := PRICE_UPDATE_REGEX.match(text):
            reply = await _handle_price_update_action(update, match.groupdict())
            
        # 4. Try to match the STOCK CHECK pattern
        elif match := QUANTITY_CHECK_REGEX.match(text):
            reply = await _handle_stock_check_action(update, match.groupdict())
            
        elif match := SET_STOCK_REGEX.match(text):
            reply = await _handle_stock_set_action(update, match.groupdict())
            
        # 5. No match found
        else:
            reply = (
    "🧐 <b>Unrecognized Action.</b> Please use one of the following formats:\n\n"
    "<b>Available Commands:</b>\n"
    
    "• **Record Purchase:** <code>Bought 1 kg Flour for 5</code>\n"
    "  (Also updates stock and cost.)\n\n"
    
    "• **Check Stock:** <code>What is the stock of Flour?</code>\n"
    "  (Or similar natural questions like 'Quantity for Eggs?')\n\n"
    
    "• **Set Stock (Absolute):** <code>Set Flour stock to 5 kg</code>\n"
    "  (Replaces the current stock total.)\n\n"
    
    "• **Adjust Stock (Relative):** <code>Increase Flour stock by 2 kg</code>\n"
    "  (Also works with 'decrease' or 'adjust'.)\n\n"
    
    "Type <code>STOP</code> to exit Manager Mode."
)


    except Exception as e:
        # Catch unexpected errors during regex matching or dispatch
        logging.critical(f"USER {user_id} - CRITICAL DISPATCH ERROR for message '{text}'. Exception: {e}", exc_info=True)
        reply = "💥 A critical system error occurred while processing your request. Please inform the system administrator."

    # Send the final reply
    await update.message.reply_text(reply, parse_mode="HTML")
    
    # Stay in the manager mode state
    return INGREDIENT_MANAGER_MODE

INGREDIENTS_MANAGER_MODE_CONVERSATION_HANDLER = ConversationHandler(
    entry_points=[
        MessageHandler(
            filters.Regex(r'(?i)^(Manage Ingredients)$') & ~filters.COMMAND, 
            enter_manager_mode
        )
    ],
    
    states={
        # P3.1.R2 will implement the dispatcher function that handles NLP here
        INGREDIENT_MANAGER_MODE: [
            
            MessageHandler(filters.TEXT & ~filters.COMMAND, dispatch_nlp_action)
        ],
    },
    
    # We use a specific keyword 'STOP' to leave the mode
    fallbacks=[MessageHandler(filters.Regex(r'(?i)^STOP$'), exit_manager_mode)],
)