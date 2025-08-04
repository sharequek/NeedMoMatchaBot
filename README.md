# 🍵 Need Mo' Matcha Bot 🍵

A Telegram bot that monitors Ippodo Tea matcha products ([ippodotea.com](https://ippodotea.com)) for stock changes and sends notifications to users.

## Features

- **Product Monitoring**: Track stock status for Ippodo matcha products
- **Customizable Alerts**: Users can choose which products to monitor
- **Persistent Preferences**: User settings saved across bot restarts
- **Enhanced Notifications**: Get updates on stock changes and restocking info
- **Development Mode**: Test safely without notifying all users

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure the bot:**
   - Update `config.yaml` with your Telegram token
   - Set your user ID in the development section for testing

3. **Start the bot:**
   ```bash
   python bot.py
   ```

## Telegram Commands

- `/start` - Register and get welcome message
- `/list` - Show all available products
- `/status` - Show your monitored products
- `/add <product_id>` - Add product to monitoring
- `/remove <product_id>` - Remove product from monitoring
- `/default` - Reset to default (Ikuyo 100g only)
- `/help` - Show help message

## Pausing Notifications

To pause notifications temporarily: **Mute the bot chat in Telegram** - the bot continues monitoring but won't send notifications.

## Development Mode

**Enable (testing):**
```bash
python dev_mode.py enable <your_user_id>
```

**Disable (production):**
```bash
python dev_mode.py disable
```

**Check status:**
```bash
python dev_mode.py status
```

## Available Products

- **Ummon**: 20g, 40g
- **Sayaka**: 40g, 100g  
- **Horai**: 20g
- **Kan**: 30g
- **Ikuyo**: 30g, 100g
- **Wakaki**: 40g

## File Structure

```
├── bot.py                 # Main bot script
├── config.yaml            # Configuration
├── dev_mode.py            # Development mode switcher
├── requirements.txt       # Python dependencies
├── users/                 # User preferences (auto-created)
├── stock_status/          # Stock tracking (auto-created)
└── README.md              # This file
```

## Deployment

**On Raspberry Pi:**
```bash
git clone git@github.com:sharequek/need-mo-matcha-bot.git
cd need-mo-matcha-bot
pip install -r requirements.txt
python bot.py
```

## Troubleshooting

- **Bot not starting**: Check Telegram token in `config.yaml`
- **No notifications**: Verify user is registered (`/start`)
- **Product errors**: Bot will notify if products become unavailable