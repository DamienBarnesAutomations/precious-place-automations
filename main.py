import os
import uvicorn
import logging
from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import Application, MessageHandler, filters # Import MessageHandler and filters
from starlette.responses import HTMLResponse
import re
from typing import Final # Import Final for constants

# Configure basic logging for the entire application
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import the necessary handlers and conversation state machine
from bot.handlers import send_global_welcome, global_fallback_handler
from bot.ingredients_handler import INGREDIENTS_MANAGER_MODE_CONVERSATION_HANDLER


# --- Configuration ---

# Get the token from Render Environment Variables
TELEGRAM_BOT_TOKEN: Final = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    # Log a critical error if the token is missing and raise an exception
    logger.critical("TELEGRAM_BOT_TOKEN is not set in environment variables!")
    raise Exception("TELEGRAM_BOT_TOKEN is not set!")

# --- Application Setup ---

# Initialize the FastAPI application
app = FastAPI(title="Precious Place Bot Backend")

# Initialize the PTB Application builder
application = (
    Application.builder()
    .token(TELEGRAM_BOT_TOKEN)
    .build()
)

# 🔑 Register the global welcome handler for common greetings
application.add_handler(
    MessageHandler(
        # Use Regex to catch start, hello, or help (case-insensitive, non-command)
        filters.Regex(r'(?i)^(start|hello|help)$') & ~filters.COMMAND,
        send_global_welcome
    )
)

# 🔑 Register the Ingredients Manager Conversation Handler
application.add_handler(INGREDIENTS_MANAGER_MODE_CONVERSATION_HANDLER) 

# 🔑 Register the Global Fallback Handler (must be registered last)
# It handles all remaining text messages that are not commands
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, global_fallback_handler))

# Global flag to track if the application has been initialized (prevents multiple initializations)
app_initialized = False


# --- FastAPI Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def root():
    """
    A simple root endpoint to confirm the service is running.
    """
    # Log successful hit to the root endpoint
    logger.info("Root endpoint hit: Service is running.")
    return "<h1>Telegram Bakery Bot Backend is running and awaiting webhook! 🚀</h1>"

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Endpoint to receive all incoming updates from Telegram.
    Processes the update using the python-telegram-bot Application.
    """
    global app_initialized
    
    # --- CRITICAL FIX: Initialize Application ---
    if not app_initialized:
        # Initialize the PTB application only once
        logger.info("Initializing python-telegram-bot application...")
        await application.initialize()
        app_initialized = True
    # ------------------------------------------

    try:
        # Get the JSON data from the request
        data = await request.json()
    except Exception as e:
        # Log invalid JSON error and raise a 400 response
        logger.error(f"Invalid JSON received on webhook. Error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    try:
        # Pass the data to the python-telegram-bot Application
        update = Update.de_json(data, application.bot)
        
        # Process the incoming update (this calls the handlers)
        await application.process_update(update)
        
    except Exception as e:
        # Log any error during PTB processing but return 200 to Telegram
        logger.error(f"Error processing Telegram update: {e}", exc_info=True)
        # Telegram requires an immediate 200 OK response even on internal error
        return {"message": "Update processed (with error logged)"}

    # Log successful update processing
    logger.debug("Update processed successfully.")
    # Telegram requires an immediate 200 OK response
    return {"message": "Update processed"}

# --- Run Command (for local development only) ---
# if __name__ == "__main__":
#     # NOTE: Render will use the 'uvicorn main:app' Start Command
#     uvicorn.run(app, host="0.0.0.0", port=8000)