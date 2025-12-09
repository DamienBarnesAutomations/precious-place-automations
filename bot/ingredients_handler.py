from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from services import ingredients 
import re
from services import ingredients 
from services import conversion

# --- Conversation States ---
# Define states for the /add ingredient conversation flow
(
    INGREDIENT_NAME,
    INGREDIENT_STOCK,
    INGREDIENT_UNIT,
    INGREDIENT_COST,
) = range(4) 

# --- Conversation States (NEW for /updateprice) ---
(
    PRICE_GET_ID,
    PRICE_GET_NEW_VALUE,
) = range(4, 6) # Start ranging from 4 to avoid conflict with existing states

STOCK_GET_ID = range(6, 7)[0] # State ID 6

INGREDIENT_MANAGER_MODE = range(7, 8)[0] # State ID 7


async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks the user for the ingredient name."""
    await update.message.reply_text(
        "👋 **New Ingredient Setup**\n\nWhat is the **Name** of the new ingredient (e.g., 'All-Purpose Flour')?",
        parse_mode="Markdown"
    )
    return INGREDIENT_NAME


async def get_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the ingredient name and asks for the stock level."""
    context.user_data["temp_ingredient_name"] = update.message.text
    
    await update.message.reply_text(
        f"✅ Saved Name: **{update.message.text}**.\n\nWhat is the **Current Stock Level** (number only)?",
        parse_mode="Markdown"
    )
    return INGREDIENT_STOCK


async def get_unit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Saves the stock level (after validation) and asks for the unit of measure.
    """
    try:
        # P3.1.3 Validation: Ensure input is a valid number
        stock_value = float(update.message.text)
        if stock_value < 0:
            raise ValueError
        
        context.user_data["temp_ingredient_stock"] = stock_value
        
        await update.message.reply_text(
            f"✅ Saved Stock: **{stock_value}**.\n\nWhat is the **Unit of Measure** (e.g., kg, g, L)?",
            parse_mode="Markdown"
        )
        return INGREDIENT_UNIT
        
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid input. Stock must be a **positive number**.\n\nPlease re-enter the Current Stock Level (number only):",
            parse_mode="Markdown"
        )
        return INGREDIENT_STOCK # Stay in the same state


async def get_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Saves the unit (after validation) and asks for the cost per unit.
    """
    user_unit = update.message.text.strip().lower()

    # P3.1.3 Validation: Unit validation (Placeholder logic)
    # NOTE: This validation should call a service function that checks the 'Units' sheet (P3.1.9).
    # For now, we will use a simple regex check for common units until P3.1.9 is done.
    if not re.match(r'^(kg|g|l|ml|count|unit)$', user_unit):
        await update.message.reply_text(
            f"❌ Unit **'{user_unit}'** is not a common unit (kg, g, L, ml, count, unit).\n\nPlease re-enter the correct Unit of Measure:",
            parse_mode="Markdown"
        )
        return INGREDIENT_UNIT # Stay in the same state

    context.user_data["temp_ingredient_unit"] = user_unit
    
    await update.message.reply_text(
        f"✅ Saved Unit: **{user_unit}**.\n\nWhat is the **Cost per Unit** in euros (number only)?",
        parse_mode="Markdown"
    )
    return INGREDIENT_COST


async def finish_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Saves the final cost, calls the service function to save to the sheet, and ends the conversation.
    """
    try:
        # P3.1.3 Validation: Ensure input is a valid positive number
        cost_value = float(update.message.text)
        if cost_value <= 0:
            raise ValueError
        
        # Gather all saved data
        name = context.user_data.get("temp_ingredient_name")
        stock = context.user_data.get("temp_ingredient_stock")
        unit = context.user_data.get("temp_ingredient_unit")
        
        # --- P3.1.4 DEPENDENCY: Call the service to save the data ---
        new_id = await ingredients.add_new_ingredient(name, stock, unit, cost_value)
        # --- END DEPENDENCY ---
        
        await update.message.reply_text(
            f"🎉 **Success!** Ingredient saved and tracked.\n\n"
            f"**ID:** `{new_id}`\n"
            f"**Name:** {name}\n"
            f"**Stock:** {stock} {unit}\n"
            f"**Cost:** {cost_value:.2f} €",
            parse_mode="Markdown"
        )
        
        # Clear temporary data and end
        context.user_data.clear()
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid input. Cost must be a **positive number**.\n\nPlease re-enter the Cost per Unit (number only):",
            parse_mode="Markdown"
        )
        return INGREDIENT_COST # Stay in the same state
    except Exception as e:
        await update.message.reply_text(
            f"❌ An error occurred while saving: {e}\n\nPlease try again later or type /cancel.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    context.user_data.clear()
    await update.message.reply_text("🚫 Ingredient setup canceled. Type /add to start over.")
    return ConversationHandler.END

# bot/ingredients_handler.py (Add new functions)

async def start_update_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks for the ingredient ID."""
    await update.message.reply_text(
        "📝 **Update Ingredient Price**\n\nPlease provide the **ID** of the ingredient you want to update (e.g., `ING001`).",
        parse_mode="Markdown"
    )
    return PRICE_GET_ID


async def get_new_price_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the ingredient ID and asks for the new price."""
    ingredient_id = update.message.text.strip().upper()
    
    # 🚨 NOTE: We should validate if the ID exists here by calling a service function.
    # For now, we save and assume it's valid, as the service function will check it later.
    
    context.user_data["temp_price_update_id"] = ingredient_id

    await update.message.reply_text(
        f"✅ Saved ID: **{ingredient_id}**.\n\nWhat is the **New Cost per Unit** in euros (number only)?",
        parse_mode="Markdown"
    )
    return PRICE_GET_NEW_VALUE


async def finish_update_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the new price, calls the service function to update the sheet, and ends the conversation."""
    try:
        new_price = float(update.message.text)
        if new_price <= 0:
            raise ValueError
        
        ingredient_id = context.user_data.get("temp_price_update_id")
        
        # --- P3.1.6 DEPENDENCY: Call the service to update the price ---
        success = await ingredients.update_ingredient_price(ingredient_id, new_price)
        # --- END DEPENDENCY ---
        
        if success:
            await update.message.reply_text(
                f"💰 **Success!** Price updated for **`{ingredient_id}`**.\n\n"
                f"**New Cost per Unit:** {new_price:.2f} €.\n"
                f"*(Price history logged.)*",
                parse_mode="Markdown"
            )
        else:
             await update.message.reply_text(
                f"❌ Update failed. Ingredient ID **`{ingredient_id}`** was not found in the sheet.",
                parse_mode="Markdown"
            )

        context.user_data.clear()
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid input. Price must be a **positive number**.\n\nPlease re-enter the New Cost per Unit:",
            parse_mode="Markdown"
        )
        return PRICE_GET_NEW_VALUE # Stay in the same state
    except Exception as e:
        await update.message.reply_text(
            f"❌ An error occurred while saving: {e}\n\nPlease try again later or type /cancel.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END


async def cancel_price_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    context.user_data.clear()
    await update.message.reply_text("🚫 Price update canceled. Type /updateprice to start over.")
    return ConversationHandler.END
# --- Exportable Conversation Handler Object ---

async def start_show_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks for the ingredient ID."""
    await update.message.reply_text(
        "📦 **Show Stock**\n\nPlease provide the **ID** of the ingredient you want to check (e.g., `ING001`).",
        parse_mode="Markdown"
    )
    return STOCK_GET_ID


async def finish_show_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gets the ingredient ID, retrieves its stock, and ends the conversation."""
    ingredient_id = update.message.text.strip().upper()
    
    # --- P3.1.7 DEPENDENCY: Call the service to retrieve stock ---
    # We will implement this function in the service layer next.
    stock_info = await ingredients.get_ingredient_stock(ingredient_id) 
    # stock_info is expected to be {'name': str, 'stock': float, 'unit': str} or None
    # --- END DEPENDENCY ---
    
    if stock_info:
        await update.message.reply_text(
            f"✅ **Stock for {stock_info['name']}** (`{ingredient_id}`):\n\n"
            f"**Current Stock:** {stock_info['stock']} {stock_info['unit']}",
            parse_mode="Markdown"
        )
    else:
         await update.message.reply_text(
            f"❌ Ingredient ID **`{ingredient_id}`** was not found in the sheet.",
            parse_mode="Markdown"
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_stock_inquiry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    context.user_data.clear()
    await update.message.reply_text("🚫 Stock inquiry canceled. Type /showstock to start over.")
    return ConversationHandler.END
    
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
    
    

ADD_INGREDIENT_CONVERSATION_HANDLER = ConversationHandler(
    entry_points=[CommandHandler("add", start_add)],
    
    states={
        INGREDIENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_stock)],
        
        # State 2: Stock collection, requires validation
        INGREDIENT_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_unit)],
        
        # State 3: Unit collection, requires validation
        INGREDIENT_UNIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_cost)],
        
        # State 4: Cost collection, requires validation and final save
        INGREDIENT_COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, finish_add)],
    },
    
    fallbacks=[CommandHandler("cancel", cancel)],
)

UPDATE_PRICE_CONVERSATION_HANDLER = ConversationHandler(
    entry_points=[CommandHandler("updateprice", start_update_price)],
    
    states={
        PRICE_GET_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_price_value)],
        
        # State 2: Price collection, requires validation and final save
        PRICE_GET_NEW_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, finish_update_price)],
    },
    
    fallbacks=[CommandHandler("cancel", cancel_price_update)],
)

SHOW_STOCK_CONVERSATION_HANDLER = ConversationHandler(
    entry_points=[CommandHandler("showstock", start_show_stock)],
    
    states={
        STOCK_GET_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, finish_show_stock)],
    },
    
    fallbacks=[CommandHandler("cancel", cancel_stock_inquiry)],
)

MANAGER_MODE_CONVERSATION_HANDLER = ConversationHandler(
    entry_points=[
        MessageHandler(
            filters.Regex(r'^(Manage Ingredients|manager)$', flags=re.IGNORECASE) & ~filters.COMMAND, 
            enter_manager_mode
        )
    ],
    
    states={
        # P3.1.R2 will implement the dispatcher function that handles NLP here
        INGREDIENT_MANAGER_MODE: [
            
            # --- Regular Expressions for NLP Actions ---

            # Regex 1: Handles NEW BUY/ADD (The most complex one)
            # Pattern: (Bought|Add) [QUANTITY] [UNIT] [NAME] for [COST]
            # Example: Bought 1 kg Flour for 5
            BUY_REGEX = re.compile(
                r"^(bought|add)\s+(?P<quantity>\d+(\.\d+)?)\s+(?P<unit>\w+)\s+(?P<name>.+?)\s+for\s+(?P<cost>\d+(\.\d+)?)$",
                re.IGNORECASE
            )

            # Regex 2: Handles STOCK ADJUSTMENT (Increase/Decrease)
            # Pattern: (Increase|Decrease|Adjust) [NAME] quantity by [QUANTITY] [UNIT]
            # Example: Increase Flour Quantity by 500 g
            ADJUST_REGEX = re.compile(
                r"^(increase|decrease|adjust)\s+(?P<name>.+?)\s+(quantity|stock)\s+(by|to)\s+(?P<quantity>\d+(\.\d+)?)\s+(?P<unit>\w+)$",
                re.IGNORECASE
            )

            # Regex 3: Handles PRICE UPDATE
            # Pattern: Update [NAME] unit cost to [COST]
            # Example: Update Flour unit cost to 5.95
            PRICE_UPDATE_REGEX = re.compile(
                r"^(update)\s+(?P<name>.+?)\s+unit\s+cost\s+to\s+(?P<cost>\d+(\.\d+)?)$",
                re.IGNORECASE
            )

            # Regex 4: Handles STOCK CHECK (Simple)
            # Pattern: (Show|Check) (stock|quantity) for [NAME]
            # Example: Check stock for Flour
            STOCK_CHECK_REGEX = re.compile(
                r"^(show|check)\s+(stock|quantity)\s+for\s+(?P<name>.+)$",
                re.IGNORECASE
            )
            MessageHandler(filters.TEXT & ~filters.COMMAND, dispatch_nlp_action)
        ],
    },
    
    # We use a specific keyword 'STOP' to leave the mode
    fallbacks=[MessageHandler(filters.Regex(r'^STOP$', flags=re.IGNORECASE), exit_manager_mode)],
)

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