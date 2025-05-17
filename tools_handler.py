# tools_handler.py

import csv
import difflib
import os
import asyncio
import logging

from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from fpdf import FPDF
from agents import function_tool, RunContextWrapper
from pydantic import BaseModel
from enum import Enum

import google_handlers.google_drive_handler as gdh  # <-- updated import path

logger = logging.getLogger(__name__)

MENU_CSV_PATH = "data/menu.csv"  # unused now, kept for backward compatibility

# --- Models ---

class OrderItem(BaseModel):
    """
    Represents an item in an order.
    """
    name: str
    quantity: int

class Order(BaseModel):
    """
    Represents a customer order.
    """
    email: Optional[str]
    items: List[OrderItem]
    discount: Optional[Union[str, float]]
    delivery: Optional[bool]
    tax_rate: Optional[float] = None

class CategoryEnum(str, Enum):
    appetizers = "appetizers"
    salad = "salad"
    main_dish = "main dish"
    deserts = "deserts"

class Menu_item(BaseModel):
    Item: str
    Price: float
    Category: CategoryEnum
    Description: Optional[str] = None

class Contact(BaseModel):
    Name: str
    Email: str
    Phone: Optional[str] = None
    Address: Optional[str] = None

from pydantic import BaseModel
from typing import Optional, List

class DeliveryEvent(BaseModel):
    """
    Represents a delivery event for the calendar.
    """
    summary: str
    address: str
    description: Optional[str]
    start_datetime: str  # ISO format
    end_datetime: str    # ISO format
    attendees: Optional[List[str]] = None
    event_id: Optional[str] = None  # For editing/deleting

# --- MENU via Drive ---

def load_menu() -> Dict[str, Dict[str, Any]]:
    return gdh.load_menu()

# --- QUOTATION & PDF (unchanged) ---

def calculate_quotation(order: Order) -> Dict[str, Any]:
    """
    Calculates the quotation for a given order.
    Returns a dictionary with line items and totals.
    """
    try:
        menu = load_menu()
        subtotal = 0.0
        lines = []
        for oi in order.items:
            name, qty = oi.name, oi.quantity
            item = menu.get(name)
            if not item:
                matches = difflib.get_close_matches(name, menu.keys(), n=1, cutoff=0.6)
                if not matches:
                    raise ValueError(f"Item '{name}' not found.")
                item = menu[matches[0]]
            unit = item["Price"]
            total = unit * qty
            subtotal += total
            lines.append({
                "Item": name,
                "Quantity": qty,
                "Unit Price": unit,
                "Total Price": total,
                "Category": item["Category"]
            })
        discount = 0.0
        if order.discount:
            if isinstance(order.discount, str) and order.discount.endswith("%"):
                p = float(order.discount.strip("%")) / 100
                discount = subtotal * p
            else:
                discount = float(order.discount)
        adjusted = subtotal - discount
        tax = adjusted * ((order.tax_rate or 8.1) / 100)
        fee = 15 if order.delivery else 0
        final = adjusted + tax + fee
        return {
            "quotation": lines,
            "subtotal": subtotal,
            "discount": discount,
            "tax": tax,
            "delivery_fee": fee,
            "final_total": final
        }
    except Exception as e:
        logger.exception("Error calculating quotation")
        raise

def generate_pdf_quote(quotation: Dict[str, Any], output_path: str = "quotation.pdf") -> str:
    """
    Generates a PDF for the given quotation.
    Returns the path to the generated PDF.
    """
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "Leyla Cuisine Quotation", ln=True, align="C")
        pdf.ln(10)

        # Order summary
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True)
        if "email" in quotation and quotation["email"]:
            pdf.cell(0, 10, f"Client Email: {quotation['email']}", ln=True)
        pdf.ln(5)

        # Table header
        pdf.set_font("Arial", "B", 12)
        pdf.cell(60, 10, "Item", border=1)
        pdf.cell(25, 10, "Quantity", border=1)
        pdf.cell(30, 10, "Unit Price", border=1)
        pdf.cell(35, 10, "Total Price", border=1)
        pdf.cell(0, 10, "Category", border=1, ln=True)

        pdf.set_font("Arial", "", 12)
        for item in quotation["quotation"]:
            pdf.cell(60, 10, str(item["Item"]), border=1)
            pdf.cell(25, 10, str(item["Quantity"]), border=1)
            pdf.cell(30, 10, f"${item['Unit Price']:.2f}", border=1)
            pdf.cell(35, 10, f"${item['Total Price']:.2f}", border=1)
            pdf.cell(0, 10, str(item["Category"]), border=1, ln=True)

        pdf.ln(5)
        # Totals
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, f"Subtotal: ${quotation['subtotal']:.2f}", ln=True)
        pdf.cell(0, 10, f"Discount: -${quotation['discount']:.2f}", ln=True)
        pdf.cell(0, 10, f"Tax: +${quotation['tax']:.2f}", ln=True)
        if quotation.get("delivery_fee", 0):
            pdf.cell(0, 10, f"Delivery Fee: +${quotation['delivery_fee']:.2f}", ln=True)
        pdf.cell(0, 10, f"Grand Total: ${quotation['final_total']:.2f}", ln=True)

        pdf.output(output_path)
        return output_path
    except Exception as e:
        logger.exception("Error generating PDF quote")
        raise

def save_approved_quotation(pdf_path: str) -> str:
    folder = "Approved Quotations"
    os.makedirs(folder, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    new = os.path.join(folder, f"Quote_{date_str}.pdf")
    with open(pdf_path, "rb") as src, open(new, "wb") as dst:
        dst.write(src.read())
    return new

# --- SALES via Drive ---

def save_sales(quotation: Dict[str, Any]) -> bool:
    return gdh.record_sales(quotation)

# --- MENU ops as function_tools wrapping Drive handlers ---

@function_tool
async def add_menu_item(wrapper: RunContextWrapper[Menu_item], mi: Menu_item) -> str:
    return gdh.add_menu_item(mi)

@function_tool
async def edit_menu_item(wrapper: RunContextWrapper[Menu_item], mi: Menu_item) -> str:
    return gdh.edit_menu_item(mi)

@function_tool
async def delete_menu_item(wrapper: RunContextWrapper[Menu_item], mi: Menu_item) -> str:
    return gdh.delete_menu_item(mi.Item)

@function_tool
async def list_menu_items(wrapper: RunContextWrapper[Menu_item]) -> str:
    return gdh.list_menu_items()

# --- CONTACTS ops as function_tools wrapping Drive handlers ---

@function_tool
async def add_contact(wrapper: RunContextWrapper[Contact], contact: Contact) -> str:
    result = gdh.append_contact(contact.Name, contact.Email, contact.Phone, contact.Address)
    return "Contact added successfully." if result else "Failed to add contact."

@function_tool
async def edit_contact(wrapper: RunContextWrapper[Contact], contact: Contact) -> str:
    # You need to implement edit_contact in google_drive_handler.py
    result = gdh.edit_contact(contact.Name, contact.Email, contact.Phone, contact.Address)
    return "Contact edited successfully." if result else "Failed to edit contact."

@function_tool
async def delete_contact(wrapper: RunContextWrapper[Contact], contact: Contact) -> str:
    # Now passes name, email, and phone for deletion
    result = gdh.delete_contact(contact.Name, contact.Email, contact.Phone)
    return "Contact deleted successfully." if result else "Failed to delete contact."

@function_tool
async def list_contacts(wrapper: RunContextWrapper[Contact]) -> str:
    # You need to implement list_contacts in google_drive_handler.py
    return gdh.list_contacts()

# --- CALENDAR TOOLS ---

from google_handlers import google_calendar_handler as gcal

@function_tool
async def add_delivery_event(wrapper: RunContextWrapper[DeliveryEvent], event: DeliveryEvent) -> str:
    """
    Adds a delivery event to the calendar.
    """
    try:
        attendees = [{"email": a} for a in (event.attendees or [])]
        created = gcal.create_delivery_event(
            summary=event.summary,
            address=event.address,
            description=event.description or "",
            start_datetime=event.start_datetime,
            end_datetime=event.end_datetime,
            attendees=attendees
        )
        return f"Delivery event created: {created.get('htmlLink')}"
    except Exception as e:
        logger.exception("Error adding delivery event")
        return f"Failed to create event: {e}"

@function_tool
async def edit_delivery_event(wrapper: RunContextWrapper[DeliveryEvent], event: DeliveryEvent) -> str:
    """
    Edits an existing delivery event.
    """
    try:
        updated = gcal.edit_delivery_event(
            event_id=event.event_id,
            summary=event.summary,
            address=event.address,
            description=event.description,
            start_datetime=event.start_datetime,
            end_datetime=event.end_datetime
        )
        return f"Delivery event updated: {updated.get('htmlLink')}"
    except Exception as e:
        logger.exception("Error editing delivery event")
        return f"Failed to edit event: {e}"

@function_tool
async def delete_delivery_event(wrapper: RunContextWrapper[DeliveryEvent], event: DeliveryEvent) -> str:
    """
    Deletes a delivery event.
    """
    try:
        gcal.delete_delivery_event(event.event_id)
        return "Delivery event deleted."
    except Exception as e:
        logger.exception("Error deleting delivery event")
        return f"Failed to delete event: {e}"
