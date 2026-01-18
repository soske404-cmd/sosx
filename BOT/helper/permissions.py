from pyrogram import Client, filters
from BOT.helper.start import load_users
from pyrogram.types import Message
import json
import os
from pyrogram.enums import ChatType

GROUPS_FILE = "DATA/groups.json"
CONFIG_FILE = "FILES/config.json"

def get_owner_id():
    """Get owner ID from config file"""
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        return int(config.get("OWNER", 0))
    except:
        return 0

def load_allowed_groups():
    if not os.path.exists(GROUPS_FILE):
        return []
    try:
        with open(GROUPS_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_allowed_groups(groups):
    os.makedirs("DATA", exist_ok=True)
    with open(GROUPS_FILE, "w") as f:
        json.dump(groups, f, indent=4)

async def is_premium_user(message: Message) -> bool:
    try:
        db = load_users()
        user_id = str(message.from_user.id)

        user_data = db.get(user_id)
        if not user_data:
            await message.reply("❌ User not found in database.")
            return False

        user_plan = user_data.get("plan", {}).get("plan", "Free")
        if user_plan in ["Free", "Redeem Code"]:
            await message.reply_text(
                "<pre>Notification ❗️</pre>\n"
                "<b>~ Message :</b> <code>Only For Premium Users !</code>\n"
                '<b>~ Buy Premium →</b> <b><a href="t.me.itzspoooky">Click Here</a></b>\n'
                "━━━━━━━━━━━━━\n"
                "<b>Type <code>/buy</code> to get Premium.</b>",
                quote=True
            )
            return False

        return True
    except Exception as e:
        return False

async def check_private_access(message: Message) -> bool:
    try:
        allowed_groups = load_allowed_groups()
        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            if message.chat.id in allowed_groups:
                return True

        db = load_users()
        user_id = str(message.from_user.id)
        user_data = db.get(user_id)

        if not user_data:
            await message.reply("❌ User not found in database.")
            return False

        private_status = user_data.get("plan", {}).get("private", "off")
        if private_status != "on":
            await message.reply_text(
                "<pre>Notification ❗️</pre>\n"
                "<b>~ Message :</b> <code>Only For Premium Users !</code>\n"
                "<b>~ Use Free In Chat →</b> Click Here\n"
                "━━━━━━━━━━━━━\n"
                "<b>Type <code>/buy</code> to get Premium.</b>",
                quote=True
            )
            return False

        return True
    except Exception as e:
        return False

# Ensure groups file exists
if not os.path.exists(GROUPS_FILE):
    os.makedirs("DATA", exist_ok=True)
    with open(GROUPS_FILE, "w") as f:
        json.dump([], f)

@Client.on_message(filters.command(["add", "addg"]))
async def add_group(client: Client, message: Message):
    """Add group to allowed list - Owner only"""
    owner_id = get_owner_id()
    
    if message.from_user.id != owner_id:
        return await message.reply("❌ Only owner can use this command.")
    
    try:
        if len(message.command) < 2:
            # If no argument, use current chat
            if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                chat_id = message.chat.id
            else:
                return await message.reply("❌ Format: /add -100xxxx\nOr use in group to add current group.")
        else:
            chat_id = int(message.command[1])
        
        groups = load_allowed_groups()
        if chat_id in groups:
            return await message.reply(f"ℹ️ Group {chat_id} already approved.")
        
        groups.append(chat_id)
        save_allowed_groups(groups)
        await message.reply(f"✅ Group <code>{chat_id}</code> approved!")
    except Exception as e:
        await message.reply(f"⚠️ Error: {e}")

@Client.on_message(filters.command(["rmv", "rmvg"]))
async def remove_group(client: Client, message: Message):
    """Remove group from allowed list - Owner only"""
    owner_id = get_owner_id()
    
    if message.from_user.id != owner_id:
        return await message.reply("❌ Only owner can use this command.")
    
    try:
        if len(message.command) < 2:
            if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                chat_id = message.chat.id
            else:
                return await message.reply("❌ Format: /rmv -100xxxx")
        else:
            chat_id = int(message.command[1])
        
        groups = load_allowed_groups()
        if chat_id not in groups:
            return await message.reply(f"ℹ️ Group {chat_id} not in approved list.")
        
        groups.remove(chat_id)
        save_allowed_groups(groups)
        await message.reply(f"✅ Group <code>{chat_id}</code> removed!")
    except Exception as e:
        await message.reply(f"⚠️ Error: {e}")

@Client.on_message(filters.command("groups"))
async def list_groups(client: Client, message: Message):
    """List all approved groups - Owner only"""
    owner_id = get_owner_id()
    
    if message.from_user.id != owner_id:
        return await message.reply("❌ Only owner can use this command.")
    
    groups = load_allowed_groups()
    
    if not groups:
        return await message.reply("<pre>No Approved Groups</pre>")
    
    group_list = "\n".join([f"• <code>{g}</code>" for g in groups])
    await message.reply(f"<pre>Approved Groups</pre>\n{group_list}\n\n<b>Total:</b> {len(groups)}")
