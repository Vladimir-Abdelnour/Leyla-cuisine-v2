"""
Google OAuth Setup Handler for Leyla Cuisine Bot.
Handles the OAuth flow through a web interface.
"""

import os
import json
import logging
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import pickle
from config import TOKEN_FILES, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI

logger = logging.getLogger(__name__)

# OAuth 2.0 scopes needed
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.send'
]

def get_client_config():
    """
    Get the client configuration for OAuth flow.
    Returns the client config dictionary.
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise ValueError(
            "Google client ID and/or secret not found. "
            "Please ensure your credentials.json file is properly configured "
            "or set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables."
        )
    
    return {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [GOOGLE_REDIRECT_URI]
        }
    }

def check_google_setup():
    """
    Checks if Google credentials are properly set up.
    Returns (bool, str) tuple: (is_setup, message)
    """
    try:
        # First check if we have client credentials
        get_client_config()
    except ValueError as e:
        return False, str(e)
    
    # Check if any token files exist
    has_tokens = any(os.path.exists(token_file) for token_file in TOKEN_FILES.values())
    if not has_tokens:
        return False, "Google authentication required. Please use /setup_google to start the setup process."

    # Check if tokens are valid
    try:
        for token_file in TOKEN_FILES.values():
            if os.path.exists(token_file):
                with open(token_file, 'rb') as token:
                    creds = pickle.load(token)
                if not creds.valid and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    with open(token_file, 'wb') as token:
                        pickle.dump(creds, token)
        return True, "Google authentication is set up and valid."
    except Exception as e:
        logger.error(f"Error checking Google setup: {e}")
        return False, "Google authentication error. Please use /setup_google to re-authenticate."

def generate_oauth_url_with_state(state):
    """
    Generates the OAuth URL for Google authentication with a specific state parameter.
    Returns the authorization URL.
    """
    try:
        client_config = get_client_config()
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=client_config['web']['redirect_uris'][0]
        )
        
        # Generate URL for request with state
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state=state
        )
        
        return auth_url
    except Exception as e:
        logger.error(f"Error generating OAuth URL with state: {e}")
        raise

def generate_oauth_url():
    """
    Generates the OAuth URL for Google authentication.
    Returns the authorization URL.
    """
    try:
        client_config = get_client_config()
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=client_config['web']['redirect_uris'][0]
        )
        
        # Generate URL for request
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        return auth_url
    except Exception as e:
        logger.error(f"Error generating OAuth URL: {e}")
        raise

def handle_oauth_callback(auth_code):
    """
    Handles the OAuth callback with the authorization code.
    Saves the credentials to token files.
    """
    try:
        client_config = get_client_config()
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=client_config['web']['redirect_uris'][0]
        )
        
        # Exchange auth code for credentials
        flow.fetch_token(code=auth_code)
        credentials = flow.credentials
        
        # Save credentials for each service
        for service, token_file in TOKEN_FILES.items():
            with open(token_file, 'wb') as token:
                pickle.dump(credentials, token)
        
        return True, "Google authentication completed successfully!"
    except Exception as e:
        logger.error(f"Error handling OAuth callback: {e}")
        return False, f"Error during authentication: {str(e)}" 