# Leyla Cuisine Bot

A Telegram bot for Leyla Cuisine that handles quotation generation, menu management, contact management, and delivery scheduling.

## Setup Instructions

### 1. Prerequisites
- Python 3.8 or higher
- A Telegram account
- A Google account with access to:
  - Google Drive
  - Google Calendar
  - Gmail

### 2. Initial Setup

1. Clone this repository:
```bash
git clone https://github.com/yourusername/leyla-cuisine-bot.git
cd leyla-cuisine-bot
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Unix/MacOS:
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Configuration

1. Create a `.env` file in the project root with the following variables:
```env
# Telegram Bot Configuration
TELEGRAM_API_KEY=your_telegram_bot_token_here

# Google API Configuration
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_EMAIL=your_google_email@gmail.com

# Email Configuration
DEFAULT_SENDER_EMAIL=your_google_email@gmail.com
DEFAULT_RECIPIENT_EMAIL=default_recipient@example.com
```

2. Set up Google API credentials:
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project or select an existing one
   - Enable the following APIs:
     - Google Drive API
     - Google Calendar API
     - Gmail API
   - Create OAuth 2.0 credentials
   - Download the credentials and save as `credentials.json` in the project root

3. Set up Telegram Bot:
   - Message [@BotFather](https://t.me/botfather) on Telegram
   - Create a new bot using `/newbot`
   - Copy the API token and add it to your `.env` file

### 4. Running the Bot

1. Start the bot:
```bash
python bot.py
```

2. The first time you run the bot, it will:
   - Open a browser window for Google OAuth authentication
   - Create necessary Google Drive folders and sheets
   - Generate token files for Google API access

### 5. Deployment

#### Local Deployment
For local deployment, simply run the bot as described above.

#### Server Deployment
For server deployment:

1. Set up a server with Python 3.8+
2. Clone the repository
3. Follow the setup instructions above
4. Use a process manager like `systemd` or `supervisor` to keep the bot running
5. Set up SSL certificates if needed

Example systemd service file:
```ini
[Unit]
Description=Leyla Cuisine Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/leyla-cuisine-bot
Environment=PATH=/path/to/leyla-cuisine-bot/.venv/bin
ExecStart=/path/to/leyla-cuisine-bot/.venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### 6. Security Notes

- Never commit the following files to version control:
  - `.env`
  - `credentials.json`
  - `*.pickle` files
  - Any PDF files
- Keep your API keys and credentials secure
- Regularly update dependencies for security patches

## Features

- Automated quotation generation
- Menu management
- Contact management
- Delivery scheduling
- Google Drive integration
- Email notifications
- Multi-threaded message handling

## Support

For support, please contact [your contact information].