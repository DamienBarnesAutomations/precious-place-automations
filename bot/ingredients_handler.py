from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from services import ingredients # We will use the service module to save data
import re

# --- Conversation States ---
# Define states for the /add ingredient conversation flow
(
    INGREDIENT_NAME,
    INGREDIENT_STOCK,
    INGREDIENT_UNIT,
    INGREDIENT_COST,
) = range(4) 


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


# --- Exportable Conversation Handler Object ---

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