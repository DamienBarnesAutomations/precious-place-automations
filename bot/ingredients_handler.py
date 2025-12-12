from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from services import ingredients 
import re
import logging

# --- Conversation States ---

INGREDIENT_MANAGER_MODE = 2 # State ID 7


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
PRICE_UPDATE_REGEX = re.compile(
    r"(?i)^(?P<quantity>\d+(\.\d+)?)\s*?"  # Capture quantity, making trailing space optional (\s*?)
    r"(?P<unit>\w+)\s+"  # Capture unit, followed by a mandatory space before the name
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
    r"(?i)"                                     # Case-insensitive
    r"(\s*^what(\'s| is) )?(\s*the\s*)?"       # Optional: (What is the)
    r"(stock|quantity)\s+"                      # Match: stock or quantity
    r"(of|for|for the|of the)\s+"               # Match: of / for
    r"(?P<name>.+?)\?*$"                        # Capture: Name

    r"|"                                        # OR operator (matches either side)

    r"(\s*^how\s+(much|many)\s+)"               # Match: (How much/many)
    r"(?P<name_q>.+?)\s+"                       # Capture: Name (separate group for safety)
    r"(do\s+i\s+have|is\s+in\s+stock)\?*$"      # Match: do i have / is in stock
)

STATUS_CHECK_REGEX = re.compile(
    r"(?i)"                                     # Case-insensitive
    r"(\s*^(what(\'s| is)|tell me)?\s+)"        # Optional start: (what is / tell me)
    r"(?:the\s+)?(status|info|details|about)\s+" # Match key phrase: status/info/details/about
    r"(?:of|for|on)\s+"                         # Match preposition: of / for / on
    r"(?P<name>.+?)\?*$"                        # Capture: Name, optional trailing question mark
)

COMBINED_UPDATE_REGEX = re.compile(
    r"(?i)"                                     # Case-insensitive
    r"^(?:update\s+)?\s*?"                      # Optional start: (update)
    r"(?P<name>.+?)\s+"                         # Capture ingredient name (non-greedy)
    r"(?:"                                      # START Non-Capturing Group for combined updates
        r"(?:stock|quantity)\s*"                # Match keyword: stock or quantity
        r"(?P<stock_quantity>\d+(\.\d+)?)\s*"   # Capture stock quantity
        r"(?P<stock_unit>\w+)\s*"               # Capture stock unit
        r"(?:and\s+)?\s*"                       # Optional "and"
        r"(?:price|cost)\s*"                    # Match keyword: price or cost
        r"(?:[€$£]\s*)?"                        # Optional currency symbol
        r"(?P<price_cost>\d+(\.\d+)?)"          # Capture the new price
    r"|"                                        # OR (Allow Price then Stock order)
        r"(?:price|cost)\s*"                    # Match keyword: price or cost
        r"(?:[€$£]\s*)?"                        # Optional currency symbol
        r"(?P<price_cost_2>\d+(\.\d+)?)\s*"     # Capture the new price (2)
        r"(?:and\s+)?\s*"                       # Optional "and"
        r"(?:stock|quantity)\s*"                # Match keyword: stock or quantity
        r"(?P<stock_quantity_2>\d+(\.\d+)?)\s*" # Capture stock quantity (2)
        r"(?P<stock_unit_2>\w+)"                # Capture stock unit (2)
    r")$"                                       # END Non-Capturing Group
)

# P3.E3b: CONTEXTUAL STOCK ADDITION
# Examples: "Added 10kg flour", "Put in 5L of milk"
STOCK_ADDITION_REGEX = re.compile(
    r"(?i)"                                     # Case-insensitive
    r"^(?:added|put in|restocked)\s+"           # Match action verb (added/put in/restocked)
    r"(?P<quantity>\d+(\.\d+)?)\s*"             # Capture numeric quantity
    r"(?P<unit>\w+)\s+"                         # Capture unit
    r"(?:of\s+)?(the\s+)?\s*?"                  # Optional: (of) or (of the)
    r"(?P<name>.+?)$"                           # Capture ingredient name
)

BUY_REGEX_MODIFIED = re.compile(
    r"(?i)^(bought|add)\s+"  # Start with "bought" or "add" (case-insensitive)
    r"(?P<quantity>\d+(\.\d+)?)\s*"  # Capture the quantity (e.g., 5)
    r"(?P<unit>\w+)?\s*"  # **MODIFIED: Unit is now optional (?); space is optional (*)**
    r"(?P<name>.+?)\s+for\s+"  # Capture the ingredient name (non-greedy)
    r"(?:[€$£]\s*)?"  # Optional non-capturing group for currency
    r"(?P<cost>\d+(\.\d+)?)$"  # Capture the cost
)

STOCK_USAGE_REGEX_MODIFIED = re.compile(
    r"(?i)"                                       # Case-insensitive
    r"^(?:used|consumed|made with)\s+"            # Match action verb
    r"(?P<quantity>\d+(\.\d+)?)\s*"               # Capture numeric quantity
   
    r"(?P<unit>(?!(of|the)\s+)\w+)?\s*"           # Capture optional unit (unit=="" if 'of' follows)
    
    r"(?:of\s+)?(the\s+)?\s*?"                    # Optional preposition/article group
    r"(?P<name>.+?)$"                             # Capture ingredient name
)

INVENTORY_REPORT_REGEX = re.compile(
    r"(?i)"                                     # Case-insensitive
    r"^(?:show|display|list)\s+(?:my\s+)?(inventory|stock|all)\?*$" # Match show/list/display inventory/stock/all
    r"|"                                        # OR
    r"^(?:full|current)\s+report\?*$"           # Match full/current report
)


STOP_REGEX = re.compile(r'(?i)^STOP$')

INGREDIENTS_MANAGER_WELCOME_MESSAGE = (
    "🥐 <b>Ingredients Inventory Manager</b>\n\n"
    "Welcome! The system is now optimized for **quick, fluid commands**.\n\n"
    
    "--- <b>Quick Actions</b> ---\n\n"
    
    "1. **Check Status:** View Stock, Unit, and Last Cost.\n"
    "   e.g. <code>What is the status of Flour?</code>\n\n"
    
    "2. **Ingredient Usage:** Decrement stock automatically.\n"
    "   e.g. <code>Used 50g of sugar</code> or <code>Consumed 2 eggs</code>\n\n"
    
    "3. **Combined Set:** Update Stock and Price atomically.\n"
    "   e.g. <code>Flour stock 15kg price 1.25</code>\n\n"
    
    "--- <b>Standard Actions</b> ---\n\n"
    
    "4. **Record Purchase (Buy/Add):** Full purchase transaction.\n"
    "   e.g. <code>Bought 1 kg Flour for 5</code>\n\n"
    
    "5. **Set Stock (Absolute):** Override current stock total.\n"
    "   e.g. <code>Set Flour stock to 5 kg</code>\n\n"
    
    "6. **Price Update:** Update cost per base unit.\n"
    "   e.g. <code>1 kg Flour is now 5</code>\n\n"
    
    "7. **Show Inventory:** Shows all Ingredients in Inventory\n"
    "   e.g. <code>Show Inventory</code>\n\n"
    
    "To exit the mode, type <code>STOP</code>."
)

INGREDIENTS_MANAGER_FALLBACK_MESSAGE = (
    "🧐 <b>Unrecognized Action.</b>\n\n"
    "I couldn't match your command to a recognized format. Please try one of the simplified actions below, focusing on the new, fluid commands:\n\n"
    
    "--- <b>Quick Actions (Recommended)</b> ---\n\n"
    
    "1. **Check Status:** View Stock, Unit, and Last Cost.\n"
    "   e.g. <code>What is the status of Flour?</code>\n\n"
    
    "2. **Ingredient Usage:** Decrement stock automatically.\n"
    "   e.g. <code>Used 50g of sugar</code> or <code>Consumed 2 eggs</code>\n\n"
    
    "3. **Combined Set:** Update Stock and Price atomically.\n"
    "   e.g. <code>Flour stock 15kg price 1.25</code>\n\n"
        
    "4. **Record Purchase (Buy/Add):** Full purchase transaction.\n"
    "   e.g. <code>Bought 1 kg Flour for 5</code>\n\n"
    
    "5. **Set Stock (Absolute):** Override current stock total.\n"
    "   e.g. <code>Set Flour stock to 5 kg</code>\n\n"
    
    "6. **Price Update:** Update cost per base unit.\n"
    "   e.g. <code>1 kg Flour is now 5</code>\n\n"
    
    "7. **Show Inventory:** Shows all Ingredients in Inventory\n"
    "   e.g. <code>Show Inventory</code>\n\n"
    
    "Type <code>STOP</code> to exit Manager Mode."
)

async def enter_manager_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Starts the conversation when the user types the entry command.
    Sets the user's state to 'INGREDIENT_MANAGER' and sends the welcome message.
    """
    user_id = update.effective_user.username
    
    logging.info(f"USER {user_id}: Attempting to enter Ingredient Manager Mode.")

    try:
        # 1. Set the user state in user_data
        context.user_data['mode'] = 'INGREDIENT_MANAGER'
        
        # 2. Send the welcome message
        
        await update.message.reply_text(
            INGREDIENTS_MANAGER_WELCOME_MESSAGE,
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
    user_id = update.effective_user.username

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
    user_id = update.effective_user.username if update.effective_user else None
        
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
    """
    Handles the STOCK CHECK pattern, robustly checking all potential name capture groups
    and retrieving the current stock level.
    """
    # 1. Robustly retrieve the ingredient name from either capture group (name or name_q)
    # The first group that holds a value will be used.
    user_input_name = data.get('name') or data.get('name_q')
    
    if not user_input_name:
        logging.error("Stock check failed: Neither 'name' nor 'name_q' was captured by regex.")
        return "❌ Input error: Could not identify the ingredient name in your query."
        
    user_input_name = user_input_name.strip()
    
    logging.info(f"ACTION: Stock check detected for {user_input_name}.")

    # 2. Resolve name to ingredient record using the robust utility
    # NOTE: The _find_ingredient_by_name utility must be awaited if it performs DB I/O.
    try:
        ingredient_record = await ingredients._find_ingredient_by_name(user_input_name)
    except Exception as e:
        logging.error(f"DATABASE READ FAILED: Error during stock check lookup for '{user_input_name}'. Exception: {e}")
        return f"❌ A database error occurred while searching for **{user_input_name}**."

    if not ingredient_record:
        logging.warning(f"Stock check failed: Ingredient '{user_input_name}' not found.")
        return f"❌ Ingredient **{user_input_name}** was not found in inventory."

    # 3. Extract required info for the reply
    # Note: Using INGREDIENT_Quantity constant for stock and INGREDIENT_UNIT for unit
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

    user_id = update.effective_user.username if update.effective_user else None
        
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

    user_id = update.effective_user.username if update.effective_user else None

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

async def handle_unified_status_check(update: Update, data: dict) -> None:
    """
    Handles the Unified Status Check pattern (P3.E1).
    """
    # It attempts to get the name from either the first or second capture group depending on the pattern structure
    ingredient_name = data.get('name', '').strip()

    if not ingredient_name:
        await update.message.reply_text("❌ Input Error: Please specify the ingredient name.")
        return

    # 2. Call the service function
    success, message = await ingredients.get_ingredient_status(ingredient_name)

    # 3. Reply to the user using HTML for rich formatting
    await update.message.reply_html(message)

    # Note: This is a standalone check, so no conversation state change is needed.

async def handle_combined_inventory_set(update: Update, data: dict) -> None:
    """
    P3.E2: Handles the user's request to simultaneously set a new stock quantity 
    and a new price, utilizing a single atomic database call.
    """
   
    ingredient_name = data.get('name', '').strip()
    
    # --- 1. Determine which set of capture groups contains the actual data ---
    
    # Check for the presence of the first pattern's stock group
    is_stock_first = bool(data.get('stock_quantity'))
    
    # 1a. Extract Stock Data
    stock_qty_str = data.get('stock_quantity' if is_stock_first else 'stock_quantity_2')
    stock_unit = data.get('stock_unit' if is_stock_first else 'stock_unit_2').strip()
    
    # 1b. Extract Price Data
    price_cost_str = data.get('price_cost' if is_stock_first else 'price_cost_2')

    # 1c. Safety check for mandatory fields
    if not ingredient_name or not stock_unit:
        await update.message.reply_text("❌ Input Error: Missing ingredient name or stock unit. Example: `flour stock 15kg price 1.5`")
        return

    try:
        # Convert strings to required types
        stock_qty = float(stock_qty_str)
        price_cost = float(price_cost_str)
    except (ValueError, TypeError):
        await update.message.reply_text("❌ Input Error: Both stock quantity and price must be valid numbers.")
        return

    user_id = update.effective_user.id
    logging.info(f"ACTION: Combined inventory set detected for '{ingredient_name}'.")

    # --- 2. Call the SINGLE ATOMIC service function ---
    # The atomic service handles conversion, single database update, and history logging.
    success, message = await ingredients.atomic_combined_update(
        name=ingredient_name,
        stock_qty_input=stock_qty,
        stock_unit_input=stock_unit,
        price_cost_input=price_cost,
        user_id=user_id
    )

    # 3. Final Reply
    await update.message.reply_html(message)
    
async def handle_stock_usage(update: Update, data: dict) -> str:
        
    # 1. Extract and Validate Input
    name = data.get('name', '').strip()
    input_unit = (data.get('unit') or '').strip()
    
    try:
        input_qty = float(data.get('quantity'))
    except (ValueError, TypeError):
        return "❌ Input Error: Usage quantity must be a valid number."
        

    # 2. Call Adjustment Service (is_addition=False)
    success, message = await ingredients.adjust_ingredient_stock(
        name=name,
        input_quantity=input_qty,
        input_unit=input_unit,
        is_addition=False,
        user_id=update.effective_user.id
    )
    return message

# P3.E3b: Handle Stock Addition
async def handle_stock_addition(update: Update, data: dict) -> None:
       
    # 1. Extract and Validate Input
    name = data.get('name', '').strip()
    input_unit = (data.get('unit') or '').strip()
    
    try:
        input_qty = float(data.get('quantity'))
    except (ValueError, TypeError):
        await update.message.reply_text("❌ Input Error: Addition quantity must be a valid number.")
        return

    # 2. Call Adjustment Service (is_addition=True)
    success, message = await ingredients.adjust_ingredient_stock(
        name=name,
        input_quantity=input_qty,
        input_unit=input_unit,
        is_addition=True,
        user_id=update.effective_user.id
    )
    await update.message.reply_html(message)
    
async def handle_inventory_report(update: Update, data: dict) -> None:
    """
    P3.E7: Handles the request to display the full list of ingredients and stock levels.
    """
    # 1. Call the service function
    success, message = await ingredients.generate_full_inventory_report()

    # 2. Reply to the user using HTML
    await update.message.reply_html(message)
    
    # Optional: If the report is long, send it as a file/document instead of a chat message.

# --- Main Dispatcher ---

async def dispatch_nlp_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Parses the incoming natural language message and calls the appropriate handler function.
    """
    text = update.message.text.strip()
    user_id = update.effective_user.username
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
        
        elif match := STATUS_CHECK_REGEX.match(text):
            reply = await handle_unified_status_check(update, match.groupdict())
        
        elif match := STOCK_USAGE_REGEX_MODIFIED.match(text):
            reply = await handle_stock_usage(update, match.groupdict())
            
        elif match := STOCK_ADDITION_REGEX.match(text):
            reply = await handle_stock_addition(update, match.groupdict())
        
        elif match := COMBINED_UPDATE_REGEX.match(text):
            reply = await handle_combined_inventory_set(update, match.groupdict())
            
        elif match := INVENTORY_REPORT_REGEX.match(text):    
            reply = await handle_inventory_report(update, match.groupdict())
            
        elif match := STOP_REGEX.match(text):
            return exit_manager_mode(update)
            
            
            
            
        # 5. No match found
        else:
            reply = INGREDIENTS_MANAGER_FALLBACK_MESSAGE

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
            filters.Regex(r'(?i)^(Ingredients)$') & ~filters.COMMAND, 
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