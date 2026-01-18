"""
Medium Stripe Single Card Check Command
/med or .med command handler
"""

import re
from time import time
from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from BOT.helper.start import load_users
from BOT.helper.antispam import can_run_command
from BOT.helper.permissions import check_private_access, load_allowed_groups
from BOT.Charge.Medium.medium import check_card_full
from BOT.Charge.Medium.response import format_medium_response
from BOT.gc.credit import has_credits, deduct_credit


def extract_card(text):
    """Extract card details from text in format: cc|mm|yy|cvv"""
    match = re.search(r'(\d{12,19})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})', text)
    if match:
        return match.groups()
    return None


@Client.on_message(filters.command("med") | filters.regex(r"^\.med(\s|$)"))
async def handle_medium_check(client, message):
    """Handle /med and .med commands for Medium Stripe checker"""
    try:
        # Check if group is allowed
        allowed_groups = load_allowed_groups()
        
        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP] and message.chat.id not in allowed_groups:
            return await message.reply(
                "<pre>Notification ❗️</pre>\n"
                "<b>~ Message :</b> <code>This Group Is Not Approved ⚠️</code>\n"
                "<b>~ Contact  →</b> <b>@itzspoooky</b>\n"
                "━━━━━━━━━━━━━\n"
                "<b>Contact Owner For Approving</b>"
            )
        
        users = load_users()
        user_id = str(message.from_user.id)
        
        # Check if user is registered
        if user_id not in users:
            return await message.reply(
                """<pre>Access Denied 🚫</pre>
<b>You have to register first using</b> <code>/register</code> <b>command.</b>""",
                reply_to_message_id=message.id
            )
        
        # Check private access
        if not await check_private_access(message):
            return
        
        # Check credits
        if not has_credits(user_id):
            return await message.reply(
                """<pre>Notification ❗️</pre>
<b>Message :</b> <code>You Have Insufficient Credits</code>
<b>Get Credits To Use</b>
━━━━━━━━━━━━━
<b>Type <code>/buy</code> to get Credits.</b>""",
                reply_to_message_id=message.id
            )
        
        # Extract card from command or replied message
        target_text = None
        if message.reply_to_message and message.reply_to_message.text:
            target_text = message.reply_to_message.text
        elif len(message.text.split(maxsplit=1)) > 1:
            target_text = message.text.split(maxsplit=1)[1]
        
        if not target_text:
            return await message.reply(
                f"""<pre>CC Not Found ❌</pre>
<b>Error:</b> <code>No CC Found in your input</code>
<b>Usage:</b> <code>/med cc|mm|yy|cvv</code>""",
                reply_to_message_id=message.id
            )
        
        extracted = extract_card(target_text)
        if not extracted:
            return await message.reply(
                f"""<pre>Invalid Format ❌</pre>
<b>Error:</b> <code>Send CC in Correct Format</code>
<b>Usage:</b> <code>/med cc|mm|yy|cvv</code>""",
                reply_to_message_id=message.id
            )
        
        # Check antispam
        allowed, wait_time = can_run_command(user_id, users)
        if not allowed:
            return await message.reply(
                f"""<pre>Antispam Detected ⚠️</pre>
<b>Message:</b> <code>You are detected as spamming</code>
<code>Try after {wait_time}s to use me again</code> <b>OR</b>
<code>Reduce Antispam Time /buy Using Paid Plan</code>""",
                reply_to_message_id=message.id
            )
        
        card, mes, ano, cvv = extracted
        fullcc = f"{card}|{mes}|{ano}|{cvv}"
        
        start_time = time()
        
        # Send loading message
        loading_msg = await message.reply(
            "<pre>Processing Your Request..!</pre>",
            reply_to_message_id=message.id
        )
        
        await loading_msg.edit(
            f"<pre>Processing Your Request..!</pre>\n"
            f"━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━\n"
            f"• <b>Card -</b> <code>{fullcc}</code>\n"
            f"• <b>Gate -</b> <code>Medium Stripe 💳</code>"
        )
        
        # Check the card
        status, response_message, raw_response = await check_card_full(fullcc)
        
        await loading_msg.edit(
            f"<pre>Processed ✔️</pre>\n"
            f"━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━\n"
            f"• <b>Card -</b> <code>{fullcc}</code>\n"
            f"• <b>Gate -</b> <code>Medium Stripe 💳</code>"
        )
        
        end_time = time()
        timetaken = round(end_time - start_time, 2)
        profile = f"<a href='tg://user?id={user_id}'>{message.from_user.first_name}</a>"
        
        # Format response
        status_flag, final_msg = format_medium_response(
            card, mes, ano, cvv,
            status, response_message, raw_response,
            timetaken, profile, user_id
        )
        
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Support", url="https://t.me/SyncUI"),
                InlineKeyboardButton("Plans", callback_data="plans_info")
            ]
        ])
        
        await loading_msg.edit(
            final_msg,
            reply_markup=buttons,
            disable_web_page_preview=True
        )
        
        # Deduct credit
        success, msg = deduct_credit(user_id)
        if not success:
            print("Credit deduction failed.")
    
    except Exception as e:
        print(f"Error in /med: {e}")
        await message.reply(
            "<code>Internal Error Occurred. Try again later.</code>",
            reply_to_message_id=message.id
        )
