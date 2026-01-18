import os
import json
import time
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from autostripe_api import verify_autostripe_site

SITES_PATH = "DATA/sites.json"
TEST_CARD = "4342562842964445|04|26|568"

@Client.on_message(filters.command("addurl") & filters.private)
async def add_autostripe_site(client, message: Message):
    """Add AutoStripe site for user"""
    if len(message.command) < 2:
        return await message.reply(
            "❌ Please provide a site URL.\n\nExample:\n`/addurl dilaboards.com`",
            parse_mode=ParseMode.MARKDOWN
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
        # Verify site with AutoStripe
        result = await verify_autostripe_site(site, TEST_CARD)
        
        end_time = time.time()
        time_taken = round(end_time - start_time, 2)
        
        if result and result.get("supported"):
            gateway = result.get("gateway", "AutoStripe")
            response = result.get("response", "N/A")
            gate_name = f"AutoStripe {gateway}"
            
            # Load or create sites.json
            all_sites = {}
            if os.path.exists(SITES_PATH):
                with open(SITES_PATH, "r", encoding="utf-8") as f:
                    all_sites = json.load(f)
            
            # Save/overwrite user's site and gate
            all_sites[user_id] = {
                "site": site,
                "gate": gate_name
            }
            
            # Ensure DATA directory exists
            os.makedirs("DATA", exist_ok=True)
            
            with open(SITES_PATH, "w", encoding="utf-8") as f:
                json.dump(all_sites, f, indent=4)
            
            clickableFname = f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>"
            
            return await wait_msg.edit_text(
                f"""<pre>Site Added ✅~ AutoStripe ✦</pre>
[⌯] <b>Site:</b> <code>{site}</code> 
[⌯] <b>Gateway:</b> <code>{gate_name}</code> 
[⌯] <b>Response:</b> <code>{response[:100]}...</code> 
[⌯] <b>Cmd:</b> <code>/au</code> | <code>/mau</code>
[⌯] <b>Time Taken:</b> <code>{time_taken} sec</code> 
━━━━━━━━━━━━━
[⌯] <b>Req By:</b> {clickableFname}
[⌯] <b>Dev:</b> <a href="tg://resolve?domain=SyncUI">𝙁𝙪𝙧𝙠𝙖𝙣</a>""",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        
        else:
            return await wait_msg.edit_text(
                "<pre>Site Not Supported ❌</pre>\n"
                "<b>AutoStripe does not support this site.</b>",
                parse_mode=ParseMode.HTML
            )
    
    except Exception as e:
        time_taken = round(time.time() - start_time, 2)
        return await wait_msg.edit_text(
            f"⚠️ Error: `{str(e)}`\n⏱️ Time Taken: `{time_taken} sec`",
            parse_mode=ParseMode.MARKDOWN
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
    with open(SITES_PATH, "r", encoding="utf-8") as f:
        all_sites = json.load(f)
    
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
    
    with open(SITES_PATH, "r", encoding="utf-8") as f:
        all_sites = json.load(f)
    
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
