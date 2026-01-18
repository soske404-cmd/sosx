import json
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

USERS_FILE = "DATA/users.json"

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

@Client.on_message(filters.command("info"))
async def info_command(client, message: Message):
    """Show user info"""
    users = load_users()
    
    # Check if replying to someone or checking self
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        user_id = str(target_user.id)
        name = target_user.first_name
    else:
        target_user = message.from_user
        user_id = str(message.from_user.id)
        name = message.from_user.first_name
    
    profile = f"<a href='tg://user?id={user_id}'>{name}</a>"
    
    if user_id not in users:
        return await message.reply(
            f"<pre>User Info ❌</pre>\n<b>User</b> {profile} <b>is not registered.</b>",
            parse_mode=ParseMode.HTML
        )
    
    user_data = users[user_id]
    plan_data = user_data.get("plan", {})
    
    plan_name = plan_data.get("plan", "Free")
    badge = plan_data.get("badge", "🎟️")
    credits = plan_data.get("credits", 0)
    antispam = plan_data.get("antispam", 15)
    mlimit = plan_data.get("mlimit", 5)
    private = plan_data.get("private", "off")
    registered_at = user_data.get("registered_at", "Unknown")
    
    # Get site info
    try:
        with open("DATA/sites.json", "r") as f:
            sites = json.load(f)
        user_site = sites.get(user_id, {}).get("site", "Not Set")
    except:
        user_site = "Not Set"
    
    info_text = f"""<pre>User Info ~ Sync ✦</pre>
━━━━━━━━━━━━━━━
<b>[•] Name:</b> {profile}
<b>[•] ID:</b> <code>{user_id}</code>
<b>[•] Plan:</b> <code>{plan_name} {badge}</code>
<b>[•] Credits:</b> <code>{credits}</code>
<b>[•] Antispam:</b> <code>{antispam}s</code>
<b>[•] Mass Limit:</b> <code>{mlimit}</code>
<b>[•] Private:</b> <code>{private}</code>
<b>[•] Site:</b> <code>{user_site}</code>
<b>[•] Registered:</b> <code>{registered_at}</code>
━━━━━━━━━━━━━━━"""
    
    await message.reply(info_text, parse_mode=ParseMode.HTML)


@Client.on_message(filters.command("me"))
async def me_command(client, message: Message):
    """Show own info"""
    users = load_users()
    user_id = str(message.from_user.id)
    name = message.from_user.first_name
    profile = f"<a href='tg://user?id={user_id}'>{name}</a>"
    
    if user_id not in users:
        return await message.reply(
            f"<pre>Not Registered ❌</pre>\n<b>Use /register first.</b>",
            parse_mode=ParseMode.HTML
        )
    
    user_data = users[user_id]
    plan_data = user_data.get("plan", {})
    
    plan_name = plan_data.get("plan", "Free")
    badge = plan_data.get("badge", "🎟️")
    credits = plan_data.get("credits", 0)
    antispam = plan_data.get("antispam", 15)
    mlimit = plan_data.get("mlimit", 5)
    private = plan_data.get("private", "off")
    
    try:
        with open("DATA/sites.json", "r") as f:
            sites = json.load(f)
        user_site = sites.get(user_id, {}).get("site", "Not Set")
    except:
        user_site = "Not Set"
    
    info_text = f"""<pre>My Info ~ Sync ✦</pre>
━━━━━━━━━━━━━━━
<b>[•] Name:</b> {profile}
<b>[•] Plan:</b> <code>{plan_name} {badge}</code>
<b>[•] Credits:</b> <code>{credits}</code>
<b>[•] Antispam:</b> <code>{antispam}s</code>
<b>[•] Mass Limit:</b> <code>{mlimit}</code>
<b>[•] Private:</b> <code>{private}</code>
<b>[•] Site:</b> <code>{user_site}</code>
━━━━━━━━━━━━━━━"""
    
    await message.reply(info_text, parse_mode=ParseMode.HTML)
