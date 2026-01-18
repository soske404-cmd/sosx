# AutoStripe Add URL Command - /addurl
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from BOT.Charge.AutoStripe.api import validate_site
import os
import json
import time

SITES_PATH = "DATA/sites.json"
TEST_CARD = "4403934091847371|06|2026|097"

def ensure_sites_file():
    """Ensure the sites.json file exists"""
    os.makedirs(os.path.dirname(SITES_PATH), exist_ok=True)
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
    """Handle /addurl command for adding AutoStripe sites"""
    args = message.command[1:]

    if len(args) < 1:
        return await message.reply(
            "<b>❌ Please provide a site URL.</b>\n"
            "Example: <code>/addurl dilaboards.com</code>\n\n"
            "<b>Note:</b> Only provide the domain name without http/https"
        )

    site = args[0].strip()
    
    # Clean the site URL
    site = site.replace("https://", "").replace("http://", "").replace("www.", "")
    if "/" in site:
        site = site.split("/")[0]

    user_id = str(message.from_user.id)
    clickable_name = f"<a href='tg://user?id={user_id}'>{message.from_user.first_name}</a>"
    start_time = time.time()
    
    wait_msg = await message.reply("<pre>[🔍 Validating Site... ]</pre>", reply_to_message_id=message.id)

    # Load existing sites
    all_sites = load_sites()

    # Check if user already has this site
    if user_id in all_sites and all_sites[user_id].get("site") == site:
        return await wait_msg.edit_text(
            "<pre>Site Already Added ⚠️</pre>\n"
            f"<b>Site:</b> <code>{site}</code>\n"
            "<b>Use /delurl to remove it first.</b>",
            parse_mode=ParseMode.HTML
        )

    # Validate the site with AutoStripe
    result = await validate_site(site, TEST_CARD)

    if not result:
        return await wait_msg.edit_text(
            "<pre>Site Not Supported ❌</pre>\n"
            f"<b>Site:</b> <code>{site}</code>\n"
            "<b>This site is not supported by AutoStripe.</b>",
            parse_mode=ParseMode.HTML
        )

    # Save the site for the user
    all_sites[user_id] = {
        "site": site,
        "gate": "AutoStripe"
    }
    save_sites(all_sites)

    end_time = time.time()
    time_taken = round(end_time - start_time, 2)

    await wait_msg.edit_text(
        f"<pre>Site Added Successfully ✅</pre>\n"
        f"━━━━━━━━━━━━━\n"
        f"[⌯] <b>Site:</b> <code>{site}</code>\n"
        f"[⌯] <b>Gateway:</b> <code>AutoStripe</code>\n"
        f"━━━━━━━━━━━━━\n"
        f"[⌯] <b>Commands:</b>\n"
        f"    • <code>/au cc|mm|yy|cvv</code> - Single Check\n"
        f"    • <code>/mau cc|mm|yy|cvv</code> - Mass Check\n"
        f"━━━━━━━━━━━━━\n"
        f"[⌯] <b>Time Taken:</b> <code>{time_taken} sec</code>\n"
        f"[⌯] <b>Added By:</b> {clickable_name}",
        parse_mode=ParseMode.HTML
    )


@Client.on_message(filters.command("delurl") & filters.private)
async def delurl_handler(client, message: Message):
    """Handle /delurl command for removing AutoStripe site"""
    user_id = str(message.from_user.id)

    all_sites = load_sites()

    if user_id not in all_sites:
        return await message.reply(
            "<pre>No Site Found ❌</pre>\n"
            "<b>You haven't added any site yet.</b>\n"
            "<b>Use /addurl to add a site.</b>"
        )

    removed_site = all_sites[user_id].get("site", "Unknown")
    del all_sites[user_id]
    save_sites(all_sites)

    await message.reply(
        f"<pre>Site Removed ✅</pre>\n"
        f"<b>Removed Site:</b> <code>{removed_site}</code>"
    )


@Client.on_message(filters.command("myurl") & filters.private)
async def myurl_handler(client, message: Message):
    """Handle /myurl command to show user's current site"""
    user_id = str(message.from_user.id)
    clickable_name = f"<a href='tg://user?id={user_id}'>{message.from_user.first_name}</a>"

    all_sites = load_sites()

    if user_id not in all_sites:
        return await message.reply(
            "<pre>No Site Found ❌</pre>\n"
            "<b>You haven't added any site yet.</b>\n"
            "<b>Use /addurl to add a site.</b>"
        )

    site_info = all_sites[user_id]

    await message.reply(
        f"<pre>Your AutoStripe Site ✦</pre>\n"
        f"━━━━━━━━━━━━━\n"
        f"[⌯] <b>Site:</b> <code>{site_info.get('site', 'N/A')}</code>\n"
        f"[⌯] <b>Gateway:</b> <code>{site_info.get('gate', 'AutoStripe')}</code>\n"
        f"━━━━━━━━━━━━━\n"
        f"[⌯] <b>User:</b> {clickable_name}"
    )
