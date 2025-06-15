"""
Leyla Cuisine Quotation Generator Bot

This script implements a Telegram bot for Leyla Cuisine, providing automated quotation generation,
menu management, contact management, and delivery scheduling for catering orders. The bot uses
multiple AI agents (triage, parser, menu, contacts, calendar) to route user requests to the
appropriate handler. It integrates with Google Drive for persistent storage and Google Calendar
for delivery scheduling. The bot is multi-threaded: each incoming message is processed in a
separate thread to ensure responsiveness and avoid blocking the main polling loop.

Main Logic Flow:
- Loads environment variables and initializes the Telegram bot.
- Imports and lazy-loads Google Drive and email handlers.
- Defines AI agents for triage, order parsing, menu, contacts, and calendar operations.
- Maintains per-user state and message history for context-aware responses.
- Processes incoming messages by routing them to the correct agent, handling agent handoffs,
  and managing follow-up interactions.
- Handles order confirmation, quotation generation, email sending, and optional delivery scheduling.
- Uses logging throughout for monitoring and debugging.

Threading Model:
- Each message is handled in a new thread (via threading.Thread in handle_message).
- This prevents blocking the main bot polling loop and allows concurrent processing of multiple user requests.
- Thread safety is maintained for per-user state by using dictionaries keyed by user_id.

"""

# ==============================
# Imports and Initialization
# ==============================

import os
import telebot
import threading  # For multi-threaded message handling
import asyncio
import logging
from dotenv import load_dotenv
import openai
import tools_handler as tl
from tools_handler import (
    calculate_quotation, generate_pdf_quote, save_sales, save_approved_quotation,
    Menu_item, Order, add_menu_item, edit_menu_item, delete_menu_item, list_menu_items,
    Contact, add_contact, edit_contact, delete_contact, list_contacts,
    DeliveryEvent, add_delivery_event, edit_delivery_event, delete_delivery_event
)
from agents import Agent, Runner, handoff, RunContextWrapper
from typing import Union
from datetime import datetime  # Changed from import datetime
from config import (
    TELEGRAM_API_KEY, GOOGLE_CREDENTIALS_FILE, GOOGLE_EMAIL,
    DEFAULT_SENDER_EMAIL, DEFAULT_RECIPIENT_EMAIL,
    TOKEN_FILES, DRIVE_CONFIG, CALENDAR_CONFIG,
    validate_config
)
from google_handlers.oauth_setup import check_google_setup, generate_oauth_url, generate_oauth_url_with_state, handle_oauth_callback
import queue
import secrets
from flask import Flask, request, render_template_string, redirect, url_for

# ==============================
# Global State and Bot Setup
# ==============================

# Validate configuration
validate_config()

user_states = {}  # user_id -> state dict

# Initialize Telegram bot
bot = telebot.TeleBot(TELEGRAM_API_KEY)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================
# Flask Web Server for OAuth Callbacks
# ==============================

# Initialize Flask app
app = Flask(__name__)

# OAuth state management
oauth_states = {}  # state -> user_id mapping
oauth_callback_queue = queue.Queue()  # Queue for (user_id, code) pairs

# HTML template for OAuth success/error pages
SUCCESS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Authentication Successful</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
        .success { color: green; }
        .container { max-width: 500px; margin: 0 auto; padding: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="success">✅ Authentication Successful!</h1>
        <p>Your Google account has been successfully linked to the Leyla Cuisine bot.</p>
        <p>You can now close this window and return to Telegram to use all features.</p>
        <p><strong>The bot will notify you shortly in Telegram.</strong></p>
    </div>
</body>
</html>
"""

ERROR_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Authentication Error</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
        .error { color: red; }
        .container { max-width: 500px; margin: 0 auto; padding: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="error">❌ Authentication Error</h1>
        <p>{{ error_message }}</p>
        <p>Please return to Telegram and try the authentication process again.</p>
        <p>You can use the /setup_google command to get a new authorization link.</p>
    </div>
</body>
</html>
"""

@app.route('/oauth2callback')
def oauth_callback():
    """Handle OAuth2 callback from Google"""
    try:
        # Get parameters from the callback
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        
        if error:
            logger.error(f"OAuth error: {error}")
            return render_template_string(ERROR_TEMPLATE, error_message=f"Google returned an error: {error}")
        
        if not code or not state:
            logger.error("Missing code or state in OAuth callback")
            return render_template_string(ERROR_TEMPLATE, error_message="Missing authorization code or state parameter.")
        
        # Validate state and get user_id
        user_id = oauth_states.get(state)
        if not user_id:
            logger.error(f"Invalid state parameter: {state}")
            return render_template_string(ERROR_TEMPLATE, error_message="Invalid or expired authorization request.")
        
        # Remove the state (one-time use)
        del oauth_states[state]
        
        # Put the code in the queue for processing
        oauth_callback_queue.put((user_id, code))
        
        logger.info(f"OAuth callback received for user {user_id}, code queued for processing")
        return render_template_string(SUCCESS_TEMPLATE)
        
    except Exception as e:
        logger.exception("Error in oauth_callback")
        return render_template_string(ERROR_TEMPLATE, error_message="An unexpected error occurred during authentication.")

@app.route('/')
def root():
    """Handle root route - check if this is a misrouted OAuth callback"""
    try:
        # Check if this looks like an OAuth callback that hit the wrong endpoint
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        
        if code or state or error:
            logger.info("OAuth callback received at root endpoint, redirecting to proper handler")
            # This is likely an OAuth callback that hit the wrong endpoint
            # Redirect to the proper callback endpoint with all parameters
            return redirect(url_for('oauth_callback', **request.args))
        
        # Regular root access
        return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Leyla Cuisine Bot</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
                .container { max-width: 500px; margin: 0 auto; padding: 20px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🍽️ Leyla Cuisine Bot</h1>
                <p>This is the OAuth callback server for the Leyla Cuisine Telegram bot.</p>
                <p>If you're seeing this page, the server is running correctly.</p>
                <p>Please return to Telegram to interact with the bot.</p>
            </div>
        </body>
        </html>
        """)
        
    except Exception as e:
        logger.exception("Error in root handler")
        return "Server Error", 500

def run_flask():
    """Run Flask app in a separate thread"""
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

# Start Flask server in background thread
flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()
logger.info("Flask server started on port 8080 for OAuth callbacks")

# ==============================
# OAuth Callback Queue Monitor
# ==============================

def monitor_oauth_queue():
    """Monitor the OAuth callback queue and process authentication automatically"""
    while True:
        try:
            # Wait for OAuth callback
            user_id, code = oauth_callback_queue.get(timeout=1)
            logger.info(f"Processing OAuth code for user {user_id}")
            
            try:
                # Process the auth code
                success, result_message = handle_oauth_callback(code)
                
                if success:
                    bot.send_message(user_id, "✅ Google authentication completed successfully!")
                    # Initialize Google services now that authentication is complete
                    bot.send_message(user_id, "Initializing Google services...")
                    if initialize_google_services():
                        bot.send_message(user_id, "🎉 All Google services are now ready! You can use all bot features.")
                    else:
                        bot.send_message(user_id, "⚠️ Google services partially initialized. Some features may be limited.")
                else:
                    bot.send_message(user_id, f"❌ Authentication failed: {result_message}")
                    
            except Exception as e:
                logger.exception(f"Error processing OAuth code for user {user_id}")
                bot.send_message(user_id, f"❌ Authentication failed due to an error: {str(e)}")
                
        except queue.Empty:
            continue
        except Exception as e:
            logger.exception("Error in OAuth queue monitor")

# Start OAuth queue monitor in background thread
oauth_monitor_thread = threading.Thread(target=monitor_oauth_queue, daemon=True)
oauth_monitor_thread.start()
logger.info("OAuth callback queue monitor started")

# ==============================
# Google Drive Handler Setup
# ==============================

gdh = None
DRIVE_IDS = None
menu = {}
menu_items_str = ""

def initialize_google_services():
    """
    Initialize Google Drive handler and load menu.
    Only called after confirming authentication tokens exist.
    """
    global gdh, DRIVE_IDS, menu, menu_items_str
    try:
        import google_handlers.google_drive_handler as gdh_module
        gdh = gdh_module
        DRIVE_IDS = gdh.DRIVE
        # Attempt to load menu from Google Drive
        try:
            menu = gdh.load_menu()
            menu_items_str = '", "'.join(menu.keys())
            menu_items_str = f'"{menu_items_str}"'
            logger.info("Menu loaded successfully from Google Drive.")
            return True
        except Exception as e:
            logger.error(f"Could not load menu from Google Drive: {e}")
            menu = {}
            menu_items_str = ""
            return False
    except Exception as e:
        logger.error(f"Could not import Google Drive handler: {e}")
        gdh = None
        DRIVE_IDS = None
        menu = {}
        menu_items_str = ""
        return False

    # Check if Google services are already set up during startup
    try:
        from google_handlers.oauth_setup import check_google_setup
        is_setup, setup_message = check_google_setup()
        if is_setup:
            logger.info("Google authentication detected. Initializing Google services...")
            if initialize_google_services():
                logger.info("Google services initialized successfully.")
            else:
                logger.warning("Google services partially initialized.")
        else:
            logger.info(f"Google services not initialized: {setup_message}")
            logger.info("Bot will prompt users to authenticate when Google features are needed.")
    except Exception as e:
        logger.error(f"Error checking Google setup during startup: {e}")
        logger.info("Bot will start without Google services. Users can authenticate later.")

# ==============================
# User State and Agent Setup
# ==============================

current_agent = ''
user_histories = {}  # user_id -> list of messages
MAX_HISTORY = 4  # Only keep the last 4 messages per user
active_agent_per_user = {}  # user_id -> currently active agent (for handoff continuity)

# ==============================
# Command Handlers
# ==============================

@bot.message_handler(commands=['Greet'])
def greet(message):
    """
    Responds to the /Greet command with a welcome message.
    """
    try:
        logger.info(f"Greet command received from user {message.from_user.id}")
        bot.reply_to(message, "Hello! How can I assist you today?")
    except Exception as e:
        logger.exception("Error in greet handler")

# ==============================
# Quotation Confirmation Handler
# ==============================

def confirmation_handler(message, pdf_path, recipient_email, quotation):
    """
    Handles user confirmation for sending the quotation and optionally schedules delivery.
    """
    try:
        logger.info(f"Confirmation handler triggered for user {message.from_user.id}")
        text = message.text.strip().lower()
        if text.startswith("y"):
            from google_handlers.email_handler import send_quotation_email
            send_status = send_quotation_email(pdf_path, recipient_email=recipient_email)
            if send_status:
                bot.send_message(message.chat.id, "Quotation sent via email successfully!")
                
                # Get customer name from quotation or message sender
                customer_name = quotation.get("name")
                if not customer_name:
                    customer_name = message.from_user.first_name
                    if message.from_user.last_name:
                        customer_name += f" {message.from_user.last_name}"
                
                # Save locally (just for reference)
                from tools_handler import save_approved_quotation
                saved_path = save_approved_quotation(pdf_path, customer_name)
                bot.send_message(message.chat.id, f"Approved quotation reference: {saved_path}")
                
                # Save to Google Drive
                if gdh:
                    try:
                        gdh.append_contact(message.from_user.first_name, recipient_email)
                        gdh.record_sales(quotation)
                        drive_file_id = gdh.save_quotation_to_drive(pdf_path, customer_name)
                        bot.send_message(message.chat.id, f"Quotation saved to Google Drive with ID: {drive_file_id}")
                        logger.info("Contact appended, sales recorded, and quotation saved in Google Drive.")
                    except Exception as e:
                        logger.error(f"Drive operation failed: {e}")
                        bot.send_message(message.chat.id, "Failed to save quotation to Google Drive.")
                
                # Ask if user wants to schedule delivery
                bot.send_message(message.chat.id, "Would you like to schedule a delivery event on the calendar? [y/n]")
                bot.register_next_step_handler(
                    message,
                    lambda m: handle_calendar_after_approval(m, quotation)
                )
            else:
                bot.send_message(message.chat.id, "Failed to send quotation via email.")
                logger.error("Failed to send quotation via email.")
        else:
            bot.send_message(message.chat.id, "Quotation sending canceled. Please try again if needed.")
            logger.info("User canceled quotation sending.")
    except Exception as e:
        logger.exception("Error in confirmation_handler")
        bot.send_message(message.chat.id, f"An error occurred: {str(e)}")

# ==============================
# Calendar Scheduling Handler
# ==============================

def handle_calendar_after_approval(message, quotation):
    """
    Handles scheduling a calendar event after quotation approval.
    """
    try:
        logger.info(f"Calendar scheduling requested by user {message.from_user.id}")
        text = message.text.strip().lower()
        if text.startswith("y"):
            client_email = quotation.get("email") or "unknown"
            client_name = quotation.get("name") or "Unknown Client"
            summary = f"Delivery for {client_name}"
            address = quotation.get("address")  # Let the agent resolve via list_contacts if needed
            description = f"Delivery for approved catering order.\nOrder details:\n"
            for item in quotation.get("quotation", []):
                description += f"- {item['Item']} x{item['Quantity']}\n"
            description += f"\nTotal: ${quotation.get('final_total', 0):.2f}"
            
            # Store state for this user
            user_id = message.from_user.id
            user_states[user_id] = {
                "calendar_agent_response": None,
                "quotation": quotation,
                "summary": summary,
                "description": description,
                "address": address,
                "is_address_update": False,  # Flag to track address updates
                "available_addresses": []  # List to store multiple addresses if found
            }
            
            prompt = (
                f"Schedule a delivery event for {client_name} ({client_email}).\n"
                f"Order details: {description}\n"
                f"Address: {address or 'To be determined'}\n"
                "Please check the contact list for any existing addresses and use them if available.\n"
                "If multiple addresses are found, ask the user which one to use.\n"
                "Please confirm the event details with the user before creating.\n"
                "End your response with [y/n] to get user confirmation."
            )
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(Runner.run(calendar_agent, prompt))
            
            # Store the calendar agent's response
            user_states[user_id]["calendar_agent_response"] = result.final_output
            
            # Send the response to the user
            bot.send_message(message.chat.id, str(result.final_output))
            
            # Register handler for user's confirmation
            bot.register_next_step_handler(
                message,
                lambda m: handle_calendar_confirmation(m, user_id)
            )
            logger.info("Calendar event details sent to user for confirmation.")
        else:
            bot.send_message(message.chat.id, "No calendar event scheduled.")
            logger.info("User declined calendar scheduling.")
    except Exception as e:
        logger.exception("Error in handle_calendar_after_approval")
        bot.send_message(message.chat.id, f"An error occurred: {str(e)}")

def handle_calendar_confirmation(message, user_id):
    """
    Handles user confirmation of calendar event details.
    """
    try:
        logger.info(f"Calendar confirmation received from user {user_id}")
        text = message.text.strip().lower()
        
        if text.startswith("y"):
            # Get the stored state
            state = user_states.get(user_id, {})
            if not state:
                raise ValueError("No calendar state found for user")
            
            # Create the event using the stored details
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(Runner.run(
                calendar_agent,
                f"Create the event with these details:\n{state['calendar_agent_response']}"
            ))
            
            # Send confirmation to user
            bot.send_message(message.chat.id, str(result.final_output))
            logger.info("Calendar event created successfully.")
        else:
            # Check if the response indicates an address update
            if "address" in text.lower() or "location" in text.lower():
                state = user_states.get(user_id, {})
                state["is_address_update"] = True
                
                # If we have multiple addresses, ask user to choose
                if state.get("available_addresses"):
                    addresses_text = "\n".join([f"{i+1}. {addr}" for i, addr in enumerate(state["available_addresses"])])
                    bot.send_message(
                        message.chat.id,
                        f"Please choose an address by number:\n{addresses_text}\n\nConfirm your choice? [y/n]"
                    )
                else:
                    bot.send_message(
                        message.chat.id,
                        "Please provide the new address:"
                    )
                # Register handler for address update
                bot.register_next_step_handler(
                    message,
                    lambda m: handle_calendar_response(m, user_id)
                )
            else:
                bot.send_message(
                    message.chat.id,
                    "Event creation canceled. Would you like to modify any details? [y/n]"
                )
                # Register handler for modifications
                bot.register_next_step_handler(
                    message,
                    lambda m: handle_calendar_modification(m, user_id)
                )
        
        # Clean up user state
        if user_id in user_states:
            del user_states[user_id]
            
    except Exception as e:
        logger.exception("Error in handle_calendar_confirmation")
        bot.send_message(message.chat.id, f"An error occurred: {str(e)}")
        # Clean up user state on error
        if user_id in user_states:
            del user_states[user_id]

def handle_calendar_modification(message, user_id):
    """
    Handles user requests to modify calendar event details.
    """
    try:
        logger.info(f"Calendar modification requested by user {user_id}")
        text = message.text.strip().lower()
        
        if text.startswith("y"):
            # Get the stored state
            state = user_states.get(user_id, {})
            if not state:
                raise ValueError("No calendar state found for user")
            
            # Ask user what they want to modify
            bot.send_message(
                message.chat.id,
                "What would you like to modify? (date, time, address, or other details) [y/n]"
            )
            # Register handler for specific modifications
            bot.register_next_step_handler(
                message,
                lambda m: handle_specific_modification(m, user_id)
            )
        else:
            bot.send_message(message.chat.id, "Calendar event scheduling canceled. [y/n]")
            # Clean up user state
            if user_id in user_states:
                del user_states[user_id]
            
    except Exception as e:
        logger.exception("Error in handle_calendar_modification")
        bot.send_message(message.chat.id, f"An error occurred: {str(e)}")
        # Clean up user state on error
        if user_id in user_states:
            del user_states[user_id]

def handle_specific_modification(message, user_id):
    """
    Handles specific modifications to calendar event details.
    """
    try:
        logger.info(f"Processing specific modification for user {user_id}")
        modification = message.text.strip().lower()
        
        # Get the stored state
        state = user_states.get(user_id, {})
        if not state:
            raise ValueError("No calendar state found for user")
        
        # Create a new prompt based on the modification request
        prompt = (
            f"Modify the calendar event with these changes:\n"
            f"Original details: {state['calendar_agent_response']}\n"
            f"Requested modification: {modification}\n"
            "Please confirm the updated event details with the user.\n"
            "End your response with [y/n] to get user confirmation."
        )
        
        # Get updated event details
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(Runner.run(calendar_agent, prompt))
        
        # Update stored state with new response
        user_states[user_id]["calendar_agent_response"] = result.final_output
        
        # Send updated details to user
        bot.send_message(message.chat.id, str(result.final_output))
        
        # Register handler for confirmation of modified details
        bot.register_next_step_handler(
            message,
            lambda m: handle_calendar_confirmation(m, user_id)
        )
        
    except Exception as e:
        logger.exception("Error in handle_specific_modification")
        bot.send_message(message.chat.id, f"An error occurred: {str(e)}")
        # Clean up user state on error
        if user_id in user_states:
            del user_states[user_id]

def handle_calendar_response(message, user_id):
    """
    Handles user response to calendar agent's message, including address updates.
    """
    try:
        state = user_states.get(user_id, {})
        if not state:
            raise ValueError("No calendar state found for user")
        
        # Check if this is an address update
        if state.get("is_address_update", False):
            # If we have multiple addresses, check if user selected one by number
            if state.get("available_addresses"):
                try:
                    choice = int(message.text.strip())
                    if 1 <= choice <= len(state["available_addresses"]):
                        state["address"] = state["available_addresses"][choice - 1]
                    else:
                        bot.send_message(message.chat.id, "Invalid selection. Please try again. [y/n]")
                        return
                except ValueError:
                    bot.send_message(message.chat.id, "Please select a valid number. [y/n]")
                    return
            else:
                # Update the address in the state
                state["address"] = message.text.strip()
            
            state["is_address_update"] = False
            
            # Create new prompt with updated address
            prompt = (
                f"Update the delivery event with the new address: {state['address']}\n"
                f"Original details: {state['calendar_agent_response']}\n"
                "Please confirm the updated event details with the user.\n"
                "End your response with [y/n] to get user confirmation."
            )
            
            # Get updated event details and continue with confirmation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(Runner.run(calendar_agent, prompt))
            
            # Send confirmation to user
            bot.send_message(message.chat.id, str(result.final_output))
            logger.info("Calendar event updated successfully.")
        else:
            bot.send_message(message.chat.id, "No address update needed. [y/n]")
            logger.info("User declined address update.")
    except Exception as e:
        logger.exception("Error in handle_calendar_response")
        bot.send_message(message.chat.id, f"An error occurred: {str(e)}")

# ==============================
# Agent Definitions
# ==============================

# Parser agent for orders
parser_agent = Agent(
    name='order_parser',
    model='gpt-4o',
    instructions=(
        'You are a helpful assistant that parses the user input and returns a JSON object matching the following structure: '
        '{"email": "customer@example.com", "name": "John Doe", "address": "123 Main St", "date": "2024-03-20", "items": [{"name": "Margherita Pizza", "quantity": 1}], "discount": "10%" or 10, "delivery": true, "tax_rate": 8.1} '
        'Your output should exactly match the naming of the food in the CSV. '
        f'Here is the menu list: {menu_items_str}. '
        'Note: The user may provide a discount as a percentage (e.g., "10%") or as a flat number (e.g., 10), '
        'indicate delivery by specifying "delivery": true or false, include their email address, '
        'and optionally specify a tax rate as a number (e.g., 8.1 for 8.1%). '
        'For name, address, and date: '
        '- If the user provides these details, include them in the output '
        '- If the user does not provide them, you can ask for them '
        '- If the user declines to provide them, simply omit them from the output '
        '- For date, use YYYY-MM-DD format if provided '
        '- If no date is provided, it will default to the current date '
        'Remember to maintain a friendly and professional tone when asking for missing information. '
        'Additional Contact Lookup Instructions: '
        '- You have access to the list_contacts tool to look up existing customer information '
        '- If the user provides an email or name that matches an existing contact, use their stored information '
        '- When a user provides an email, check if it exists in contacts to get their name and address '
        '- When a user provides a name, check if it exists in contacts to get their email and address '
        '- If you find a matching contact, use their information to fill in any missing fields '
        '- Always verify with the user if you find a matching contact to ensure it\'s the correct person '
        '- If no matching contact is found, proceed with the information provided by the user '
        '- For new customers, you can still ask for their information if not provided'
    ),
    tools=[
        list_contacts  # Add list_contacts tool to parser agent
    ],
    output_type=tl.Order,
)

menu_agent: Agent[tl.Menu_item] = Agent[tl.Menu_item](
    name="Menu agent",
    model='gpt-4o',
    instructions=(
        'You are a menu management agent that can add, edit, list, or delete menu items. '
        'When handling a menu operation, use the Menu_item structure for input. '
        'Output a message describing the operation performed. '
        f'Here is the current menu: {menu_items_str}.'
    ),
    tools=[
        add_menu_item,
        edit_menu_item,
        delete_menu_item,
        list_menu_items
    ],
    output_type=Union[tl.Menu_item, str],
)

contacts_agent = Agent(
    name="Contacts agent",
    model='gpt-4o',
    instructions=(
        'You are a contacts management agent that can add, edit, list, or delete contacts. '
        'When asked to add a number, email, or address to an existing contact, use the information from the user and edit the contact accordingly. '
        'When asked to delete the contact, delete all contact information. '
        'When asked to add a contact, request from the user to give phone, email, and address, if not already given. '
        'Use the Contact structure for input and output a message describing what you did.'
    ),
    tools=[
        add_contact,
        edit_contact,
        delete_contact,
        list_contacts
    ],
    output_type=Union[Contact, str],
)

def on_handoff_menu(ctx: RunContextWrapper):
    global current_agent
    current_agent = 'Menu agent'

def on_handoff_parser(ctx: RunContextWrapper):
    global current_agent
    current_agent = 'Parser agent'

def on_handoff_contacts(ctx: RunContextWrapper):
    global current_agent
    current_agent = 'Contacts agent'

def on_handoff_calendar(ctx: RunContextWrapper):
    global current_agent
    current_agent = 'Calendar agent'

calendar_agent = Agent(
    name="Calendar agent",
    model='gpt-4o',
    instructions=(
        "You are a calendar management agent for scheduling, editing, or deleting delivery events for catering orders. "
            "You can:\n"
            "- Create delivery events: Use the add_delivery_event tool. You need summary, address, description, start and end datetime, and optionally attendees.\n"
            "- Edit events: Use edit_delivery_event with the event_id and any fields to update.\n"
            "- Delete events: Use delete_delivery_event with the event_id.\n"
            "Address Handling Rules:\n"
            "- Always check the contact list first for any address information\n"
            "- If a client's address is in the contact list, use that address\n"
            "- If multiple addresses exist for a client, ask the user which one to use\n"
            "- If no address is found in contacts, use the address provided in the order\n"
            "- If no address is available, ask the user to provide one\n"
            "- Accept any valid address provided by the user\n"
            "If the user provides a client name but not an address, use the list_contacts tool to find the address. "
            "If the name is not found, ask the user to try again with a valid client name. "
            "If the user asks to schedule a delivery after a quotation is approved, use the order's email/name to look up the address. "
            "Always confirm the event details with the user before creating or editing events.\n"
            "Important Date/Time Rules:\n"
            "- Always use the current year (2025) for scheduling events\n"
            "- If a user provides a date without a year, assume it's for 2025\n"
            "- If a user provides a past date, ask them to provide a future date\n"
            "- Default delivery duration is 1 hour unless specified otherwise\n"
            "- All times should be in Mountain Time (UTC-7)\n"
            "- Format dates as YYYY-MM-DD and times as HH:MM:SS\n"
            "- When creating events, always verify the date is in the future\n"
            f"Current time in Mountain Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            "Additional Event Creation Rules:\n"
            "- Always include the client's name in the event summary\n"
            "- Include the order details in the event description\n"
            "- Set appropriate reminders (default is 1 hour before)\n"
            "- Always verify the address is complete and accurate\n"
            "- For delivery events, ensure the duration is appropriate (default 1 hour)\n"
            "- When scheduling from a quotation, include the quotation details in the description\n"
            "- Always confirm the event details with the user before creating\n"
            "- If the user confirms, create the event and provide the calendar link\n"
            "- If the user declines, ask for any corrections needed\n"
            "Error Handling:\n"
            "- If an address is missing, use list_contacts to find it\n"
            "- If a date is invalid, ask for a valid future date\n"
            "- If a time is not specified, ask for a preferred time\n"
            "- If any required information is missing, ask the user to provide it\n"
            "- If there's an error creating the event, explain the issue and ask for corrections"
    ),
    tools=[
        add_delivery_event,
        edit_delivery_event,
        delete_delivery_event,
        list_contacts
    ],
    output_type=Union[DeliveryEvent, str],
)

triage_agent = Agent(
    name="Triage agent",
    model='gpt-4o',
    instructions=(
        'Decide if the user input is an order, a menu operation, a contacts operation, or a calendar operation. '
        'When the user requests a quotation, to send an email, or to process an order, you should hand off to the parser agent. This very important'
        'Menu operations include "menu", "add", "edit", "delete" for menu items. '
        'Contacts operations include "contact", "add contact", "edit contact", "delete contact", "list contacts". '
        'Calendar operations include "schedule delivery", "edit delivery", "delete delivery", or anything about delivery events. '
        'You have a parser agent related to send orders, menu agents to operate on menu items, contacts agents to edit contacts list, and calendar agent to handle delivery calendar. Hand off accordingly.'
        'For example, if the user says "I want to send a quotation to John Doe", you should hand off to the parser agent. '
        'If the user says " send an email or quotation to X@Y.com for Z of item1 and F of item2", you should hand off to the parser agent. '
        'If the user says "I want to add a menu item", you should hand off to the menu agent. '
        'If the user says "I want to add a contact", you should hand off to the contacts agent. '
        'If the user says "I want to schedule a delivery", you should hand off to the calendar agent. '
    ),
    handoffs=[
        handoff(agent=parser_agent, on_handoff=on_handoff_parser),
        handoff(agent=menu_agent, on_handoff=on_handoff_menu),
        handoff(agent=contacts_agent, on_handoff=on_handoff_contacts),
        handoff(agent=calendar_agent, on_handoff=on_handoff_calendar),
    ]
)

# ==============================
# Google Setup Commands
# ==============================

@bot.message_handler(commands=['setup_google'])
def setup_google(message):
    """
    Initiates the Google OAuth setup process through a web interface.
    """
    try:
        # Check if already set up
        is_setup, setup_message = check_google_setup()
        if is_setup:
            bot.reply_to(message, setup_message)
            return

        # Generate OAuth URL
        auth_url = generate_oauth_url()
        
        # Send instructions and URL
        instructions = (
            "To set up Google integration, please follow these steps:\n\n"
            "1. Click the link below to authorize the bot\n"
            "2. Sign in with your Google account\n"
            "3. Grant the requested permissions\n"
            "4. After authorization, you'll be redirected to a page\n"
            "5. Copy the authorization code from the page\n"
            "6. Send the code back to me using /auth_code <code>\n\n"
            f"Authorization link: {auth_url}"
        )
        bot.reply_to(message, instructions)
        
    except Exception as e:
        logger.exception("Error in setup_google")
        bot.reply_to(message, f"Error setting up Google integration: {str(e)}")

@bot.message_handler(commands=['auth_code'])
def handle_auth_code(message):
    """
    Handles the authorization code from the user.
    """
    try:
        # Extract the code from the message
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "Please provide the authorization code in the format: /auth_code <code>")
            return

        auth_code = parts[1]
        
        # Process the auth code
        success, result_message = handle_oauth_callback(auth_code)
        
        if success:
            bot.reply_to(message, result_message)
            # Verify the setup
            is_setup, setup_message = check_google_setup()
            if is_setup:
                bot.send_message(message.chat.id, "Google integration is now ready to use!")
                # Initialize Google services now that authentication is complete
                bot.send_message(message.chat.id, "Initializing Google services...")
                if initialize_google_services():
                    bot.send_message(message.chat.id, "✅ Google services initialized successfully! You can now use all features.")
                else:
                    bot.send_message(message.chat.id, "⚠️ Google services partially initialized. Some features may be limited.")
            else:
                bot.send_message(message.chat.id, "There was an issue with the setup. Please try again.")
        else:
            bot.reply_to(message, f"Authentication failed: {result_message}")
            
    except Exception as e:
        logger.exception("Error in handle_auth_code")
        bot.reply_to(message, f"Error processing authorization code: {str(e)}")

@bot.message_handler(commands=['check_google'])
def check_google(message):
    """
    Checks the status of Google integration.
    """
    try:
        is_setup, setup_message = check_google_setup()
        bot.reply_to(message, setup_message)
    except Exception as e:
        logger.exception("Error in check_google")
        bot.reply_to(message, f"Error checking Google setup: {str(e)}")

# ==============================
# Helper Functions
# ==============================

def get_contacts_str():
    """
    Retrieves the current contacts as a string from Google Drive handler.
    """
    try:
        if gdh:
            logger.info("Fetching contacts from Google Drive.")
            return gdh.list_contacts()
        else:
            logger.warning("Google Drive handler not available; returning empty contacts.")
            return ""
    except Exception as e:
        logger.error(f"Could not fetch contacts: {e}")
        return ""

# ==============================
# Main Message Processing Logic
# ==============================

def process_message(message):
    """
    Processes incoming messages, routes to the correct agent, and handles responses.
    Main processor for agent handoffs and conversation continuity.
    """
    try:
        logger.info(f"Received message from {message.from_user.id}: {message.text}")
        user_id = message.from_user.id

        # Check Google setup for non-setup commands
        if not message.text.startswith(('/setup_google', '/auth_code', '/check_google', '/Greet')):
            is_setup, setup_message = check_google_setup()
            if not is_setup:
                # Proactively send authentication instructions and link
                bot.reply_to(message, setup_message) # Tell them why
                try:
                    # Generate a secure state parameter
                    state = secrets.token_urlsafe(32)
                    oauth_states[state] = user_id
                    
                    # Generate OAuth URL with state
                    auth_url = generate_oauth_url_with_state(state)
                    instructions = (
                        "To use this feature, Google integration is required. Please follow these steps:\n\n"
                        "1. Click the link below to authorize the bot\n"
                        "2. Sign in with your Google account\n"
                        "3. Grant the requested permissions\n"
                        "4. After authorization, you'll be automatically redirected\n"
                        "5. The bot will notify you here when authentication is complete\n\n"
                        f"🔗 Authorization link: {auth_url}\n\n"
                        "⚠️ This link is unique to you and expires in 10 minutes for security."
                    )
                    bot.send_message(message.chat.id, instructions)
                    logger.info(f"Sent proactive OAuth instructions with state to user {user_id}.")
                    
                    # Clean up expired states (older than 10 minutes)
                    threading.Timer(600.0, lambda: oauth_states.pop(state, None)).start()
                    
                except Exception as e:
                    logger.exception(f"Error generating OAuth URL for proactive auth for user {user_id}")
                    bot.send_message(message.chat.id, "Sorry, I couldn't generate the authentication link. Please try running /setup_google manually.")
                return
        
        # Initialize or retrieve user conversation history
        if user_id not in user_histories:
            user_histories[user_id] = []
            active_agent_per_user[user_id] = triage_agent
            
        conversation = user_histories[user_id]
        conversation.append({"role": "user", "content": message.text})
        conversation = conversation[-MAX_HISTORY:]  # Keep history manageable
        
        # Get the currently active agent for this user
        active_agent = active_agent_per_user.get(user_id, triage_agent)
        
        # Only show "processing" for longer operations like quotation generation
        if active_agent == parser_agent:
            bot.send_message(message.chat.id, "Processing your order, please wait...")
            
        logger.info(f"Routing message to agent: {active_agent.name}")
        
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Run the agent using the new event loop
            response = loop.run_until_complete(
                Runner.run(
                    starting_agent=active_agent,
                    input=conversation
                )
            )
            
            # The result contains the agent that actually responded
            active_agent = response.last_agent
            result = response.final_output
            logger.info(f"Agent responded: {active_agent.name}, Result: {result}")
            
            # Update conversation with the full conversation history
            conversation = response.to_input_list()
            user_histories[user_id] = conversation
            
            # Store the active agent for the next turn
            active_agent_per_user[user_id] = active_agent
            
            # Handle special case for parser agent when it returns an Order
            if active_agent == parser_agent and isinstance(result, Order):
                # Special handling for orders with quotation generation
                bot.send_message(message.chat.id, "Processing your order details...")
                logger.info("Processing order for quotation.")
                
                quotation = calculate_quotation(result)
                # Include additional fields in quotation dict
                quotation["email"] = result.email
                quotation["name"] = result.name
                quotation["address"] = result.address
                quotation["date"] = result.date
                
                pdf_path = generate_pdf_quote(quotation)
                
                # Generate summary
                summary = "Your order quotation is ready:\n\n"
                if result.name:
                    summary += f"Customer: {result.name}\n"
                if result.address:
                    summary += f"Address: {result.address}\n"
                current_date = datetime.now().strftime('%Y-%m-%d')  # Fixed datetime usage
                summary += f"Date: {result.date or current_date}\n\n"
                for item in quotation["quotation"]:
                    summary += f"• {item['Item']} x{item['Quantity']} - ${item['Total Price']:.2f}\n"
                summary += f"\nGrand Total: ${quotation['final_total']:.2f}\n"
                summary += f"Send quotation to: {result.email or 'default@example.com'}\n"
                summary += "Confirm? [y/n]"
                
                bot.send_message(message.chat.id, summary)
                logger.info("Quotation summary sent to user.")
                
                # Register confirmation handler
                bot.register_next_step_handler(
                    message,
                    lambda m: confirmation_handler(
                        m,
                        pdf_path,
                        result.email or "default@example.com",
                        quotation
                    )
                )
                # Reset to triage for next conversation after order processing
                active_agent_per_user[user_id] = triage_agent
            else:
                # For all other agents, simply send the response
                # Clean up any meta-descriptions from the output
                clean_output = str(result)
                
                # Remove prefixes that make the conversation feel disjointed
                prefixes_to_remove = [
                    "Contacts operation result: ",
                    "Menu operation result: ",
                    "Calendar agent result: "
                ]
                for prefix in prefixes_to_remove:
                    if clean_output.startswith(prefix):
                        clean_output = clean_output[len(prefix):]
                
                bot.send_message(message.chat.id, clean_output)
                logger.info(f"Sent {active_agent.name} response to user.")
                
                # Keep special agent continuity when needed (calendar agent waiting for more info)
                if active_agent != triage_agent and active_agent != parser_agent:
                    logger.info(f"Keeping {active_agent.name} active for conversation continuity.")
                else:
                    # Otherwise reset to triage for next conversation
                    active_agent_per_user[user_id] = triage_agent
                    logger.info("Resetting to Triage agent for next turn.")
        finally:
            # Clean up the event loop
            loop.close()
                
    except Exception as e:
        logger.exception("Error processing message")
        bot.send_message(message.chat.id, f"Sorry, there was an error: {str(e)}")
        # Reset to triage after errors
        if user_id in active_agent_per_user:
            active_agent_per_user[user_id] = triage_agent

# ==============================
# Fallback Message Handler
# ==============================

@bot.message_handler(func=lambda m: True)
def handle_message(m):
    """
    Handles all incoming messages not caught by other handlers.
    """
    try:
        logger.info(f"Handling message from user {m.from_user.id}")
        # Start a new thread for each message to avoid blocking
        threading.Thread(target=process_message, args=(m,)).start()
    except Exception as e:
        logger.exception("Error in handle_message")

# ==============================
# Bot Polling Entry Point
# ==============================

bot.polling()
print("Bot is running...")