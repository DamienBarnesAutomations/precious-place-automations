from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from services import ingredients 
import re
from services import ingredients 
from services import conversion

# --- Conversation States ---

INGREDIENT_MANAGER_MODE = range(7, 8)[0] # State ID 7


# --- Regular Expressions for NLP Actions  ---

# Regex 1: Handles NEW BUY/ADD
BUY_REGEX = re.compile(
    r"(?i)^(bought|add)\s+(?P<quantity>\d+(\.\d+)?)\s+(?P<unit>\w+)\s+(?P<name>.+?)\s+for\s+(?P<cost>\d+(\.\d+)?)$"
)

# Regex 2: Handles STOCK ADJUSTMENT 
ADJUST_REGEX = re.compile(
    r"(?i)^(increase|decrease|adjust)\s+(?P<name>.+?)\s+(quantity|stock)\s+(by|to)\s+(?P<quantity>\d+(\.\d+)?)\s+(?P<unit>\w+)$"
)

# Regex 3: Handles PRICE UPDATE
PRICE_UPDATE_REGEX = re.compile(
    r"(?i)^(update)\s+(?P<name>.+?)\s+unit\s+cost\s+to\s+(?P<cost>\d+(\.\d+)?)$"
)

# Regex 4: Handles STOCK CHECK
STOCK_CHECK_REGEX = re.compile(
    r"(?i)^(show|check)\s+(stock|quantity)\s+for\s+(?P<name>.+)$"
)

async def enter_manager_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Starts the conversation when the user types 'Manage Ingredients' (or similar command).
    Sets the bot into a state where it expects natural language actions.
    """
    context.user_data['mode'] = 'INGREDIENT_MANAGER'
    await update.message.reply_text(
        "📝 **Ingredient Manager Mode**\n\n"
        "I'm now ready to accept natural language commands.\n"
        "Try sending: `Bought 1 kg Flour for 5` or `Update Flour unit cost to 5`.\n"
        "Type `STOP` to exit this mode.",
        parse_mode="Markdown"
    )
    # Move to the special state where we listen for NLP commands
    return INGREDIENT_MANAGER_MODE


async def exit_manager_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exits the Ingredient Manager Mode."""
    context.user_data.pop('mode', None)
    await update.message.reply_text("👋 Exited Ingredient Manager Mode. Commands like `/add` or `/showstock` are available again.")
    # End the conversation and return to global handlers
    return ConversationHandler.END
    
    
async def dispatch_nlp_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Parses the incoming natural language message and calls the appropriate service function.
    """
    text = update.message.text.strip()
    
    # 1. Try to match the BUY/ADD pattern
    if match := BUY_REGEX.match(text):
        data = match.groupdict()
        
        # NOTE: This logic needs to decide if it's a new ingredient OR an existing ingredient update.
        # Since we don't have a service function to search by NAME (only ID), 
        # for now, we will treat everything that matches this pattern as a NEW ingredient.
        # Future refinement: check if name exists, get its ID, then use P3.1.6/P3.1.8.
        
        # For P3.1.4 (add_new_ingredient) to work:
        name = data['name'].strip()
        quantity = float(data['quantity'])
        unit = data['unit'].strip()
        cost = float(data['cost'])

        # --- Call Service Logic ---
        new_id = await ingredients.add_new_ingredient(name, quantity, unit, cost)
        
        if new_id and new_id != "ERROR_SAVE_FAILED":
            reply = f"🎉 **New Ingredient Added**\n\n**ID:** `{new_id}`\n**Name:** {name}\n**Stock:** {quantity} {unit}\n**Cost:** {cost:.2f} €"
        else:
            reply = f"❌ Error saving '{name}'. Please check the logs."

    # 2. Try to match the ADJUST pattern (P3.1.8 logic)
    elif match := ADJUST_REGEX.match(text):
        data = match.groupdict()
        name = data['name'].strip()
        quantity = float(data['quantity'])
        unit = data['unit'].strip()
        action = data[1].lower() # 'increase' or 'decrease'
        
        # FUTURE DEPENDENCY: We need a function to get the ID from the NAME.
        # For now, let's assume the user uses the ID for testing.
        # Replace 'name' lookup with direct ID usage for now:
        ingredient_id = name.upper() # Assuming user sends ID as the 'name' placeholder

        # Invert quantity for 'decrease'
        if action == 'decrease':
            quantity *= -1

        # --- Call Service Logic ---
        if await ingredients.adjust_ingredient_stock(ingredient_id, quantity, unit):
            reply = f"✅ Stock adjusted for **{name}** (`{ingredient_id}`)."
        else:
            reply = f"❌ Failed to adjust stock. Check if ID **`{ingredient_id}`** exists or if unit conversion failed."

    # 3. Try to match the PRICE UPDATE pattern (P3.1.6 logic)
    elif match := PRICE_UPDATE_REGEX.match(text):
        # FUTURE DEPENDENCY: We need a function to get the ID from the NAME.
        # For now, assume user sends ID.
        data = match.groupdict()
        ingredient_id = data['name'].strip().upper() 
        new_price = float(data['cost'])
        
        # --- Call Service Logic ---
        if await ingredients.update_ingredient_price(ingredient_id, new_price):
            reply = f"💰 Price updated for **`{ingredient_id}`** to {new_price:.2f} €."
        else:
            reply = f"❌ Failed to update price. ID **`{ingredient_id}`** not found."
            
    # 4. Try to match the STOCK CHECK pattern (P3.1.7 logic)
    elif match := STOCK_CHECK_REGEX.match(text):
        # FUTURE DEPENDENCY: We need a function to get the ID from the NAME.
        # For now, assume user sends ID.
        data = match.groupdict()
        ingredient_id = data['name'].strip().upper() 

        # --- Call Service Logic ---
        stock_info = await ingredients.get_ingredient_stock(ingredient_id) 
        
        if stock_info:
            reply = (
                f"✅ **Stock for {stock_info['name']}** (`{ingredient_id}`):\n\n"
                f"**Current Stock:** {stock_info['stock']} {stock_info['unit']}"
            )
        else:
            reply = f"❌ Ingredient ID **`{ingredient_id}`** was not found."

    # 5. No match found
    else:
        reply = (
            "🧐 **Unrecognized Action.** Please use one of the following formats:\n"
            "* `Bought 1 kg Flour for 5` (Adds new ingredient)\n"
            "* `Increase ING001 quantity by 500 g`\n"
            "* `Update ING001 unit cost to 5.95`\n"
            "* `Check stock for ING001`\n"
            "Type `STOP` to exit Manager Mode."
        )

    await update.message.reply_text(reply, parse_mode="Markdown")
    
    # Stay in the manager mode state, ready for the next command
    return INGREDIENT_MANAGER_MODE

INGREDIENTS_MANAGER_MODE_CONVERSATION_HANDLER = ConversationHandler(
    entry_points=[
        MessageHandler(
            filters.Regex(r'(?i)^(Manage Ingredients|manager)$') & ~filters.COMMAND, 
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