"""
Configuration settings for Leyla Cuisine Bot.
This file contains all the configuration settings and credentials needed to run the bot.
"""

import os
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

# Telegram Bot Configuration
TELEGRAM_API_KEY = os.getenv('TELEGRAM_API_KEY')

# Google API Configuration
GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')
GOOGLE_EMAIL = os.getenv('GOOGLE_EMAIL')

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
        ('GOOGLE_CREDENTIALS_FILE', GOOGLE_CREDENTIALS_FILE),
        ('GOOGLE_EMAIL', GOOGLE_EMAIL),
        ('DEFAULT_SENDER_EMAIL', DEFAULT_SENDER_EMAIL)
    ]
    
    missing = [var for var, val in required_vars if not val]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    # Check if credentials file exists
    if not os.path.exists(GOOGLE_CREDENTIALS_FILE):
        # Instead of raising an error, just log a warning
        logging.warning(
            f"Google credentials file not found at {GOOGLE_CREDENTIALS_FILE}. "
            "The bot will prompt users to set up Google integration when needed."
        )
        return
    
    # Check if credentials file is valid
    if not os.path.exists(GOOGLE_CREDENTIALS_FILE):
        raise FileNotFoundError(
            f"Google credentials file not found at {GOOGLE_CREDENTIALS_FILE}. "
            "Please download your credentials.json from Google Cloud Console "
            "and place it in the project root directory."
        ) 