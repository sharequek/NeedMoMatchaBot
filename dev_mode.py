#!/usr/bin/env python3
"""
Development Mode Manager for Need Mo Matcha Bot
Simple script to switch between development and production modes.
"""

import yaml
import sys

def update_dev_mode(enabled, dev_user_id=None):
    """Update the development mode settings in config.yaml"""
    
    # Read current config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Update development settings
    if 'development' not in config:
        config['development'] = {}
    
    # If enabling and no user_id provided, use existing one
    if enabled and not dev_user_id:
        existing_user_id = config.get('development', {}).get('dev_user_id')
        if existing_user_id:
            dev_user_id = existing_user_id
            print(f"📱 Using existing dev user ID: {dev_user_id}")
        else:
            print("❌ No dev user ID found in config")
            print("Please run: python dev_mode.py enable <your_user_id>")
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
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    dev_config = config.get('development', {})
    enabled = dev_config.get('enabled', False)
    dev_user_id = dev_config.get('dev_user_id', 'Not set')
    
    print(f"🔧 Development Mode: {'✅ Enabled' if enabled else '❌ Disabled'}")
    if enabled:
        print(f"📱 Dev User ID: {dev_user_id}")
    print(f"🤖 Production Mode: {'❌ Disabled' if enabled else '✅ Enabled'}")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python dev_mode.py enable [user_id]  # Enable dev mode")
        print("  python dev_mode.py disable            # Disable dev mode")
        print("  python dev_mode.py status             # Show current status")
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
        
    else:
        print("❌ Unknown command. Use: enable, disable, or status")

if __name__ == "__main__":
    main() 