"""
Google Calendar Handler for Leyla Cuisine Bot.
Handles calendar operations for delivery scheduling.
"""

import os
import pickle
import logging
from datetime import datetime, timezone, timedelta
import pytz
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from config import TOKEN_FILES, CALENDAR_CONFIG

# The Calendar API scope.
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Get the project root directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_FILE = os.path.join(PROJECT_ROOT, 'credentials.json')
TOKEN_FILE = os.path.join(PROJECT_ROOT, 'token_calendar.pickle')

# Timezone settings
TIMEZONE = 'America/Phoenix'  # Mountain Time
mt_tz = pytz.timezone(TIMEZONE)

logger = logging.getLogger(__name__)

def get_credentials():
    """Obtain valid user credentials from storage or run OAuth2 flow."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
        # If stored credentials don't include the required scopes, force a new login.
        if creds and not set(SCOPES).issubset(set(creds.scopes)):
            creds = None # Invalidate creds to force re-auth via /setup_google
            try:
                os.remove(TOKEN_FILE) # Remove the old token file with insufficient scopes
                logger.info(f"Removed token file {TOKEN_FILE} due to insufficient scopes.")
            except OSError as e:
                logger.error(f"Error removing token file {TOKEN_FILE}: {e}")

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    # Save the refreshed credentials
                    with open(TOKEN_FILE, 'wb') as token:
                        pickle.dump(creds, token)
                    logger.info(f"Refreshed and saved credentials to {TOKEN_FILE}")
                except Exception as e: # Catch broader exceptions during refresh, e.g., RefreshError
                    logger.error(f"Failed to refresh token: {e}. Deleting problematic token file {TOKEN_FILE}.")
                    if os.path.exists(TOKEN_FILE):
                        try:
                            os.remove(TOKEN_FILE)
                        except OSError as e_remove:
                            logger.error(f"Error removing token file {TOKEN_FILE}: {e_remove}")
                    creds = None # Ensure creds is None if refresh fails
            else:
                creds = None # Credentials are not valid and cannot be refreshed

    if not creds:
        # If credentials are still not available or valid,
        # direct the user to the bot's setup command.
        raise RuntimeError(
            "Google Calendar authentication required or token is invalid/expired. "
            "Please use the /setup_google command in the Telegram bot to authorize."
        )
    return creds

def get_calendar_service():
    creds = get_credentials()
    service = build('calendar', 'v3', credentials=creds)
    return service

def create_event(event_body, calendar_id='primary'):
    """Create a new calendar event."""
    service = get_calendar_service()
    event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
    print("Event created: %s" % event.get('htmlLink'))
    return event

def update_event(event_id, event_body, calendar_id='primary'):
    """Update an existing calendar event."""
    service = get_calendar_service()
    event = service.events().patch(calendarId=calendar_id, eventId=event_id, body=event_body).execute()
    print("Event updated: %s" % event.get('htmlLink'))
    return event

def delete_event(event_id, calendar_id='primary'):
    """Delete a calendar event."""
    service = get_calendar_service()
    service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
    print("Event deleted")
    return True

def validate_datetime(dt_str: str) -> str:
    """
    Validates and formats datetime string to ensure it's in the future and properly formatted.
    Returns ISO format string in Mountain Time.
    """
    try:
        # Parse the input datetime
        dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
        
        # If year is not 2025, update it
        if dt.year != 2025:
            dt = dt.replace(year=2025)
        
        # Localize to Mountain Time
        dt = mt_tz.localize(dt)
        
        # Check if the date is in the future
        now = datetime.now(mt_tz)
        if dt < now:
            raise ValueError("Cannot schedule events in the past")
        
        # Return ISO format string
        return dt.isoformat()
    except ValueError as e:
        logger.error(f"Invalid datetime format or past date: {e}")
        raise

def create_delivery_event(
    summary: str,
    address: str,
    description: str,
    start_datetime: str,
    end_datetime: str,
    attendees: list = None,
    calendar_id: str = 'primary'
) -> dict:
    """
    Create a calendar event for a delivery.
    """
    try:
        # Validate and format datetimes
        start_dt = validate_datetime(start_datetime)
        end_dt = validate_datetime(end_datetime)
        
        event_body = {
            'summary': summary,
            'location': address,
            'description': description,
            'start': {
                'dateTime': start_dt,
                'timeZone': TIMEZONE,
            },
            'end': {
                'dateTime': end_dt,
                'timeZone': TIMEZONE,
            },
            'attendees': attendees or [],
            'reminders': {'useDefault': True},
        }
        return create_event(event_body, calendar_id)
    except Exception as e:
        logger.exception("Error creating delivery event")
        raise

def edit_delivery_event(
    event_id: str,
    summary: str = None,
    address: str = None,
    description: str = None,
    start_datetime: str = None,
    end_datetime: str = None,
    calendar_id: str = 'primary'
) -> dict:
    """
    Edit an existing delivery event.
    """
    try:
        event_body = {}
        if summary: event_body['summary'] = summary
        if address: event_body['location'] = address
        if description: event_body['description'] = description
        if start_datetime:
            start_dt = validate_datetime(start_datetime)
            event_body['start'] = {'dateTime': start_dt, 'timeZone': TIMEZONE}
        if end_datetime:
            end_dt = validate_datetime(end_datetime)
            event_body['end'] = {'dateTime': end_dt, 'timeZone': TIMEZONE}
        return update_event(event_id, event_body, calendar_id)
    except Exception as e:
        logger.exception("Error editing delivery event")
        raise

def delete_delivery_event(event_id: str, calendar_id: str = 'primary') -> bool:
    """
    Delete a delivery event by event_id.
    """
    try:
        return delete_event(event_id, calendar_id)
    except Exception as e:
        logger.exception("Error deleting delivery event")
        raise

if __name__ == "__main__":
    # Example usage:
    event_body = {
        'summary': 'Meeting with Client',
        'location': '123 Main St, City, Country',
        'description': 'Discuss project details.',
        'start': {
            'dateTime': '2025-03-30T09:00:00',
            'timeZone': 'America/New_York',
        },
        'end': {
            'dateTime': '2025-03-30T10:00:00',
            'timeZone': 'America/New_York',
        },
        'attendees': [
            {'email': 'vladimirabdelnour00@gmail.com'},
        ],
        'reminders': {
            'useDefault': True,
        },
    }
    
    # Create an event.
    created_event = create_event(event_body)
    event_id = created_event.get('id')
    
    # Update the event (for example, change the summary).
    updated_body = {'summary': 'Updated Meeting with Client'}
    update_event(event_id, updated_body)
    
    # To delete the event, uncomment the following line:
    # delete_event(event_id)
