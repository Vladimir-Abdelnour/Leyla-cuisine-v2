# Leyla Cuisine Quotation Generator

## Overview

Leyla Cuisine Quotation Generator is an AI-powered Telegram bot that manages menu items, contacts, and generates quotations for catering orders. It integrates with Google Drive, Sheets, Calendar, and Gmail for seamless business operations.

---

## Features

- **Order Parsing:** Understands natural language orders and generates structured quotations.
- **Menu Management:** Add, edit, delete, and list menu items via Google Sheets.
- **Contact Management:** Manage customer contacts in Google Sheets.
- **Quotation Generation:** Calculates totals, applies discounts/tax, and generates PDF quotations.
- **Sales Recording:** Logs sales data to Google Sheets.
- **Email Integration:** Sends quotations as PDF attachments via Gmail.
- **Google Calendar:** (Optional) Schedule events for orders.

---

## File Structure

```
Leyla-cuisine/
├── bot.py                  # Main Telegram bot logic
├── tools_handler.py        # Business logic and model definitions
├── agents/                 # AI agent definitions
├── google_handlers/        # Google API integrations
│   ├── google_drive_handler.py
│   ├── google_calendar_handler.py
│   └── email_handler.py
├── data/                   # CSV data files (menu, sales, contacts)
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (not committed)
├── .gitignore
└── README.md
```

---

## Setup Instructions

### 1. Clone the Repository

```sh
git clone <repo-url>
cd Leyla-cuisine
```

### 2. Create and Activate a Virtual Environment

```sh
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```sh
pip install -r requirements.txt
```

### 4. Set Up Environment Variables

Create a `.env` file in the project root:

```
TELEGRAM_API_KEY=your-telegram-bot-api-key
OPENAI_API_KEY=your-openai-api-key
```

### 5. Google API Credentials

- Download `credentials.json` from your Google Cloud Console (OAuth2 client).
- Place it in the project root.

### 6. Run the Bot

```sh
python bot.py
```

---

## Usage

- Interact with the Telegram bot using `/Greet` or by sending orders, menu, or contact management commands.
- The bot will guide you through order confirmation and send quotations via email.

---

## Security

- **Never commit `.env` or `credentials.json` to version control.**
- All sensitive keys are loaded from environment variables.

---

## Testing

- Add unit tests for all business logic in `tools_handler.py` and Google handlers.
- Use `pytest` for running tests.

---

## Deployment

- Use a process manager (e.g., `systemd`, `pm2`, or Docker) for production deployment.
- Ensure all environment variables are set in your deployment environment.

---

## Troubleshooting

- Ensure all Google API tokens are valid and have the correct scopes.
- Check logs (`logging.INFO`) for detailed error messages.

---

## License

MIT License

---

## Contact

For support, contact Vladimir Abdelnou at vabdelno@asu.edu.