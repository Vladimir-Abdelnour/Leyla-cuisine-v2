"""
Email Handler for Leyla Cuisine Bot.
Handles sending quotations via Gmail API.
"""

import os
import pickle
import logging
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from config import TOKEN_FILES, DEFAULT_SENDER_EMAIL

logger = logging.getLogger(__name__)

# The Gmail API scope for sending messages.
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

# Filenames for OAuth2 credentials and token
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.pickle'

def get_gmail_service():
    """
    Obtains a Gmail API service using OAuth2 credentials.
    If the saved token is invalid, expired, or revoked, deletes it and regenerates.
    """
    creds = None

    # Load existing credentials, if available
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token_file:
            creds = pickle.load(token_file)

    # If no valid credentials, or they need refresh/re‑auth
    if not creds or not creds.valid:
        # Try refreshing, if possible
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                # Token is no longer valid. Remove it and start over.
                os.remove(TOKEN_FILE)
                creds = None

        # If there are still no valid creds, run the OAuth flow
        if not creds:
            raise RuntimeError(
                "Google authentication required. Please use /setup_google in the Telegram bot to set up Google integration."
            )

    # Build the Gmail service
    return build('gmail', 'v1', credentials=creds)


def send_quotation_email(
    pdf_path: str,
    sender_email: str = "vladimirabdelnour00@gmail.com",
    recipient_email: str = "vabdelno@asu.edu",
    subject: str = "Quotation PDF",
    body: str = None
) -> bool:
    """
    Sends the generated PDF quotation via Gmail API using OAuth2.
    Returns True on success, False otherwise.
    """
    try:
        print(f"Attempting to send email from {sender_email} to {recipient_email}")
        print(f"PDF path: {pdf_path}")

        # Verify PDF exists.
        if not os.path.exists(pdf_path):
            print(f"Error: PDF file not found at {pdf_path}")
            return False

        if body is None:
            body = (
                "Dear Valued Client,\n\n"
                "Please find attached the quotation document as requested. We appreciate the opportunity "
                "to serve your needs and hope our proposal meets your expectations.\n\n"
                "Should you have any questions or require further clarification, please do not hesitate to contact me.\n\n"
                "Thank you for your business.\n\n"
                "Best regards,\n"
                "Khaykon el Gergy\n"
            )

        # Build the MIME message
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = recipient_email
        message['Subject'] = subject
        message.attach(MIMEText(body, 'plain'))

        # Attach the PDF file
        try:
            with open(pdf_path, 'rb') as f:
                part = MIMEApplication(f.read(), _subtype='pdf')
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{os.path.basename(pdf_path)}"'
                )
                message.attach(part)
        except Exception as e:
            print(f"Error attaching PDF: {e}")
            return False

        # Send via Gmail API
        try:
            print("Getting Gmail service...")
            service = get_gmail_service()
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            send_request = {'raw': raw}

            print("Sending email via Gmail API...")
            sent = service.users().messages().send(userId="me", body=send_request).execute()
            print(f"Email sent successfully! Message ID: {sent['id']}")
            return True

        except Exception as e:
            print(f"Failed to send email. Detailed error: {e}")
            return False

    except Exception as e:
        logger.exception("Failed to send email")
        return False


if __name__ == "__main__":
    # Example usage
    pdf_file = "quotation.pdf"
    success = send_quotation_email(pdf_file)
    print("Send status:", success)
