#!/bin/bash

# Leyla Cuisine Bot Deployment Script
# This script sets up the bot on an Ubuntu server

set -e  # Exit on any error

echo "🚀 Starting Leyla Cuisine Bot Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root for security reasons"
   exit 1
fi

# Update system packages
print_status "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python 3.11+ and pip
print_status "Installing Python and dependencies..."
sudo apt install -y python3 python3-pip python3-venv git curl wget

# Install system dependencies for Python packages
sudo apt install -y build-essential libssl-dev libffi-dev python3-dev

# Create application directory
APP_DIR="$HOME/leyla-cuisine-bot"
print_status "Creating application directory at $APP_DIR..."
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# Create Python virtual environment
print_status "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
print_status "Installing Python dependencies..."
if [ -f "requirements_production.txt" ]; then
    pip install -r requirements_production.txt
else
    print_warning "requirements_production.txt not found, using requirements.txt"
    pip install -r requirements.txt
fi

# Create systemd service file
print_status "Creating systemd service..."
sudo tee /etc/systemd/system/leyla-cuisine-bot.service > /dev/null <<EOF
[Unit]
Description=Leyla Cuisine Telegram Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
ExecStart=$APP_DIR/venv/bin/python bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Create log directory
print_status "Creating log directory..."
mkdir -p "$APP_DIR/logs"

# Set up firewall (allow SSH and bot port)
print_status "Configuring firewall..."
sudo ufw allow ssh
sudo ufw allow 8080/tcp
sudo ufw --force enable

# Enable and start the service
print_status "Enabling and starting the bot service..."
sudo systemctl daemon-reload
sudo systemctl enable leyla-cuisine-bot.service

print_success "Deployment completed successfully!"
print_status "Next steps:"
echo "1. Copy your .env file to $APP_DIR/"
echo "2. Copy your credentials.json file to $APP_DIR/"
echo "3. Start the bot with: sudo systemctl start leyla-cuisine-bot"
echo "4. Check status with: sudo systemctl status leyla-cuisine-bot"
echo "5. View logs with: sudo journalctl -u leyla-cuisine-bot -f"
echo ""
print_warning "Don't forget to:"
echo "- Set up your domain/ngrok for OAuth callbacks"
echo "- Update your Google Cloud Console redirect URIs"
echo "- Test the OAuth flow after deployment" 