from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters

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
    # Move to the INGREDIENT_NAME state
    return INGREDIENT_NAME


async def get_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the ingredient name and asks for the stock level."""
    # Store the input in the context for later use
    context.user_data["temp_ingredient_name"] = update.message.text
    
    await update.message.reply_text(
        f"✅ Saved Name: **{update.message.text}**.\n\nWhat is the **Current Stock Level** (number only)?",
        parse_mode="Markdown"
    )
    # Move to the INGREDIENT_STOCK state
    return INGREDIENT_STOCK


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text("🚫 Ingredient setup canceled. Type /add to start over.")
    # End the conversation
    return ConversationHandler.END


# --- Exportable Conversation Handler Object ---

ADD_INGREDIENT_CONVERSATION_HANDLER = ConversationHandler(
    entry_points=[CommandHandler("add", start_add)],
    
    states={
        INGREDIENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_stock)],
        
        # State 2 (Stock) and onward will be completed in P3.1.3
        INGREDIENT_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: ConversationHandler.END)], # Placeholder
    },
    
    fallbacks=[CommandHandler("cancel", cancel)],
)