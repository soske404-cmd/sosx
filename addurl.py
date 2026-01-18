import os
import json
import time
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

SITES_PATH = "DATA/sites.json"
TEST_CARD = "4403934091847371|06|2026|097"

# AutoStripe API Config
AUTOSTRIPE_BASE_URL = "https://blackxcard-autostripe.onrender.com"
AUTOSTRIPE_GATEWAY = "autostripe"
AUTOSTRIPE_KEY = "Blackxcard"

@Client.on_message(filters.command("addurl") & filters.private)
async def add_autostripe_site(client, message: Message):
    """Add AutoStripe site for user"""
    if len(message.command) < 2:
        return await message.reply(
            "❌ Please provide a site URL.\n\nExample:\n<code>/addurl dilaboards.com</code>",
            parse_mode=ParseMode.HTML
        )
    
    site = message.command[1]
    # Clean the site URL
    site = site.replace("https://", "").replace("http://", "").strip("/")
    
    user_id = str(message.from_user.id)
    
    wait_msg = await message.reply(
        "<pre>[🔍 Checking AutoStripe Site..! ]</pre>",
        reply_to_message_id=message.id
    )
    
    start_time = time.time()
    
    try:
        # Build AutoStripe API URL
        url = f"{AUTOSTRIPE_BASE_URL}/gateway={AUTOSTRIPE_GATEWAY}/key={AUTOSTRIPE_KEY}/site={site}/cc={TEST_CARD}"
        
        async with httpx.AsyncClient(timeout=90.0) as http_client:
            response = await http_client.get(url)
            response_text = response.text.strip()
        
        end_time = time.time()
        time_taken = round(end_time - start_time, 2)
        
        # If we got a response, site is working
        if response_text and len(response_text) > 0:
            gate_name = "AutoStripe"
            
            # Ensure DATA directory exists
            os.makedirs("DATA", exist_ok=True)
            
            # Load or create sites.json
            all_sites = {}
            if os.path.exists(SITES_PATH):
                try:
                    with open(SITES_PATH, "r", encoding="utf-8") as f:
                        all_sites = json.load(f)
                except:
                    all_sites = {}
            
            # Save/overwrite user's site and gate
            all_sites[user_id] = {
                "site": site,
                "gate": gate_name
            }
            
            with open(SITES_PATH, "w", encoding="utf-8") as f:
                json.dump(all_sites, f, indent=4)
            
            clickableFname = f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>"
            
            # Truncate response if too long
            display_response = response_text[:100] + "..." if len(response_text) > 100 else response_text
            
            return await wait_msg.edit_text(
                f"""<pre>Site Added ✅ ~ AutoStripe ✦</pre>
[⌯] <b>Site:</b> <code>{site}</code> 
[⌯] <b>Gateway:</b> <code>{gate_name}</code> 
[⌯] <b>Response:</b> <code>{display_response}</code> 
[⌯] <b>Cmd:</b> <code>/au</code> | <code>/mau</code>
[⌯] <b>Time Taken:</b> <code>{time_taken} sec</code> 
━━━━━━━━━━━━━
[⌯] <b>Req By:</b> {clickableFname}""",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        
        else:
            return await wait_msg.edit_text(
                "<pre>Site Not Supported ❌</pre>\n"
                "<b>No response from AutoStripe API.</b>",
                parse_mode=ParseMode.HTML
            )
    
    except httpx.TimeoutException:
        time_taken = round(time.time() - start_time, 2)
        return await wait_msg.edit_text(
            f"<pre>Timeout ❌</pre>\n<b>Request timed out.</b>\n⏱️ Time: <code>{time_taken} sec</code>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        time_taken = round(time.time() - start_time, 2)
        return await wait_msg.edit_text(
            f"⚠️ Error: <code>{str(e)}</code>\n⏱️ Time: <code>{time_taken} sec</code>",
            parse_mode=ParseMode.HTML
        )


@Client.on_message(filters.command("mysite") & filters.private)
async def show_my_site(client, message: Message):
    """Show user's current AutoStripe site"""
    user_id = str(message.from_user.id)
    clickableFname = f"<a href='tg://user?id={user_id}'>{message.from_user.first_name}</a>"
    
    # Check if data file exists
    if not os.path.exists(SITES_PATH):
        return await message.reply(
            "<pre>No Site Found ❌</pre>\n"
            "<b>Use /addurl to add a site.</b>",
            parse_mode=ParseMode.HTML
        )
    
    # Load JSON
    try:
        with open(SITES_PATH, "r", encoding="utf-8") as f:
            all_sites = json.load(f)
    except:
        return await message.reply(
            "<pre>No Site Found ❌</pre>\n"
            "<b>Use /addurl to add a site.</b>",
            parse_mode=ParseMode.HTML
        )
    
    user_site = all_sites.get(user_id)
    
    if not user_site:
        return await message.reply(
            "<pre>No Site Found ❌</pre>\n"
            "<b>Use /addurl to add a site.</b>",
            parse_mode=ParseMode.HTML
        )
    
    # UI message
    await message.reply(
        f"""<pre>Your AutoStripe Site ~ Sync ✦</pre>
[⌯] <b>Site:</b> <code>{user_site['site']}</code>
[⌯] <b>Gateway:</b> <code>{user_site.get('gate', 'AutoStripe')}</code>
━━━━━━━━━━━━━
[⌯] <b>Cmd:</b> <code>/au</code> | <code>/mau</code>
[⌯] <b>Req By:</b> {clickableFname}""",
        parse_mode=ParseMode.HTML
    )


@Client.on_message(filters.command("delsite") & filters.private)
async def delete_my_site(client, message: Message):
    """Delete user's AutoStripe site"""
    user_id = str(message.from_user.id)
    
    if not os.path.exists(SITES_PATH):
        return await message.reply(
            "<pre>No Site Found ❌</pre>",
            parse_mode=ParseMode.HTML
        )
    
    try:
        with open(SITES_PATH, "r", encoding="utf-8") as f:
            all_sites = json.load(f)
    except:
        return await message.reply(
            "<pre>No Site Found ❌</pre>",
            parse_mode=ParseMode.HTML
        )
    
    if user_id not in all_sites:
        return await message.reply(
            "<pre>No Site Found ❌</pre>",
            parse_mode=ParseMode.HTML
        )
    
    del all_sites[user_id]
    
    with open(SITES_PATH, "w", encoding="utf-8") as f:
        json.dump(all_sites, f, indent=4)
    
    await message.reply(
        "<pre>Site Removed ✅</pre>\n"
        "<b>Use /addurl to add a new site.</b>",
        parse_mode=ParseMode.HTML
    )
