import asyncio
import json
import re
import requests
from bs4 import BeautifulSoup
from telegram import Bot, Update
import yaml
from datetime import datetime
import os

class NeedMoMatchaBot:
    def __init__(self, config_path="config.yaml"):
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Initialize bot
        self.bot = Bot(token=self.config['telegram']['token'])
        
        # Create directories if they don't exist
        os.makedirs('users', exist_ok=True)
        os.makedirs('stock_status', exist_ok=True)
        
        # Load all users
        self.users = self.load_users()
        
        # Development mode - only send to specific user (you)
        self.dev_mode = self.config.get('development', {}).get('enabled', False)
        self.dev_user_id = self.config.get('development', {}).get('dev_user_id', None)
        
        # Track bot state per user to prevent duplicate notifications
        self.user_bot_states = self.load_bot_states()  # 'maintenance' or 'resumed' per user
        
        print(f"🤖 Bot initialized")
        print(f"👥 Loaded {len(self.users)} users")
        print(f"📋 Available products: {len(self.config['available_products'])}")
        if self.dev_mode:
            print(f"🔧 Development mode enabled - only sending to user {self.dev_user_id}")
    
    def load_users(self):
        """Load all user configurations"""
        users = {}
        if os.path.exists('users'):
            for filename in os.listdir('users'):
                if filename.endswith('.json'):
                    chat_id = filename.replace('user_', '').replace('.json', '')
                    try:
                        with open(f'users/{filename}', 'r') as f:
                            user_data = json.load(f)
                            users[chat_id] = user_data
                    except Exception as e:
                        print(f"⚠️ Error loading user {chat_id}: {e}")
        return users
    
    def save_user(self, chat_id, user_data):
        """Save user configuration"""
        filename = f'users/user_{chat_id}.json'
        with open(filename, 'w') as f:
            json.dump(user_data, f, indent=2)
        self.users[chat_id] = user_data
    
    def get_user_stock_status(self, chat_id):
        """Get stock status for a specific user"""
        filename = f'stock_status/user_{chat_id}.json'
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                # Handle legacy format
                for product_id in data:
                    if isinstance(data[product_id], bool):
                        data[product_id] = {
                            'in_stock': data[product_id],
                            'message': 'Legacy status'
                        }
                return data
        except FileNotFoundError:
            return {}
    
    def save_user_stock_status(self, chat_id, stock_status):
        """Save stock status for a specific user"""
        filename = f'stock_status/user_{chat_id}.json'
        with open(filename, 'w') as f:
            json.dump(stock_status, f, indent=2)
    
    def load_bot_states(self):
        """Load bot states for all users"""
        filename = 'bot_states.json'
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def save_bot_states(self):
        """Save bot states for all users"""
        filename = 'bot_states.json'
        with open(filename, 'w') as f:
            json.dump(self.user_bot_states, f, indent=2)
    
    def add_user(self, chat_id, name="Unknown User"):
        """Add a new user with default preferences"""
        if chat_id not in self.users:
            user_data = {
                "chat_id": chat_id,
                "name": name,
                "monitored_products": ["ikuyo_100g"],  # Default
                "created_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat()
            }
            self.save_user(chat_id, user_data)
            print(f"✅ Added new user: {name} ({chat_id})")
            return True
        return False
    
    def update_user_preferences(self, chat_id, monitored_products):
        """Update user's monitored products"""
        if chat_id in self.users:
            self.users[chat_id]["monitored_products"] = monitored_products
            self.users[chat_id]["last_active"] = datetime.now().isoformat()
            self.save_user(chat_id, self.users[chat_id])
            return True
        return False
    
    def should_send_notification(self, notification_type, chat_id=None):
        """Check if we should send a notification based on bot state transitions"""
        if notification_type == "maintenance_start" or notification_type == "dev_mode_enabled":
            # Only send maintenance if user was previously in 'resumed' state
            current_state = self.user_bot_states.get(chat_id, 'resumed')  # Default to resumed
            if current_state == 'maintenance':
                return False  # Already in maintenance, don't send again
            else:
                # Update state to maintenance
                self.user_bot_states[chat_id] = 'maintenance'
                self.save_bot_states()  # Save the updated state
                return True
                
        elif notification_type == "maintenance_end":
            # Only send resume notification if user was previously in 'maintenance' state
            current_state = self.user_bot_states.get(chat_id, 'resumed')
            if current_state == 'resumed':
                return False  # Already resumed, don't send again
            else:
                # Update state to resumed
                self.user_bot_states[chat_id] = 'resumed'
                self.save_bot_states()  # Save the updated state
                return True
            
        elif notification_type == "unexpected_shutdown":
            # Always send crash notifications
            return True
            
        else:
            # For other notifications, always send
            return True
    
    def check_product_stock(self, product_id, product_config):
        """Check if a product is in stock using our proven logic"""
        try:
            response = requests.get(
                product_config['url'],
                timeout=self.config['monitoring']['timeout'],
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            
            # Handle different HTTP status codes
            if response.status_code == 404:
                return None, f"Product page not found (404) - Product may have been removed or URL changed"
            elif response.status_code == 403:
                return None, f"Access denied (403) - Website may be blocking requests"
            elif response.status_code == 500:
                return None, f"Server error (500) - Website may be experiencing issues"
            elif response.status_code != 200:
                return None, f"HTTP {response.status_code} - Unexpected response from website"
            
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check if page looks like a product page (basic validation)
            page_title = soup.find('title')
            if page_title:
                title_text = page_title.get_text().lower()
                if '404' in title_text or 'not found' in title_text or 'error' in title_text:
                    return None, f"Product page not found - Page title indicates error"
            
            # Check for out-of-stock container
            oos_container = soup.find('div', id='oos-container')
            if oos_container:
                # Extract OOS message if available
                oos_message = oos_container.get_text(strip=True)
                if oos_message:
                    return False, f"Out of stock: {oos_message}"
                else:
                    return False, "Out of stock (oos-container found)"
            
            # Check the add button container
            add_button_container = soup.find('div', class_='add-button-container')
            if add_button_container:
                stock_status_span = add_button_container.find('span', class_='product-stock-status')
                if stock_status_span:
                    status_text = stock_status_span.get_text(strip=True)
                    status_normalized = re.sub(r'\s+', ' ', status_text.lower().strip())
                    
                    if 'sold out' in status_normalized:
                        return False, f"Out of stock ({status_text})"
                    elif 'add to bag' in status_normalized:
                        return True, f"In stock ({status_text})"
                    else:
                        return None, f"Unknown status ({status_text})"
                else:
                    return None, "No stock status span found"
            else:
                return None, "No add button container found"
                
        except requests.exceptions.ConnectionError:
            return None, f"Connection error - Cannot reach the website"
        except requests.exceptions.Timeout:
            return None, f"Timeout error - Website took too long to respond"
        except requests.exceptions.RequestException as e:
            return None, f"Request error: {str(e)}"
        except Exception as e:
            return None, f"Unexpected error: {str(e)}"
    
    async def send_notification(self, chat_id, product_name, is_in_stock, message, product_url):
        """Send Telegram notification"""
        # Skip if in dev mode and not the dev user
        if self.dev_mode and str(chat_id) != str(self.dev_user_id):
            print(f"🔧 Dev mode: Skipping notification to {chat_id} for {product_name}")
            return
            
        status_emoji = "🟢" if is_in_stock else "🔴"
        status_text = "In Stock" if is_in_stock else "Out of Stock"
        
        # Format message for better readability
        if is_in_stock:
            notification = (
                f"🍵 *Matcha Stock Update*\n\n"
                f"*{product_name}*\n"
                f"Status: {status_emoji} {status_text}\n"
                f"Details: {message}\n\n"
                f"Check it out: {product_url}"
            )
        else:
            # For out of stock, emphasize the restocking message
            notification = (
                f"🍵 *Matcha Stock Update*\n\n"
                f"*{product_name}*\n"
                f"Status: {status_emoji} {status_text}\n"
                f"📢 *Restocking Info:* {message}\n\n"
                f"Check it out: {product_url}"
            )
        
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=notification,
                parse_mode='Markdown'
            )
            print(f"📱 Notification sent to {chat_id} for {product_name}")
        except Exception as e:
            print(f"❌ Error sending notification to {chat_id}: {e}")
    
    async def send_message(self, chat_id, message, parse_mode='Markdown'):
        """Send message to Telegram chat"""
        # Skip if in dev mode and not the dev user
        if self.dev_mode and str(chat_id) != str(self.dev_user_id):
            print(f"🔧 Dev mode: Skipping message to {chat_id}")
            return
            
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=parse_mode
            )
        except Exception as e:
            print(f"❌ Error sending message to {chat_id}: {e}")
    
    async def notify_maintenance_start(self):
        """Notify all users that bot is going into maintenance"""
        maintenance_msg = (
            "🔧 *Bot Maintenance*\n\n"
            "The bot is going into maintenance mode for updates.\n"
            "You won't receive notifications during this time.\n\n"
            "The bot will resume automatically when maintenance is complete."
        )
        
        if self.dev_mode:
            # In dev mode, only notify the dev user
            if self.should_send_notification("maintenance_start", self.dev_user_id):
                try:
                    await self.bot.send_message(
                        chat_id=self.dev_user_id,
                        text=maintenance_msg,
                        parse_mode='Markdown'
                    )
                    print(f"📱 Dev mode: Maintenance notification sent to {self.dev_user_id}")
                except Exception as e:
                    print(f"❌ Error sending maintenance notification to dev user: {e}")
            else:
                print(f"📱 Dev mode: Skipping maintenance notification (already in maintenance)")
            return
        
        # In production mode, notify all users
        for chat_id in self.users:
            if self.should_send_notification("maintenance_start", chat_id):
                try:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=maintenance_msg,
                        parse_mode='Markdown'
                    )
                    print(f"📱 Maintenance notification sent to {chat_id}")
                except Exception as e:
                    print(f"❌ Error sending maintenance notification to {chat_id}: {e}")
            else:
                print(f"📱 Skipping maintenance notification to {chat_id} (already in maintenance)")
    
    async def notify_maintenance_end(self):
        """Notify all users that bot has resumed"""
        resume_msg = (
            "✅ *Bot Resumed*\n\n"
            "The bot is back online and monitoring your products!\n\n"
            "You'll receive notifications for stock changes as usual."
        )
        
        if self.dev_mode:
            # In dev mode, only notify the dev user
            if self.should_send_notification("maintenance_end", self.dev_user_id):
                try:
                    await self.bot.send_message(
                        chat_id=self.dev_user_id,
                        text=resume_msg,
                        parse_mode='Markdown'
                    )
                    print(f"📱 Dev mode: Resume notification sent to {self.dev_user_id}")
                except Exception as e:
                    print(f"❌ Error sending resume notification to dev user: {e}")
            else:
                print(f"📱 Dev mode: Skipping resume notification (already resumed)")
            return
        
        # In production mode, notify all users
        for chat_id in self.users:
            if self.should_send_notification("maintenance_end", chat_id):
                try:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=resume_msg,
                        parse_mode='Markdown'
                    )
                    print(f"📱 Resume notification sent to {chat_id}")
                except Exception as e:
                    print(f"❌ Error sending resume notification to {chat_id}: {e}")
            else:
                print(f"📱 Skipping resume notification to {chat_id} (already resumed)")
    
    async def notify_dev_mode_enabled(self):
        """Notify dev user that dev mode is enabled (same as maintenance message)"""
        maintenance_msg = (
            "🔧 *Bot Maintenance*\n\n"
            "The bot is going into maintenance mode for updates.\n"
            "You won't receive notifications during this time.\n\n"
            "The bot will resume automatically when maintenance is complete."
        )
        
        if self.dev_mode and self.dev_user_id:
            # Use the same state-based logic as other notifications
            if self.should_send_notification("dev_mode_enabled", self.dev_user_id):
                try:
                    await self.bot.send_message(
                        chat_id=self.dev_user_id,
                        text=maintenance_msg,
                        parse_mode='Markdown'
                    )
                    print(f"📱 Dev mode: Maintenance notification sent to {self.dev_user_id}")
                except Exception as e:
                    print(f"❌ Error sending dev mode notification: {e}")
            else:
                print(f"📱 Dev mode: Skipping maintenance notification (already in maintenance)")

    async def notify_unexpected_shutdown(self, error_message):
        """Notify all users that bot crashed unexpectedly"""
        crash_msg = (
            "💥 *Bot Unexpected Shutdown*\n\n"
            "The bot encountered an error and had to stop.\n"
            f"Error: {error_message}\n\n"
            "The bot will need to be restarted manually.\n"
            "You won't receive notifications until it's back online."
        )
        
        if self.dev_mode:
            # In dev mode, only notify the dev user
            try:
                await self.bot.send_message(
                    chat_id=self.dev_user_id,
                    text=crash_msg,
                    parse_mode='Markdown'
                )
                print(f"📱 Dev mode: Crash notification sent to {self.dev_user_id}")
            except Exception as e:
                print(f"❌ Error sending crash notification to dev user: {e}")
            return
        
        # In production mode, notify all users
        for chat_id in self.users:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=crash_msg,
                    parse_mode='Markdown'
                )
                print(f"📱 Crash notification sent to {chat_id}")
            except Exception as e:
                print(f"❌ Error sending crash notification to {chat_id}: {e}")
    
    async def notify_product_error(self, chat_id, product_name, error_message):
        """Notify user about a product that can't be monitored"""
        if self.dev_mode and str(chat_id) != str(self.dev_user_id):
            print(f"🔧 Dev mode: Skipping product error notification to {chat_id}")
            return
            
        error_msg = (
            f"⚠️ *Product Monitoring Issue*\n\n"
            f"*{product_name}*\n"
            f"**Error:** {error_message}\n\n"
            f"This product may have been removed from the website or the URL may have changed.\n\n"
            f"*To fix this:*\n"
            f"• Use `/remove {product_name.lower().replace(' ', '_')}` to stop monitoring\n"
            f"• Use `/list` to see other available products\n"
            f"• Contact the bot administrator if this persists"
        )
        
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=error_msg,
                parse_mode='Markdown'
            )
            print(f"📱 Product error notification sent to {chat_id} for {product_name}")
        except Exception as e:
            print(f"❌ Error sending product error notification to {chat_id}: {e}")
    

    
    async def handle_command(self, chat_id, message_text):
        """Handle Telegram commands from specific user"""
        if message_text.startswith('/'):
            command = message_text.split()[0].lower()
            
            if command == '/start':
                # Add user if they don't exist
                self.add_user(chat_id, "Telegram User")
                await self.send_message(
                    chat_id,
                    "🍵 *Welcome to Need Mo Matcha Bot!*\n\n"
                    "I monitor Ippodo Tea matcha products (ippodotea.com) for stock changes.\n\n"
                    "*Default Setup:* You're monitoring **Ikuyo 100g**\n\n"
                    "*Commands:*\n"
                    "📋 `/list` - Show all products\n"
                    "📊 `/status` - Show your monitored products\n"
                    "➕ `/add <product_id>` - Add product to monitoring\n"
                    "➖ `/remove <product_id>` - Remove product\n"
                    "🔄 `/default` - Reset to default\n"
                    "❓ `/help` - Show help\n\n"
                    "*To pause notifications:* Mute this chat in Telegram\n\n"
                    "*Example:* `/add sayaka_40g`"
                )
            
            elif command == '/list':
                product_list = "📋 *Available Matcha Products:*\n\n"
                user_products = self.users.get(chat_id, {}).get('monitored_products', [])
                
                # Define the order based on website layout (RICH, MEDIUM, LIGHT)
                product_order = [
                    'ummon_40g', 'ummon_20g',  # RICH
                    'sayaka_100g', 'sayaka_40g', 'horai_20g',  # RICH
                    'kan_30g',  # MEDIUM
                    'ikuyo_100g', 'ikuyo_30g',  # MEDIUM
                    'wakaki_40g'  # LIGHT
                ]
                
                for product_id in product_order:
                    if product_id in self.config['available_products']:
                        product_info = self.config['available_products'][product_id]
                        status = "✅" if product_id in user_products else "❌"
                        product_list += f"{status} `{product_id}` - {product_info['name']}\n"
                
                product_list += "\n*Legend:*\n"
                product_list += "✅ = Currently being monitored\n"
                product_list += "❌ = Not being monitored\n\n"
                product_list += "*To add a product:* `/add <product_id>`\n"
                product_list += "*To remove a product:* `/remove <product_id>`"
                
                await self.send_message(chat_id, product_list)
            
            elif command == '/status':
                if chat_id not in self.users:
                    await self.send_message(chat_id, "❌ You're not registered. Use /start to begin.")
                    return
                
                user_products = self.users[chat_id].get('monitored_products', [])
                if not user_products:
                    status_msg = "📊 *Your Monitoring Status:*\n\n"
                    status_msg += "❌ *No products currently being monitored*\n\n"
                    status_msg += "Use `/add <product_id>` to start monitoring a product.\n"
                    status_msg += "Use `/list` to see all available products.\n"
                    status_msg += "Use `/default` to reset to default (Ikuyo 100g only)."
                    await self.send_message(chat_id, status_msg)
                else:
                    status_msg = f"📊 *Your Monitoring Status:*\n\n"
                    status_msg += f"Currently monitoring **{len(user_products)}** product(s):\n\n"
                    
                    for product_id in user_products:
                        if product_id in self.config['available_products']:
                            status_msg += f"✅ {self.config['available_products'][product_id]['name']}\n"
                    
                    status_msg += "\n*To add more products:* `/add <product_id>`\n"
                    status_msg += "*To remove products:* `/remove <product_id>`\n"
                    status_msg += "*To see all products:* `/list`"
                    
                    await self.send_message(chat_id, status_msg)
            
            elif command == '/add':
                if chat_id not in self.users:
                    await self.send_message(chat_id, "❌ You're not registered. Use /start to begin.")
                    return
                
                parts = message_text.split()
                if len(parts) < 2:
                    await self.send_message(
                        chat_id, 
                        "❌ *Missing Product ID*\n\n"
                        "Please specify which product to add.\n\n"
                        "*Example:* `/add sayaka_40g`\n"
                        "*To see all products:* `/list`"
                    )
                    return
                
                product_id = parts[1]
                if product_id not in self.config['available_products']:
                    await self.send_message(
                        chat_id, 
                        f"❌ *Product Not Found*\n\n"
                        f"`{product_id}` is not a valid product ID.\n\n"
                        f"*To see all available products:* `/list`\n"
                        f"*Example valid IDs:* `sayaka_40g`, `ummon_20g`, `kan_30g`"
                    )
                    return
                
                user_products = self.users[chat_id].get('monitored_products', [])
                if product_id in user_products:
                    await self.send_message(
                        chat_id, 
                        f"ℹ️ *Already Monitoring*\n\n"
                        f"`{product_id}` is already in your monitoring list.\n\n"
                        f"Use `/status` to see all your monitored products.\n"
                        f"Use `/list` to see all available products."
                    )
                    return
                
                user_products.append(product_id)
                self.update_user_preferences(chat_id, user_products)
                await self.send_message(
                    chat_id, 
                    f"✅ *Added to monitoring:* `{product_id}`\n\n"
                    f"You're now monitoring **{len(user_products)}** product(s).\n"
                    f"Use `/status` to see all your monitored products.\n"
                    f"Use `/list` to see all available products."
                )
            
            elif command == '/remove':
                if chat_id not in self.users:
                    await self.send_message(chat_id, "❌ You're not registered. Use /start to begin.")
                    return
                
                parts = message_text.split()
                if len(parts) < 2:
                    await self.send_message(
                        chat_id, 
                        "❌ *Missing Product ID*\n\n"
                        "Please specify which product to remove.\n\n"
                        "*Example:* `/remove sayaka_40g`\n"
                        "*To see your monitored products:* `/status`"
                    )
                    return
                
                product_id = parts[1]
                user_products = self.users[chat_id].get('monitored_products', [])
                if product_id not in user_products:
                    await self.send_message(
                        chat_id, 
                        f"❌ *Not Being Monitored*\n\n"
                        f"`{product_id}` is not in your monitoring list.\n\n"
                        f"Use `/status` to see your currently monitored products.\n"
                        f"Use `/list` to see all available products."
                    )
                    return
                
                user_products = [p for p in user_products if p != product_id]
                self.update_user_preferences(chat_id, user_products)
                
                if user_products:
                    await self.send_message(
                        chat_id, 
                        f"✅ *Removed from monitoring:* `{product_id}`\n\n"
                        f"You're now monitoring **{len(user_products)}** product(s).\n"
                        f"Use `/status` to see all your monitored products.\n"
                        f"Use `/list` to see all available products."
                    )
                else:
                    await self.send_message(
                        chat_id, 
                        f"✅ *Removed from monitoring:* `{product_id}`\n\n"
                        f"❌ *No products currently being monitored*\n\n"
                        f"Use `/add <product_id>` to start monitoring a product.\n"
                        f"Use `/default` to reset to default (Ikuyo 100g only)."
                    )
            
            elif command == '/default':
                if chat_id not in self.users:
                    await self.send_message(chat_id, "❌ You're not registered. Use /start to begin.")
                    return
                
                self.update_user_preferences(chat_id, ['ikuyo_100g'])
                await self.send_message(
                    chat_id, 
                    "🔄 *Reset to Default*\n\n"
                    "✅ You're now monitoring **Ikuyo 100g** only.\n\n"
                    "Use `/add <product_id>` to add more products.\n"
                    "Use `/list` to see all available products.\n"
                    "Use `/status` to see your current monitoring."
                )
            
            elif command == '/help':
                await self.send_message(
                    chat_id,
                    "🍵 *Need Mo Matcha Bot Help*\n\n"
                    "I monitor Ippodo Tea matcha products (ippodotea.com) for stock changes.\n\n"
                    "*I'll send you notifications when:*\n"
                    "• Products come back in stock 🟢\n"
                    "• Products go out of stock 🔴\n"
                    "• Restocking messages change (e.g., \"back in 3 days\" or \"restocking weekly\")\n\n"
                    "*Commands:*\n"
                    "📋 `/list` - Show all products\n"
                    "📊 `/status` - Show your monitored products\n"
                    "➕ `/add <product_id>` - Add product to monitoring\n"
                    "➖ `/remove <product_id>` - Remove product\n"
                    "🔄 `/default` - Reset to default\n"
                    "❓ `/help` - Show this help\n\n"
                    "*To pause notifications:* Mute this chat in Telegram\n\n"
                    "*Examples:*\n"
                    "`/add sayaka_40g` - Monitor Sayaka 40g\n"
                    "`/remove ummon_20g` - Stop monitoring Ummon 20g\n\n"
                    "*Available Products:*\n"
                    "• **Ummon** - `ummon_40g`, `ummon_20g`\n"
                    "• **Sayaka** - `sayaka_100g`, `sayaka_40g`\n"
                    "• **Horai** - `horai_20g`\n"
                    "• **Kan** - `kan_30g`\n"
                    "• **Ikuyo** - `ikuyo_100g`, `ikuyo_30g`\n"
                    "• **Wakaki** - `wakaki_40g`"
                )
    
    async def monitor_products(self):
        """Main monitoring loop for all users"""
        print("🚀 Starting Need Mo Matcha Monitor...")
        print(f"⏰ Checking every {self.config['monitoring']['check_interval']} seconds")
        
        while True:
            try:
                print(f"\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Checking products...")
                
                # Track which products we've already checked this cycle
                checked_products = {}
                
                # Collect all unique products to check
                all_products_to_check = set()
                for user_data in self.users.values():
                    all_products_to_check.update(user_data.get('monitored_products', []))
                
                if not all_products_to_check:
                    print("  ⏸️ No products to monitor - waiting...")
                    await asyncio.sleep(self.config['monitoring']['check_interval'])
                    continue
                
                print(f"  📦 Checking {len(all_products_to_check)} unique products...")
                
                # Check all unique products once
                for product_id in all_products_to_check:
                    if product_id in self.config['available_products']:
                        product_config = self.config['available_products'][product_id]
                        
                        is_in_stock, message = self.check_product_stock(product_id, product_config)
                        checked_products[product_id] = (is_in_stock, message)
                        
                        if is_in_stock is None:
                            print(f"    ⚠️ {product_config['name']}: {message}")
                
                # Process results for each user
                for chat_id, user_data in self.users.items():
                    monitored_products = user_data.get('monitored_products', [])
                    user_stock_status = self.get_user_stock_status(chat_id)
                    
                    print(f"  👤 Processing {user_data.get('name', 'Unknown')} ({len(monitored_products)} products)")
                    
                    for product_id in monitored_products:
                        if product_id not in checked_products:
                            continue
                        
                        is_in_stock, message = checked_products[product_id]
                        
                        if is_in_stock is not None:  # Only process if we got a valid result
                            # Get previous status for this user
                            previous_status = user_stock_status.get(product_id, None)
                            
                            # Check if status or message changed
                            status_changed = False
                            message_changed = False
                            
                            if previous_status is not None:
                                # Handle new format (dict with in_stock and message)
                                if isinstance(previous_status, dict):
                                    prev_in_stock = previous_status.get('in_stock')
                                    prev_message = previous_status.get('message', '')
                                    
                                    status_changed = prev_in_stock != is_in_stock
                                    message_changed = prev_message != message
                                else:
                                    # Handle legacy format (just boolean)
                                    status_changed = previous_status != is_in_stock
                                    message_changed = True  # Always notify on first run with new format
                            else:
                                # First check
                                status_changed = True
                                message_changed = True
                            
                            # Send notification if status or message changed
                            if status_changed or message_changed:
                                if status_changed:
                                    print(f"      🔄 Status changed: {previous_status.get('in_stock') if isinstance(previous_status, dict) else previous_status} → {is_in_stock}")
                                if message_changed:
                                    print(f"      📝 Message changed: {previous_status.get('message', 'N/A') if isinstance(previous_status, dict) else 'N/A'} → {message}")
                                
                                product_config = self.config['available_products'][product_id]
                                await self.send_notification(
                                    chat_id,
                                    product_config['name'], 
                                    is_in_stock, 
                                    message, 
                                    product_config['url']
                                )
                            
                            # Update stored status for this user
                            user_stock_status[product_id] = {
                                'in_stock': is_in_stock,
                                'message': message
                            }
                        else:
                            # Check if this is a persistent error (product removed/changed)
                            if "not found" in message.lower() or "404" in message or "removed" in message.lower():
                                # Only notify once per day to avoid spam
                                last_error_time = user_stock_status.get(f"{product_id}_error_time", 0)
                                current_time = datetime.now().timestamp()
                                
                                if current_time - last_error_time > 86400:  # 24 hours
                                    product_config = self.config['available_products'][product_id]
                                    await self.notify_product_error(chat_id, product_config['name'], message)
                                    user_stock_status[f"{product_id}_error_time"] = current_time
                    
                    # Save user's stock status
                    self.save_user_stock_status(chat_id, user_stock_status)
                
                print(f"  💾 All user statuses saved. Waiting {self.config['monitoring']['check_interval']} seconds...")
                await asyncio.sleep(self.config['monitoring']['check_interval'])
                
            except Exception as e:
                print(f"💥 Error in monitoring loop: {e}")
                # Continue monitoring despite errors
                await asyncio.sleep(30)  # Wait a bit longer before retrying

async def handle_message(update: Update, bot_instance):
    """Handle incoming messages from Telegram"""
    chat_id = str(update.effective_chat.id)
    message_text = update.message.text
    
    # Handle the command
    await bot_instance.handle_command(chat_id, message_text)

async def main():
    bot = NeedMoMatchaBot()
    
    print("🤖 Starting bot with message handling...")
    
    # Check if we should send startup notifications based on previous states
    if bot.dev_mode:
        # In dev mode, always notify the dev user about maintenance mode
        await bot.notify_dev_mode_enabled()
    else:
        # In production mode, only notify if users were previously in 'maintenance' state
        # Check if any users were in maintenance mode
        users_in_maintenance = [chat_id for chat_id, state in bot.user_bot_states.items() 
                              if state == 'maintenance']
        
        if users_in_maintenance:
            # Only send resume notifications to users who were in maintenance
            for chat_id in users_in_maintenance:
                if bot.should_send_notification("maintenance_end", chat_id):
                    try:
                        resume_msg = (
                            "✅ *Bot Resumed*\n\n"
                            "The bot is back online and monitoring your products!\n\n"
                            "You'll receive notifications for stock changes as usual."
                        )
                        await bot.bot.send_message(
                            chat_id=chat_id,
                            text=resume_msg,
                            parse_mode='Markdown'
                        )
                        print(f"📱 Resume notification sent to {chat_id}")
                    except Exception as e:
                        print(f"❌ Error sending resume notification to {chat_id}: {e}")
    
    # Start monitoring in the background
    monitoring_task = asyncio.create_task(bot.monitor_products())
    
    try:
        # Simple polling loop for messages
        offset = 0
        while True:
            try:
                updates = await bot.bot.get_updates(offset=offset, timeout=30)
                for update in updates:
                    if update.message and update.message.text:
                        await handle_message(update, bot)
                    offset = update.update_id + 1
            except asyncio.CancelledError:
                print("🛑 Bot shutdown requested...")
                break
            except KeyboardInterrupt:
                print("🛑 KeyboardInterrupt caught in polling loop...")
                break
            except Exception as e:
                print(f"⚠️ Error in polling: {e}")
                await asyncio.sleep(5)
    except KeyboardInterrupt:
        print("🛑 Stopping bot...")
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        # Notify users about unexpected shutdown
        await bot.notify_unexpected_shutdown(str(e))
    finally:
        # Always try to send maintenance notification
        try:
            print("📱 Sending maintenance notifications...")
            await bot.notify_maintenance_start()
        except Exception as e:
            print(f"❌ Error sending maintenance notifications: {e}")
        
        # Cancel monitoring when bot stops
        monitoring_task.cancel()
        try:
            await monitoring_task
        except asyncio.CancelledError:
            pass
        
        print("✅ Bot shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Bot stopped by user")
    except Exception as e:
        print(f"💥 Fatal error: {e}") 