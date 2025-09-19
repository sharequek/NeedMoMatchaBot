#!/usr/bin/env python3
"""
Development Mode Manager for Need Mo Matcha Bot
Simple script to switch between development and production modes.
Supports both config.yaml and environment variable configuration.
"""

import yaml
import sys
import os
from dotenv import load_dotenv

def get_dev_user_id():
    """Get dev user ID from environment variable or config file"""
    load_dotenv()
    
    # Check environment variable first
    env_user_id = os.getenv('DEV_USER_ID')
    if env_user_id:
        return env_user_id
    
    # Fallback to config file
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        return config.get('development', {}).get('dev_user_id')
    except FileNotFoundError:
        return None

def update_dev_mode(enabled, dev_user_id=None):
    """Update the development mode settings in config.yaml"""
    
    # Read current config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Update development settings
    if 'development' not in config:
        config['development'] = {}
    
    # If enabling and no user_id provided, try to get existing one
    if enabled and not dev_user_id:
        existing_user_id = get_dev_user_id()
        if existing_user_id:
            dev_user_id = existing_user_id
            print(f"📱 Using existing dev user ID: {dev_user_id}")
        else:
            print("❌ No dev user ID found in config or environment")
            print("Please run: python dev_mode.py enable <your_user_id>")
            print("Or set DEV_USER_ID environment variable in .env file")
            return False
    
    config['development']['enabled'] = enabled
    if dev_user_id:
        config['development']['dev_user_id'] = str(dev_user_id)
    
    # Write updated config
    with open('config.yaml', 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    status = "enabled" if enabled else "disabled"
    print(f"✅ Development mode {status}")
    if enabled and dev_user_id:
        print(f"📱 Only sending messages to user: {dev_user_id}")
    
    return True

def show_status():
    """Show current development mode status"""
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print("❌ config.yaml not found")
        return
    
    dev_config = config.get('development', {})
    enabled = dev_config.get('enabled', False)
    
    # Get dev user ID from environment or config
    dev_user_id = get_dev_user_id() or 'Not set'
    
    print(f"🔧 Development Mode: {'✅ Enabled' if enabled else '❌ Disabled'}")
    if enabled:
        print(f"📱 Dev User ID: {dev_user_id}")
        if dev_user_id != 'Not set':
            print(f"🔍 Source: {'Environment (.env)' if os.getenv('DEV_USER_ID') else 'Config file'}")
    print(f"🤖 Production Mode: {'❌ Disabled' if enabled else '✅ Enabled'}")
    
    # Show environment status
    load_dotenv()
    env_token = os.getenv('TELEGRAM_BOT_TOKEN')
    env_user_id = os.getenv('DEV_USER_ID')
    
    print(f"\n🔐 Environment Variables:")
    print(f"   TELEGRAM_BOT_TOKEN: {'✅ Set' if env_token else '❌ Not set'}")
    print(f"   DEV_USER_ID: {'✅ Set' if env_user_id else '❌ Not set'}")

def setup_env_file():
    """Help user set up .env file with required variables"""
    print("🔧 Setting up environment variables...")
    
    # Check if .env exists
    if os.path.exists('.env'):
        print("📄 .env file already exists")
        with open('.env', 'r') as f:
            content = f.read()
            if 'TELEGRAM_BOT_TOKEN' in content:
                print("✅ TELEGRAM_BOT_TOKEN is already set")
            else:
                print("❌ TELEGRAM_BOT_TOKEN is missing from .env")
                print("Please add: TELEGRAM_BOT_TOKEN=your_bot_token")
    else:
        print("📄 Creating .env file...")
        with open('.env', 'w') as f:
            f.write("# Telegram Bot Configuration\n")
            f.write("TELEGRAM_BOT_TOKEN=your_bot_token_here\n")
            f.write("\n# Development Configuration\n")
            f.write("DEV_USER_ID=your_user_id_here\n")
        print("✅ .env file created")
        print("📝 Please edit .env file and add your actual token and user ID")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python dev_mode.py enable [user_id]  # Enable dev mode")
        print("  python dev_mode.py disable            # Disable dev mode")
        print("  python dev_mode.py status             # Show current status")
        print("  python dev_mode.py setup              # Set up .env file")
        return
    
    command = sys.argv[1].lower()
    
    if command == "enable":
        user_id = sys.argv[2] if len(sys.argv) > 2 else None
        if update_dev_mode(True, user_id):
            print("\n🔄 **Next steps:**")
            print("   1. Stop the bot in Cursor (Ctrl+C)")
            print("   2. Restart: python bot.py")
            print("   3. Bot will send maintenance notifications when it restarts")
        
    elif command == "disable":
        if update_dev_mode(False):
            print("\n🔄 **Next steps:**")
            print("   1. Stop the bot in Cursor (Ctrl+C)")
            print("   2. Restart: python bot.py")
            print("   3. Bot will send resume notifications when it restarts")
        
    elif command == "status":
        show_status()
        
    elif command == "setup":
        setup_env_file()
        
    else:
        print("❌ Unknown command. Use: enable, disable, status, or setup")

if __name__ == "__main__":
    main() 