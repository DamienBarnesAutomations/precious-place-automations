# bot/handlers.py (Final reliable version)

from telegram import Update
from telegram.ext import ContextTypes


async def send_global_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (other code) ...
    
    welcome_message = """\
👋 *Welcome to the Bakery Bot\\!*

I can help you manage your ingredients, track stock, and log costs\\.

*📝 Available Modes*
* *Ingredient Manager Mode:* Type `Manage Ingredients` to switch the bot into natural language mode for tracking stock, costs, and purchases\\.
    * *In Manager Mode:* Send actions like `Bought 1 kg Flour for 5` or `Check stock for ING001`\\.
    * *To Exit:* Type `STOP`
* **\[Future Mode 1\]**: \\(e\\.g\\., Recipe Planner Mode\\)  <-- ADDED ESCAPING HERE
* **\[Future Mode 2\]**: \\(e\\.g\\., Financial Analysis Mode\\)  <-- ADDED ESCAPING HERE

*💬 Global Commands*
You can type `start`, `hello`, or `help` anytime to see this message\\.\
"""
    
    await update.message.reply_text(
        welcome_message, 
        parse_mode="MarkdownV2" 
    )