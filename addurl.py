from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from autostripe import test_site_autostripe
import os
import json
import time

SITES_PATH = "DATA/sites.json"

def ensure_sites_file():
    """Ensure the sites.json file exists"""
    if not os.path.exists("DATA"):
        os.makedirs("DATA")
    if not os.path.exists(SITES_PATH):
        with open(SITES_PATH, "w") as f:
            json.dump({}, f)

def load_sites():
    """Load sites from JSON file"""
    ensure_sites_file()
    with open(SITES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_sites(sites):
    """Save sites to JSON file"""
    ensure_sites_file()
    with open(SITES_PATH, "w", encoding="utf-8") as f:
        json.dump(sites, f, indent=4)


@Client.on_message(filters.command("addurl") & filters.private)
async def addurl_handler(client, message: Message):
    """
    Add a site URL for Autostripe checking
    Command: /addurl site.com
    """
    args = message.command[1:]

    if len(args) < 1:
        return await message.reply(
            "<pre>Invalid Format</pre>\n"
            "<b>Please provide a site URL.</b>\n"
            "<b>Example:</b> <code>/addurl dilaboards.com</code>",
            parse_mode=ParseMode.HTML
        )

    site = args[0].strip()
    
    # Clean the site URL (remove http/https if present)
    site = site.replace("https://", "").replace("http://", "")
    if site.endswith("/"):
        site = site[:-1]

    user_id = str(message.from_user.id)
    clickable_name = f"<a href='tg://user?id={user_id}'>{message.from_user.first_name}</a>"
    start_time = time.time()
    
    wait_msg = await message.reply(
        "<pre>[Checking Site..!]</pre>",
        reply_to_message_id=message.id,
        parse_mode=ParseMode.HTML
    )

    # Test the site
    await wait_msg.edit_text(
        f"<pre>[Testing Site..!]</pre>\n"
        f"<b>Site:</b> <code>{site}</code>\n"
        f"<b>Gateway:</b> <code>Autostripe</code>",
        parse_mode=ParseMode.HTML
    )

    result = await test_site_autostripe(site)

    if not result:
        return await wait_msg.edit_text(
            "<pre>Site Not Supported</pre>\n"
            f"<b>Site:</b> <code>{site}</code>\n"
            "<b>Error:</b> <code>Site is not compatible with Autostripe</code>\n"
            "<b>Try another site or check the URL</b>",
            parse_mode=ParseMode.HTML
        )

    # Save the site for user
    sites = load_sites()
    sites[user_id] = {
        "site": site,
        "gate": "Autostripe",
        "added_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    save_sites(sites)

    end_time = time.time()
    timetaken = round(end_time - start_time, 2)

    await wait_msg.edit_text(
        f"<pre>Site Added Successfully</pre>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<b>[*] Site:</b> <code>{site}</code>\n"
        f"<b>[*] Gateway:</b> <code>Autostripe</code>\n"
        f"<b>[*] Status:</b> <code>Active</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<b>[*] Commands:</b>\n"
        f"    <code>/au cc|mm|yy|cvv</code> - Single Check\n"
        f"    <code>/mau</code> - Mass Check\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<b>[*] Time Taken:</b> <code>{timetaken}s</code>\n"
        f"<b>[*] Added By:</b> {clickable_name}",
        parse_mode=ParseMode.HTML
    )


@Client.on_message(filters.command("myurl") & filters.private)
async def myurl_handler(client, message: Message):
    """
    Show user's current site URL
    Command: /myurl
    """
    user_id = str(message.from_user.id)
    clickable_name = f"<a href='tg://user?id={user_id}'>{message.from_user.first_name}</a>"

    sites = load_sites()
    
    if user_id not in sites:
        return await message.reply(
            "<pre>No Site Found</pre>\n"
            "<b>You haven't added any site yet.</b>\n"
            "<b>Use:</b> <code>/addurl site.com</code>",
            parse_mode=ParseMode.HTML
        )

    user_site = sites[user_id]
    site = user_site.get("site", "Unknown")
    gate = user_site.get("gate", "Autostripe")
    added_at = user_site.get("added_at", "Unknown")

    await message.reply(
        f"<pre>Your Site Info</pre>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<b>[*] Site:</b> <code>{site}</code>\n"
        f"<b>[*] Gateway:</b> <code>{gate}</code>\n"
        f"<b>[*] Added At:</b> <code>{added_at}</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<b>[*] User:</b> {clickable_name}",
        parse_mode=ParseMode.HTML
    )


@Client.on_message(filters.command("delurl") & filters.private)
async def delurl_handler(client, message: Message):
    """
    Delete user's current site URL
    Command: /delurl
    """
    user_id = str(message.from_user.id)

    sites = load_sites()
    
    if user_id not in sites:
        return await message.reply(
            "<pre>No Site Found</pre>\n"
            "<b>You haven't added any site to delete.</b>",
            parse_mode=ParseMode.HTML
        )

    deleted_site = sites[user_id].get("site", "Unknown")
    del sites[user_id]
    save_sites(sites)

    await message.reply(
        f"<pre>Site Removed Successfully</pre>\n"
        f"<b>Removed Site:</b> <code>{deleted_site}</code>",
        parse_mode=ParseMode.HTML
    )


@Client.on_message(filters.command("siteinfo") & filters.private)
async def siteinfo_handler(client, message: Message):
    """
    Alias for /myurl - Show user's current site URL
    Command: /siteinfo
    """
    await myurl_handler(client, message)
