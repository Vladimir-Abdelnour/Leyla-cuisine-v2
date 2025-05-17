# google_handlers/google_drive_handler.py

import os
import pickle
import logging
from datetime import datetime
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

# Scopes
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token_drive.pickle"

# Drive titles
ROOT_FOLDER_NAME = "Leyla Cuisine"
MENU_SHEET_TITLE = "Menu"
CONTACTS_SHEET_TITLE = "Contacts"
SALES_FOLDER_TITLE = "Sales"

MENU_HEADERS = ["Item", "Category", "Price", "Description"]
CONTACTS_HEADERS = ["Name", "Email", "Phone", "Address"]
MONTHLY_SALES_HEADERS = ["Item", "Quantity", "Total Sales"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_credentials():
    """
    Obtains Google API credentials, refreshing or creating as needed.
    """
    try:
        creds = None
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "rb") as f:
                creds = pickle.load(f)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except RefreshError:
                    os.remove(TOKEN_FILE)
                    creds = None
            if not creds:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
                with open(TOKEN_FILE, "wb") as f:
                    pickle.dump(creds, f)
        return creds
    except Exception as e:
        logger.exception("Error getting Google credentials")
        raise


def get_drive_service():
    logger.info("Getting Google Drive service...")
    creds = get_credentials()
    return build('drive', 'v3', credentials=creds, cache_discovery=False)


def get_sheets_service():
    logger.info("Getting Google Sheets service...")
    return build("sheets", "v4", credentials=get_credentials())


def find_file(name: str, mime: str, parent_id: str = None) -> str:
    svc = get_drive_service()
    q = f"name='{name}' and mimeType='{mime}' and trashed=false"
    if parent_id:
        q += f" and '{parent_id}' in parents"
    files = svc.files().list(q=q, fields="files(id)").execute().get("files", [])
    return files[0]["id"] if files else None


def create_folder(name: str, parent_id: str = None) -> str:
    folder_mime = "application/vnd.google-apps.folder"
    existing = find_file(name, folder_mime, parent_id)
    if existing:
        return existing
    body = {"name": name, "mimeType": folder_mime}
    if parent_id:
        body["parents"] = [parent_id]
    return get_drive_service().files().create(body=body, fields="id").execute()["id"]


def create_sheet(title: str, parent_id: str, headers: list) -> str:
    sheets = get_sheets_service()
    body = {
        "properties": {"title": title},
        "sheets": [{
            "properties": {"title": "Sheet1"},
            "data": [{
                "rowData": [{
                    "values": [{"userEnteredValue": {"stringValue": h}} for h in headers]
                }]
            }]
        }]
    }
    ss = sheets.spreadsheets().create(body=body, fields="spreadsheetId").execute()
    sid = ss["spreadsheetId"]
    drive = get_drive_service()
    parents = ",".join(drive.files().get(fileId=sid, fields="parents").execute()["parents"])
    drive.files().update(
        fileId=sid,
        addParents=parent_id,
        removeParents=parents,
        fields="id,parents"
    ).execute()
    return sid


def append_row(sheet_id: str, row: list, sheet_name: str = "Sheet1"):
    return get_sheets_service().spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=sheet_name,
        valueInputOption="USER_ENTERED",
        body={"values": [row]}
    ).execute()


def read_rows(sheet_id: str, sheet_name: str = "Sheet1") -> list:
    return get_sheets_service().spreadsheets().values().get(
        spreadsheetId=sheet_id, range=sheet_name
    ).execute().get("values", [])


def check_or_create_structure() -> dict:
    logger.info("Checking or creating Google Drive structure...")
    root = create_folder(ROOT_FOLDER_NAME)
    logger.info(f"Root folder ID: {root}")
    menu = find_file(MENU_SHEET_TITLE, "application/vnd.google-apps.spreadsheet", root) \
           or create_sheet(MENU_SHEET_TITLE, root, MENU_HEADERS)
    logger.info(f"Menu sheet ID: {menu}")
    contacts = find_file(CONTACTS_SHEET_TITLE, "application/vnd.google-apps.spreadsheet", root) \
               or create_sheet(CONTACTS_SHEET_TITLE, root, CONTACTS_HEADERS)
    logger.info(f"Contacts sheet ID: {contacts}")
    sales_folder = create_folder(SALES_FOLDER_TITLE, root)
    logger.info(f"Sales folder ID: {sales_folder}")
    return {
        "menu_sheet_id": menu,
        "contacts_sheet_id": contacts,
        "sales_folder_id": sales_folder
    }


DRIVE = check_or_create_structure()


def load_menu() -> dict:
    """
    Loads the menu from Google Sheets.
    Returns a dictionary of menu items.
    """
    try:
        rows = read_rows(DRIVE["menu_sheet_id"])
        menu = {}
        for r in rows[1:]:
            if not r: continue
            name, cat, price, desc = (r + ["", "", "", ""])[:4]
            menu[name] = {"Category": cat, "Price": float(price), "Description": desc}
        return menu
    except Exception as e:
        logger.exception("Error loading menu")
        raise


def add_menu_item(item) -> str:
    append_row(DRIVE["menu_sheet_id"],
               [item.Item, item.Category, str(item.Price), item.Description or ""])
    return f"Added {item.Item}."


def delete_menu_item(item_name: str) -> str:
    rows = read_rows(DRIVE["menu_sheet_id"])
    for idx, r in enumerate(rows[1:], start=2):
        if r and r[0] == item_name:
            sid = DRIVE["menu_sheet_id"]
            meta = get_sheets_service().spreadsheets().get(
                spreadsheetId=sid, fields="sheets.properties"
            ).execute()
            sheet_id = next(s["properties"]["sheetId"]
                            for s in meta["sheets"]
                            if s["properties"]["title"] == "Sheet1")
            req = {
                "requests": [{
                    "deleteDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": idx - 1,
                            "endIndex": idx
                        }
                    }
                }]
            }
            get_sheets_service().spreadsheets().batchUpdate(
                spreadsheetId=sid, body=req
            ).execute()
            return f"Deleted {item_name}."
    return f"{item_name} not found."


def edit_menu_item(item) -> str:
    delete_menu_item(item.Item)
    return add_menu_item(item)


def list_menu_items() -> str:
    menu = load_menu()
    return "\n".join(f"{n}: ${v['Price']:.2f} ({v['Category']})"
                     for n, v in menu.items())


def append_contact(name: str, email: str, phone: str = "", address: str = "") -> bool:
    rows = read_rows(DRIVE["contacts_sheet_id"])
    for r in rows[1:]:
        if len(r) > 1 and r[1].lower() == email.lower():
            return False
    append_row(DRIVE["contacts_sheet_id"], [name, email, phone, address])
    return True


def list_contacts() -> str:
    rows = read_rows(DRIVE["contacts_sheet_id"])
    if len(rows) <= 1:
        return "No contacts found."
    contacts = []
    for r in rows[1:]:
        name, email, phone, address = (r + ["", "", "", ""])[:4]
        contacts.append(f"Name: {name}, Email: {email}, Phone: {phone}, Address: {address}")
    return "\n".join(contacts)


def edit_contact(name: str, email: str, phone: str = "", address: str = "") -> bool:
    """
    Edit a contact by email. If found, update the row with new values.
    """
    rows = read_rows(DRIVE["contacts_sheet_id"])
    svc = get_sheets_service()
    sid = DRIVE["contacts_sheet_id"]
    meta = svc.spreadsheets().get(spreadsheetId=sid, fields="sheets.properties").execute()
    sheet_id = next(s["properties"]["sheetId"]
                    for s in meta["sheets"]
                    if s["properties"]["title"] == "Sheet1")
    for idx, r in enumerate(rows[1:], start=2):
        if len(r) > 1 and r[1].lower() == email.lower():
            # Update the row
            svc.spreadsheets().values().update(
                spreadsheetId=sid,
                range=f"Sheet1!A{idx}:D{idx}",
                valueInputOption="USER_ENTERED",
                body={"values": [[name, email, phone, address]]}
            ).execute()
            return True
    return False


def delete_contact(name: str = None, email: str = None, phone: str = None) -> bool:
    """Delete a contact by name, email, or phone."""
    sheet_id = DRIVE["contacts_sheet_id"]
    rows = read_rows(sheet_id)
    found = False
    for idx, row in enumerate(rows[1:], start=2):  # skip header
        row_name = row[0] if len(row) > 0 else ""
        row_email = row[1] if len(row) > 1 else ""
        row_phone = row[2] if len(row) > 2 else ""
        if (
            (name and row_name and row_name.strip().lower() == name.strip().lower()) or
            (email and row_email and row_email.strip().lower() == email.strip().lower()) or
            (phone and row_phone and row_phone.strip() == phone.strip())
        ):
            # Delete the row using batchUpdate
            get_sheets_service().spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body={
                    "requests": [
                        {
                            "deleteDimension": {
                                "range": {
                                    "sheetId": 0,
                                    "dimension": "ROWS",
                                    "startIndex": idx - 1,
                                    "endIndex": idx
                                }
                            }
                        }
                    ]
                }
            ).execute()
            found = True
            break
    return found


def record_sales(quotation: dict) -> bool:
    now = datetime.now()
    title = now.strftime("Sales_%Y_%m")
    sid = find_file(title, "application/vnd.google-apps.spreadsheet", DRIVE["sales_folder_id"]) \
          or create_sheet(title, DRIVE["sales_folder_id"], MONTHLY_SALES_HEADERS)
    rows = read_rows(sid)
    svc = get_sheets_service()
    meta = svc.spreadsheets().get(spreadsheetId=sid, fields="sheets.properties").execute()
    sheet_id = next(s["properties"]["sheetId"]
                    for s in meta["sheets"]
                    if s["properties"]["title"] == "Sheet1")
    for line in quotation["quotation"]:
        name, qty, tot = line["Item"], line["Quantity"], line["Total Price"]
        for idx, r in enumerate(rows[1:], start=2):
            if r and r[0] == name:
                old_qty, old_tot = float(r[1]), float(r[2])
                svc.spreadsheets().values().update(
                    spreadsheetId=sid,
                    range=f"Sheet1!A{idx}:C{idx}",
                    valueInputOption="USER_ENTERED",
                    body={"values": [[name, old_qty+qty, old_tot+tot]]}
                ).execute()
                break
        else:
            append_row(sid, [name, qty, tot])
    return True
