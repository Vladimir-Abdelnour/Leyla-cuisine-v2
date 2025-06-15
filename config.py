"""
Configuration settings for Leyla Cuisine Bot.
This file contains all the configuration settings and credentials needed to run the bot.
"""

import os
import json
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

# Telegram Bot Configuration
TELEGRAM_API_KEY = os.getenv('TELEGRAM_API_KEY')

# Google API Configuration
GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'https://conversation.ngrok.app/oauth2callback')
GOOGLE_EMAIL = os.getenv('GOOGLE_EMAIL')

# Function to load Google credentials from credentials.json
def load_google_credentials():
    """
    Load Google client ID and secret from credentials.json file.
    Returns (client_id, client_secret) tuple or (None, None) if file doesn't exist or is invalid.
    """
    try:
        if os.path.exists(GOOGLE_CREDENTIALS_FILE):
            with open(GOOGLE_CREDENTIALS_FILE, 'r') as f:
                creds_data = json.load(f)
                
            # Check for different credential formats
            if 'installed' in creds_data:
                # Desktop application format
                client_id = creds_data['installed'].get('client_id')
                client_secret = creds_data['installed'].get('client_secret')
            elif 'web' in creds_data:
                # Web application format
                client_id = creds_data['web'].get('client_id')
                client_secret = creds_data['web'].get('client_secret')
            else:
                # Direct format
                client_id = creds_data.get('client_id')
                client_secret = creds_data.get('client_secret')
                
            return client_id, client_secret
        else:
            return None, None
    except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
        logging.error(f"Error loading Google credentials from {GOOGLE_CREDENTIALS_FILE}: {e}")
        return None, None

# Load Google credentials
GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET = load_google_credentials()

# Fallback to environment variables if not found in credentials.json
if not GOOGLE_CLIENT_ID:
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
if not GOOGLE_CLIENT_SECRET:
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

# Email Configuration
DEFAULT_SENDER_EMAIL = os.getenv('DEFAULT_SENDER_EMAIL')
DEFAULT_RECIPIENT_EMAIL = os.getenv('DEFAULT_RECIPIENT_EMAIL')

# File Paths
TOKEN_FILES = {
    'drive': os.getenv('DRIVE_TOKEN_FILE', 'token_drive.pickle'),
    'calendar': os.getenv('CALENDAR_TOKEN_FILE', 'token_calendar.pickle'),
    'gmail': os.getenv('GMAIL_TOKEN_FILE', 'token.pickle')
}

# Google Drive Configuration
DRIVE_CONFIG = {
    'ROOT_FOLDER_NAME': 'Leyla Cuisine',
    'MENU_SHEET_TITLE': 'Menu',
    'CONTACTS_SHEET_TITLE': 'Contacts',
    'SALES_FOLDER_TITLE': 'Sales'
}

# Calendar Configuration
CALENDAR_CONFIG = {
    'TIMEZONE': 'America/New_York',
    'DEFAULT_CALENDAR_ID': 'primary'
}

def validate_config():
    """
    Validates that all required configuration values are present.
    Raises ValueError if any required values are missing.
    """
    required_vars = [
        ('TELEGRAM_API_KEY', TELEGRAM_API_KEY),
        ('GOOGLE_EMAIL', GOOGLE_EMAIL),
        ('DEFAULT_SENDER_EMAIL', DEFAULT_SENDER_EMAIL)
    ]
    
    missing = [var for var, val in required_vars if not val]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    # Check if credentials file exists
    if not os.path.exists(GOOGLE_CREDENTIALS_FILE):
        logging.warning(
            f"Google credentials file not found at {GOOGLE_CREDENTIALS_FILE}. "
            "The bot will prompt users to set up Google integration when needed."
        )
        return
    
    # Check if Google credentials are available
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        logging.warning(
            f"Google client ID or secret not found in {GOOGLE_CREDENTIALS_FILE} or environment variables. "
            "The bot will prompt users to set up Google integration when needed."
        )
        return
    
    logging.info("Configuration validation completed successfully.") 