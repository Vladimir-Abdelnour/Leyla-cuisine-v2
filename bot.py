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
import datetime

# ==============================
# Global State and Bot Setup
# ==============================

user_states = {}  # user_id -> state dict

# Load environment variables
load_dotenv()

API_KEY = os.getenv("TELEGRAM_API_KEY")
if not API_KEY:
    raise ValueError("TELEGRAM_API_KEY is not set in environment variables.")

# Initialize Telegram bot
bot = telebot.TeleBot(API_KEY)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================
# Google Drive Handler Setup
# ==============================

gdh = None
DRIVE_IDS = None
menu = {}
menu_items_str = ""
try:
    import google_handlers.google_drive_handler as gdh
    from google_handlers.google_drive_handler import append_contact
    DRIVE_IDS = gdh.DRIVE
    # Attempt to load menu from Google Drive
    try:
        menu = gdh.load_menu()
        menu_items_str = '", "'.join(menu.keys())
        menu_items_str = f'"{menu_items_str}"'
        logger.info("Menu loaded successfully from Google Drive.")
    except Exception as e:
        logger.error(f"Could not load menu from Google Drive: {e}")
        menu = {}
        menu_items_str = ""
except Exception as e:
    logger.error(f"Could not import Google Drive handler: {e}")
    gdh = None
    DRIVE_IDS = None
    menu = {}
    menu_items_str = ""

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
                from tools_handler import save_approved_quotation
                saved_path = save_approved_quotation(pdf_path)
                bot.send_message(message.chat.id, f"Approved quotation saved as {saved_path}.")
                if gdh:
                    try:
                        gdh.append_contact(message.from_user.first_name, recipient_email)
                        gdh.record_sales(quotation)
                        logger.info("Contact appended and sales recorded in Google Drive.")
                    except Exception as e:
                        logger.error(f"Drive operation failed: {e}")
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
            summary = "Delivery for order"
            address = None  # Let the agent resolve via list_contacts if needed
            description = "Delivery for approved catering order."
            prompt = (
                f"Schedule a delivery event for {client_email}. "
                f"Order details: {quotation}. "
                "If you need the address, use the client list."
            )
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(Runner.run(calendar_agent, prompt))
            bot.send_message(message.chat.id, f"Calendar agent result: {result.final_output}")
            logger.info("Calendar event scheduled.")
        else:
            bot.send_message(message.chat.id, "No calendar event scheduled.")
            logger.info("User declined calendar scheduling.")
    except Exception as e:
        logger.exception("Error in handle_calendar_after_approval")
        bot.send_message(message.chat.id, f"An error occurred: {str(e)}")

# ==============================
# Agent Definitions
# ==============================

# Parser agent for orders
parser_agent = Agent(
    name='order_parser',
    model='gpt-4o',
    instructions=(
        'You are a helpful assistant that parses the user input and returns a JSON object matching '
        '{"email": "customer@example.com", "items": [{"name": "Margherita Pizza", "quantity": 1}], '
        '"discount": "10%" or 10, "delivery": true, "tax_rate": 8.1}. '
        f'Here is the menu list: {menu_items_str}.'
    ),
    output_type=tl.Order,
)

menu_agent: Agent[tl.Menu_item] = Agent[tl.Menu_item](
    name="Menu agent",
    model='gpt-4o',
    instructions=(
        'You are a menu management agent that can add, edit, list, or delete menu items. '
        'Use the Menu_item structure for input and output a message describing what you did. '
        f'Current menu: {menu_items_str}.'
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
            "If the user provides a client name but not an address, use the list_contacts tool to find the address. "
            "If the name is not found, ask the user to try again with a valid client name. "
            "If the user asks to schedule a delivery after a quotation is approved, use the order's email/name to look up the address. "
            "Always confirm the event details with the user before creating or editing events.\n"
        "YOur current timezone is Mountain Time Zone of North America UTC-7 "
        f"and the current time is {datetime.datetime.now()}"
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
        'Menu operations include "menu", "add", "edit", "delete" for menu items. '
        'Contacts operations include "contact", "add contact", "edit contact", "delete contact", "list contacts". '
        'Calendar operations include "schedule delivery", "edit delivery", "delete delivery", or anything about delivery events. '
        'Orders include an email or item quantities. '
        'You have a parser agent related to send orders, menu agents to operate on menu items, contacts agents to edit contacts list, and calendar agent to handle delivery calendar. Hand off accordingly.'
    ),
    handoffs=[
        handoff(agent=parser_agent, on_handoff=on_handoff_parser),
        handoff(agent=menu_agent, on_handoff=on_handoff_menu),
        handoff(agent=contacts_agent, on_handoff=on_handoff_contacts),
        handoff(agent=calendar_agent, on_handoff=on_handoff_calendar),
    ]
)

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
        
        # Run the agent synchronously using the OpenAI agents SDK method
        response = Runner.run_sync(
            starting_agent=active_agent,
            input=conversation
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
            pdf_path = generate_pdf_quote(quotation)
            
            # Include email in quotation dict
            quotation["email"] = result.email
            
            # Generate summary
            summary = "Your order quotation is ready:\n\n"
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

# ==============================
# End of File
# ==============================