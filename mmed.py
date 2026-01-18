"""
Medium Stripe Mass Card Check Command
/mmed or .mmed command handler
"""

import re
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.enums import ChatType

from BOT.Charge.Medium.medium import check_card_full
from BOT.Charge.Medium.response import format_medium_response_simple
from BOT.helper.start import load_users
from BOT.tools.proxy import get_proxy
from BOT.helper.permissions import check_private_access, load_allowed_groups
from BOT.gc.credit import deduct_credit_bulk

# Lock to prevent multiple simultaneous checks per user
user_locks = {}


def chunk_cards(cards, size):
    """Split cards into chunks for batch processing"""
    for i in range(0, len(cards), size):
        yield cards[i:i + size]


def get_status_flag(status):
    """Get status flag from status code"""
    status_map = {
        "LIVE": "Charged 💎",
        "APPROVED": "Approved ✅",
        "CCN": "Invalid CCN ❌",
        "DECLINED": "Declined ❌",
        "ERROR": "Error ⚠️"
    }
    return status_map.get(status, "Unknown ❓")


def extract_cards(text):
    """Extract all cards from text"""
    return re.findall(r'(\d{12,19}\|\d{1,2}\|\d{2,4}\|\d{3,4})', text)


@Client.on_message(filters.command("mmed") | filters.regex(r"^\.mmed(\s|$)"))
async def mmed_handler(client, message):
    """Handle /mmed and .mmed commands for mass Medium Stripe checking"""
    user_id = str(message.from_user.id)
    
    if not message.from_user:
        return await message.reply("❌ Cannot process this message. Comes From Channel")
    
    # Check if user already has a running check
    if user_id in user_locks:
        return await message.reply(
            "<pre>⚠️ Wait!</pre>\n"
            "<b>Your previous</b> <code>/mmed</code> <b>request is still processing.</b>\n"
            "<b>Please wait until it finishes.</b>",
            reply_to_message_id=message.id
        )
    
    user_locks[user_id] = True
    
    try:
        users = load_users()
        
        # Check if user is registered
        if user_id not in users:
            return await message.reply(
                "<pre>Access Denied 🚫</pre>\n"
                "<b>You have to register first using</b> <code>/register</code> <b>command.</b>",
                reply_to_message_id=message.id
            )
        
        # Check if group is allowed
        allowed_groups = load_allowed_groups()
        
        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP] and message.chat.id not in allowed_groups:
            return await message.reply(
                "<pre>Notification ❗️</pre>\n"
                "<b>~ Message :</b> <code>This Group Is Not Approved ⚠️</code>\n"
                "<b>~ Contact  →</b> <b>@itzspoooky</b>\n"
                "━━━━━━━━━━━━━\n"
                "<b>Contact Owner For Approving</b>",
                reply_to_message_id=message.id
            )
        
        # Check private access
        if not await check_private_access(message):
            return
        
        # Get proxy (optional for Medium)
        proxy = get_proxy(user_id)
        
        # Get user plan info
        user_data = users[user_id]
        plan_info = user_data.get("plan", {})
        mlimit = plan_info.get("mlimit")
        plan = plan_info.get("plan", "Free")
        badge = plan_info.get("badge", "🎟️")
        
        # Default limit if not set
        if mlimit is None or str(mlimit).lower() in ["null", "none"]:
            mlimit = 10_000
        else:
            mlimit = int(mlimit)
        
        # Extract cards from message
        target_text = None
        if message.reply_to_message and message.reply_to_message.text:
            target_text = message.reply_to_message.text
        elif len(message.text.split(maxsplit=1)) > 1:
            target_text = message.text.split(maxsplit=1)[1]
        
        if not target_text:
            return await message.reply(
                "❌ Send cards!\n1 per line:\n4633438786747757|10|2025|298",
                reply_to_message_id=message.id
            )
        
        all_cards = extract_cards(target_text)
        if not all_cards:
            return await message.reply("❌ No valid cards found!", reply_to_message_id=message.id)
        
        # Check card limit
        if len(all_cards) > mlimit:
            return await message.reply(
                f"❌ You can check max {mlimit} cards as per your plan!",
                reply_to_message_id=message.id
            )
        
        # Check credits
        available_credits = user_data.get("plan", {}).get("credits", 0)
        card_count = len(all_cards)
        
        if available_credits != "∞":
            try:
                available_credits = int(available_credits)
                if card_count > available_credits:
                    return await message.reply(
                        "<pre>Notification ❗️</pre>\n"
                        "<b>Message :</b> <code>You Have Insufficient Credits</code>\n"
                        "<b>Get Credits To Use</b>\n"
                        "━━━━━━━━━━━━━\n"
                        "<b>Type <code>/buy</code> to get Credits.</b>",
                        reply_to_message_id=message.id
                    )
            except Exception:
                return await message.reply(
                    "⚠️ Error reading your credit balance.",
                    reply_to_message_id=message.id
                )
        
        checked_by = f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>"
        
        # Send loading message
        loader_msg = await message.reply(
            f"<pre>✦ [$mmed] | M-Medium Stripe</pre>"
            f"<b>[⚬] Gateway -</b> <b>Medium Stripe 💳</b>\n"
            f"<b>[⚬] CC Amount : {card_count}</b>\n"
            f"<b>[⚬] Checked By :</b> {checked_by} [<code>{plan} {badge}</code>]\n"
            f"<b>[⚬] Status :</b> <code>Processing Request..!</code>\n",
            reply_to_message_id=message.id
        )
        
        start_time = time.time()
        
        batch_size = 5  # Smaller batch for Stripe to avoid rate limits
        final_results = []
        hits = 0
        
        for batch in chunk_cards(all_cards, batch_size):
            # Run check_card in parallel for current batch
            results = await asyncio.gather(*[
                check_card_full(card, proxy) for card in batch
            ])
            
            # Process results from batch
            for card, (status, response_message, raw_response) in zip(batch, results):
                status_flag = get_status_flag(status)
                
                if status in ("LIVE", "APPROVED"):
                    hits += 1
                
                final_results.append(
                    f"• <b>Card :</b> <code>{card}</code>\n"
                    f"• <b>Status :</b> <code>{status_flag}</code>\n"
                    f"• <b>Result :</b> <code>{response_message or '-'}</code>\n"
                    "━ ━ ━ ━ ━ ━━━ ━ ━ ━ ━ ━"
                )
            
            # Edit after every batch
            try:
                await loader_msg.edit(
                    f"<pre>✦ [$mmed] | M-Medium Stripe</pre>\n"
                    + "\n".join(final_results[-20:]) + "\n"  # Show last 20 results
                    f"<b>[⚬] Progress :</b> <code>{len(final_results)}/{card_count}</code>\n"
                    f"<b>[⚬] Hits :</b> <code>{hits}</code>\n"
                    f"<b>[⚬] Checked By :</b> {checked_by} [<code>{plan} {badge}</code>]\n"
                    f"<b>[⚬] Dev :</b> <a href='https://t.me/syncblast'>𝙁𝙪𝙧𝙠𝙖𝙣</a>",
                    disable_web_page_preview=True
                )
            except Exception:
                pass  # Ignore edit errors
            
            # Small delay between batches
            await asyncio.sleep(1)
        
        end_time = time.time()
        timetaken = round(end_time - start_time, 2)
        
        # Deduct credits after processing
        if user_data["plan"].get("credits") != "∞":
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, deduct_credit_bulk, user_id, len(all_cards))
        
        # Final edit with summary
        summary = "\n".join(final_results[-15:]) if len(final_results) > 15 else "\n".join(final_results)
        
        await loader_msg.edit(
            f"<pre>✦ [$mmed] | M-Medium Stripe ✅</pre>\n"
            f"{summary}\n"
            f"<b>[⚬] Total Checked :</b> <code>{card_count}</code>\n"
            f"<b>[⚬] Hits :</b> <code>{hits}</code>\n"
            f"<b>[⚬] T/t :</b> <code>{timetaken}s</code>\n"
            f"<b>[⚬] Checked By :</b> {checked_by} [<code>{plan} {badge}</code>]\n"
            f"<b>[⚬] Dev :</b> <a href='https://t.me/syncblast'>𝙁𝙪𝙧𝙠𝙖𝙣</a>",
            disable_web_page_preview=True
        )
    
    except Exception as e:
        await message.reply(f"⚠️ Error: {e}", reply_to_message_id=message.id)
    
    finally:
        user_locks.pop(user_id, None)
