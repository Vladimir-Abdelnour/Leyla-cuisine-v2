import os
import pickle
import logging
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# The Calendar API scope.
SCOPES = ['https://www.googleapis.com/auth/calendar']

logger = logging.getLogger(__name__)

def get_credentials():
    """Obtain valid user credentials from storage or run OAuth2 flow."""
    creds = None
    token_file = 'token_calendar.pickle'
    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            creds = pickle.load(token)
        # If stored credentials don't include the required scopes, force a new login.
        if not set(SCOPES).issubset(set(creds.scopes)):
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Use the login_hint to enforce using vladimirabdelnour00@gmail.com
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0, login_hint="vladimirabdelnour00@gmail.com")
        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)
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
        event_body = {
            'summary': summary,
            'location': address,
            'description': description,
            'start': {
                'dateTime': start_datetime,
                'timeZone': 'America/New_York',
            },
            'end': {
                'dateTime': end_datetime,
                'timeZone': 'America/New_York',
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
            event_body['start'] = {'dateTime': start_datetime, 'timeZone': 'America/New_York'}
        if end_datetime:
            event_body['end'] = {'dateTime': end_datetime, 'timeZone': 'America/New_York'}
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
