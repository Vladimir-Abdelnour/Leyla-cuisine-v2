# 🚀 Leyla Cuisine Bot - Production Deployment Guide

This guide will walk you through deploying your Leyla Cuisine Telegram bot to an Ubuntu server with full automation and monitoring.

## 📋 Prerequisites

- Ubuntu 20.04+ server with sudo access
- Domain name or ngrok account for OAuth callbacks
- Google Cloud Console project with APIs enabled
- Telegram Bot Token
- OpenAI API Key

## 🔧 Phase 1: Push Code to GitHub

### 1.1 Prepare Your Repository

```bash
# Add all files to git
git add .

# Commit your changes
git commit -m "feat: Add OAuth web server and production deployment setup

- Added Flask web server for OAuth callbacks
- Fixed OAuth redirect URI handling
- Added production requirements.txt
- Added deployment automation script
- Ready for server deployment"

# Push to GitHub
git push origin main
```

### 1.2 Verify GitHub Repository
- Go to your GitHub repository
- Ensure all files are present including:
  - `bot.py`
  - `requirements_production.txt`
  - `deploy.sh`
  - All `google_handlers/` files
  - `config.py`
  - `.env.example` (create this if needed)

## 🖥️ Phase 2: Server Setup

### 2.1 Connect to Your Ubuntu Server

```bash
# SSH into your server
ssh username@your-server-ip

# Or if using a key file
ssh -i /path/to/your-key.pem username@your-server-ip
```

### 2.2 Clone Your Repository

```bash
# Clone your repository
git clone https://github.com/yourusername/your-repo-name.git
cd your-repo-name

# Make deployment script executable
chmod +x deploy.sh
```

### 2.3 Run Automated Deployment

```bash
# Run the deployment script
./deploy.sh
```

This script will:
- ✅ Update system packages
- ✅ Install Python 3 and dependencies
- ✅ Create virtual environment
- ✅ Install Python packages
- ✅ Create systemd service
- ✅ Configure firewall
- ✅ Set up logging

## 🔐 Phase 3: Configuration

### 3.1 Create Environment File

```bash
# Navigate to the bot directory
cd ~/leyla-cuisine-bot

# Create .env file
nano .env
```

Add your configuration:
```env
# Telegram Bot Configuration
TELEGRAM_API_KEY=your_telegram_bot_token_here

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Google OAuth Configuration
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=https://yourdomain.com/oauth2callback

# Email Configuration
GOOGLE_EMAIL=your_google_email@gmail.com
DEFAULT_SENDER_EMAIL=your_sender_email@gmail.com
DEFAULT_RECIPIENT_EMAIL=your_default_recipient@gmail.com

# File Paths
GOOGLE_CREDENTIALS_FILE=credentials.json
```

### 3.2 Upload Google Credentials

```bash
# Upload your credentials.json file to the server
# Option 1: Using scp from your local machine
scp credentials.json username@your-server-ip:~/leyla-cuisine-bot/

# Option 2: Create and paste content
nano ~/leyla-cuisine-bot/credentials.json
# Paste your credentials.json content here
```

## 🌐 Phase 4: Domain/Tunnel Setup

### Option A: Using Your Own Domain (Recommended for Production)

#### 4.1 Set Up Reverse Proxy with Nginx

```bash
# Install Nginx
sudo apt install nginx

# Create Nginx configuration
sudo nano /etc/nginx/sites-available/leyla-cuisine-bot
```

Add this configuration:
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Enable the site
sudo ln -s /etc/nginx/sites-available/leyla-cuisine-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Install SSL certificate with Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

#### 4.2 Update Google Cloud Console
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to APIs & Services > Credentials
3. Edit your OAuth 2.0 Client ID
4. Update Authorized redirect URIs to: `https://yourdomain.com/oauth2callback`

### Option B: Using ngrok (For Testing/Development)

```bash
# Install ngrok
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok

# Authenticate ngrok (get token from ngrok.com)
ngrok config add-authtoken YOUR_NGROK_TOKEN

# Create ngrok service
sudo tee /etc/systemd/system/ngrok.service > /dev/null <<EOF
[Unit]
Description=ngrok tunnel
After=network.target

[Service]
Type=simple
User=$USER
ExecStart=/usr/local/bin/ngrok http 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start ngrok
sudo systemctl enable ngrok
sudo systemctl start ngrok

# Get your ngrok URL
curl http://localhost:4040/api/tunnels | jq '.tunnels[0].public_url'
```

## 🚀 Phase 5: Start the Bot

### 5.1 Start the Bot Service

```bash
# Start the bot
sudo systemctl start leyla-cuisine-bot

# Check status
sudo systemctl status leyla-cuisine-bot

# Enable auto-start on boot
sudo systemctl enable leyla-cuisine-bot
```

### 5.2 Monitor Logs

```bash
# View real-time logs
sudo journalctl -u leyla-cuisine-bot -f

# View recent logs
sudo journalctl -u leyla-cuisine-bot -n 50

# View logs from specific time
sudo journalctl -u leyla-cuisine-bot --since "1 hour ago"
```

## 🔍 Phase 6: Testing & Verification

### 6.1 Test Bot Connectivity

```bash
# Check if bot is responding
curl http://localhost:8080/

# Test OAuth endpoint
curl http://localhost:8080/oauth2callback
```

### 6.2 Test Telegram Bot

1. Open Telegram and find your bot
2. Send `/start` or any message
3. The bot should respond and ask for Google authentication if needed
4. Follow the OAuth flow to complete setup

### 6.3 Test OAuth Flow

1. Send a message that requires Google services
2. Bot should provide an OAuth link
3. Click the link and authorize
4. Verify successful authentication

## 🛠️ Phase 7: Maintenance & Monitoring

### 7.1 Useful Commands

```bash
# Restart the bot
sudo systemctl restart leyla-cuisine-bot

# Stop the bot
sudo systemctl stop leyla-cuisine-bot

# Check bot status
sudo systemctl status leyla-cuisine-bot

# Update the bot code
cd ~/leyla-cuisine-bot
git pull origin main
sudo systemctl restart leyla-cuisine-bot

# Check system resources
htop
df -h
free -h
```

### 7.2 Log Management

```bash
# Rotate logs to prevent disk space issues
sudo nano /etc/logrotate.d/leyla-cuisine-bot
```

Add:
```
/var/log/leyla-cuisine-bot/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 ubuntu ubuntu
}
```

### 7.3 Backup Strategy

```bash
# Create backup script
nano ~/backup-bot.sh
```

Add:
```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$HOME/backups"
mkdir -p "$BACKUP_DIR"

# Backup bot files
tar -czf "$BACKUP_DIR/leyla-bot-$DATE.tar.gz" \
    ~/leyla-cuisine-bot \
    --exclude="~/leyla-cuisine-bot/venv" \
    --exclude="~/leyla-cuisine-bot/__pycache__"

# Keep only last 7 backups
find "$BACKUP_DIR" -name "leyla-bot-*.tar.gz" -mtime +7 -delete
```

```bash
# Make executable and add to cron
chmod +x ~/backup-bot.sh
crontab -e
# Add: 0 2 * * * /home/ubuntu/backup-bot.sh
```

## 🚨 Troubleshooting

### Common Issues:

1. **Bot not starting:**
   ```bash
   sudo journalctl -u leyla-cuisine-bot -n 50
   ```

2. **OAuth not working:**
   - Check redirect URI in Google Console
   - Verify domain/ngrok is accessible
   - Check firewall settings

3. **Permission errors:**
   ```bash
   sudo chown -R $USER:$USER ~/leyla-cuisine-bot
   ```

4. **Port already in use:**
   ```bash
   sudo lsof -i :8080
   sudo kill -9 PID
   ```

## 🎉 Success!

Your Leyla Cuisine bot is now running in production! 

### Key Features Now Available:
- ✅ 24/7 automated operation
- ✅ Automatic OAuth handling
- ✅ Google Drive integration
- ✅ Email quotations
- ✅ Calendar scheduling
- ✅ Persistent logging
- ✅ Auto-restart on failure
- ✅ Secure HTTPS OAuth

### Next Steps:
- Monitor logs regularly
- Set up monitoring alerts
- Consider load balancing for high traffic
- Implement database backup automation
- Add health check endpoints 