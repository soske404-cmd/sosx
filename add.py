# AutoStripe - Add Site URL Command
# Command: /addurl

import os
import json
import time
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

from BOT.Charge.AutoStripe.autostripe import validate_site_autostripe

SITES_PATH = "DATA/sites.json"
TEST_CARD = "4403934091847371|06|2026|097"

@Client.on_message(filters.command("addurl") & filters.private)
async def add_site_autostripe(client, message: Message):
    """Add a site for AutoStripe checking"""
    if len(message.command) < 2:
        return await message.reply(
            "<pre>Usage Error</pre>\n"
            "<b>Please provide a site URL.</b>\n\n"
            "<b>Example:</b>\n<code>/addurl example.com</code>",
            parse_mode=ParseMode.HTML
        )

    site = message.command[1].strip()
    
    # Remove protocol if provided
    site = site.replace("https://", "").replace("http://", "").rstrip("/")
    
    user_id = str(message.from_user.id)
    clickableFname = f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>"

    wait_msg = await message.reply("<pre>[Checking Site...!]</pre>", reply_to_message_id=message.id)
    start_time = time.time()

    try:
        # Validate the site with AutoStripe
        result = await validate_site_autostripe(site, TEST_CARD)

        end_time = time.time()
        time_taken = round(end_time - start_time, 2)

        if result:
            # Site is supported - save it
            all_sites = {}
            if os.path.exists(SITES_PATH):
                with open(SITES_PATH, "r", encoding="utf-8") as f:
                    all_sites = json.load(f)

            all_sites[user_id] = {
                "site": site,
                "gate": result.get("gate", "AutoStripe")
            }

            with open(SITES_PATH, "w", encoding="utf-8") as f:
                json.dump(all_sites, f, indent=4)

            return await wait_msg.edit_text(
                f"""<pre>Site Added - AutoStripe</pre>
-------------------
<b>[>] Site:</b> <code>{site}</code> 
<b>[>] Gateway:</b> <code>AutoStripe</code> 
<b>[>] Response:</b> <code>{result.get('response', 'Valid')}</code> 
<b>[>] Command:</b> <code>/au cc|mm|yy|cvv</code>
<b>[>] Mass Cmd:</b> <code>/mau (multiple cards)</code>
<b>[>] Time Taken:</b> <code>{time_taken} sec</code> 
-------------------
<b>[>] Req By:</b> {clickableFname}
<b>[>] Dev:</b> <a href="tg://resolve?domain=SyncUI">SyncBlast</a>""",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )

        else:
            return await wait_msg.edit_text(
                "<pre>Site Not Supported</pre>\n"
                "<b>The provided site may not be compatible with AutoStripe.</b>",
                parse_mode=ParseMode.HTML
            )

    except Exception as e:
        time_taken = round(time.time() - start_time, 2)
        return await wait_msg.edit_text(
            f"<pre>Error</pre>\n<code>{str(e)}</code>\n<b>Time:</b> <code>{time_taken} sec</code>", 
            parse_mode=ParseMode.HTML
        )

@Client.on_message(filters.command("mysite") & filters.private)
async def my_site_handler(client, message: Message):
    """Show user's current site"""
    user_id = str(message.from_user.id)
    
    if not os.path.exists(SITES_PATH):
        return await message.reply(
            "<pre>No Site Found</pre>\n<b>Use</b> <code>/addurl site.com</code> <b>to add a site.</b>",
            parse_mode=ParseMode.HTML
        )
    
    try:
        with open(SITES_PATH, "r") as f:
            sites = json.load(f)
        
        site_info = sites.get(user_id)
        if not site_info:
            return await message.reply(
                "<pre>No Site Found</pre>\n<b>Use</b> <code>/addurl site.com</code> <b>to add a site.</b>",
                parse_mode=ParseMode.HTML
            )
        
        return await message.reply(
            f"""<pre>Your AutoStripe Site</pre>
-------------------
<b>[>] Site:</b> <code>{site_info.get('site', 'Unknown')}</code>
<b>[>] Gateway:</b> <code>{site_info.get('gate', 'AutoStripe')}</code>
-------------------
<b>[>] Commands:</b>
<code>/au cc|mm|yy|cvv</code> - Single check
<code>/mau (cards)</code> - Mass check
<code>/delsite</code> - Remove site""",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        return await message.reply(f"<pre>Error</pre>\n<code>{str(e)}</code>", parse_mode=ParseMode.HTML)

@Client.on_message(filters.command("delsite") & filters.private)
async def delete_site_handler(client, message: Message):
    """Delete user's current site"""
    user_id = str(message.from_user.id)
    
    if not os.path.exists(SITES_PATH):
        return await message.reply(
            "<pre>No Site Found</pre>\n<b>Nothing to delete.</b>",
            parse_mode=ParseMode.HTML
        )
    
    try:
        with open(SITES_PATH, "r") as f:
            sites = json.load(f)
        
        if user_id not in sites:
            return await message.reply(
                "<pre>No Site Found</pre>\n<b>Nothing to delete.</b>",
                parse_mode=ParseMode.HTML
            )
        
        del sites[user_id]
        
        with open(SITES_PATH, "w") as f:
            json.dump(sites, f, indent=4)
        
        return await message.reply(
            "<pre>Site Removed</pre>\n<b>Your AutoStripe site has been deleted.</b>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        return await message.reply(f"<pre>Error</pre>\n<code>{str(e)}</code>", parse_mode=ParseMode.HTML)
