# AutoStripe Mass Card Checker
# Command: /mau or .mau

import re
import time
import json
import asyncio
from pyrogram import Client, filters
from pyrogram.enums import ChatType

# Local imports - these match the existing file structure
from BOT.helper.start import load_users
from BOT.tools.proxy import get_proxy
from BOT.helper.permissions import check_private_access, load_allowed_groups
from BOT.gc.credit import deduct_credit_bulk
from BOT.Charge.AutoStripe.autostripe import check_card_autostripe

user_locks = {}

def chunk_cards(cards, size):
    """Chunk cards into batches"""
    for i in range(0, len(cards), size):
        yield cards[i:i + size]

def get_status_flag(raw_response):
    """Determine status flag from response"""
    response_upper = raw_response.upper() if raw_response else ""
    
    if any(x in response_upper for x in ["CHARGED", "SUCCESS", "ORDER_PLACED", "THANK YOU"]):
        return "Charged"
    elif any(x in response_upper for x in [
        "CCN", "CVV", "CVC", "3DS", "3D_SECURE", "INSUFFICIENT", 
        "INCORRECT_ZIP", "AVS", "MISMATCHED", "AUTHENTICATION"
    ]):
        return "Approved (CCN)"
    else:
        return "Declined"

def extract_cards(text):
    """Extract all cards from text"""
    return re.findall(r'(\d{12,19}\|\d{1,2}\|\d{2,4}\|\d{3,4})', text)

def load_sites():
    """Load sites from JSON file"""
    try:
        with open("DATA/sites.json", "r") as f:
            return json.load(f)
    except Exception:
        return {}

@Client.on_message(filters.command("mau") | filters.regex(r"^\.mau(\s|$)"))
async def mau_handler(client, message):
    user_id = str(message.from_user.id)

    if not message.from_user:
        return await message.reply("Cannot process this message. Comes From Channel")

    # Check if user already has a running request
    if user_id in user_locks:
        return await message.reply(
            "<pre>Wait!</pre>\n"
            "<b>Your previous</b> <code>/mau</code> <b>request is still processing.</b>\n"
            "<b>Please wait until it finishes.</b>",
            reply_to_message_id=message.id
        )

    user_locks[user_id] = True

    try:
        users = load_users()

        # Check if user is registered
        if user_id not in users:
            return await message.reply(
                "<pre>Access Denied</pre>\n"
                "<b>You have to register first using</b> <code>/register</code> <b>command.</b>",
                reply_to_message_id=message.id
            )

        # Check if group is allowed
        allowed_groups = load_allowed_groups()

        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP] and message.chat.id not in allowed_groups:
            return await message.reply(
                "<pre>Notification</pre>\n"
                "<b>~ Message :</b> <code>This Group Is Not Approved</code>\n"
                "<b>~ Contact  -></b> <b>@itzspoooky</b>\n"
                "-------------------\n"
                "<b>Contact Owner For Approving</b>",
                reply_to_message_id=message.id
            )

        # Check private access
        if not await check_private_access(message):
            return

        # Check proxy for mass checking
        proxy = get_proxy(user_id)
        if proxy is None:
            return await message.reply(
                "<pre>Proxy Error</pre>\n"
                "<b>~ Message :</b> <code>You Have To Add Proxy For Mass checking</code>\n"
                "<b>~ Command  -></b> <b>/setpx</b>\n",
                reply_to_message_id=message.id
            )
        
        user_data = users[user_id]
        plan_info = user_data.get("plan", {})
        mlimit = plan_info.get("mlimit")
        plan = plan_info.get("plan", "Free")
        badge = plan_info.get("badge", "")

        # Default limit if None
        if mlimit is None or str(mlimit).lower() in ["null", "none"]:
            mlimit = 10_000
        else:
            mlimit = int(mlimit)

        # Check if user has site set
        sites = load_sites()
        if user_id not in sites:
            await message.reply(
                "<pre>Site Not Found</pre>\n"
                "Error : <code>Please Set Site First</code>\n"
                "~ <code>Using /addurl in Bot's Private</code>",
                reply_to_message_id=message.id
            )
            return

        user_site_info = sites[user_id]
        site = user_site_info["site"]
        gateway = user_site_info.get("gate", "AutoStripe")

        # Extract cards from message
        target_text = None
        if message.reply_to_message and message.reply_to_message.text:
            target_text = message.reply_to_message.text
        elif len(message.text.split(maxsplit=1)) > 1:
            target_text = message.text.split(maxsplit=1)[1]

        if not target_text:
            return await message.reply(
                "Send cards!\n1 per line:\n4633438786747757|10|2025|298",
                reply_to_message_id=message.id
            )

        all_cards = extract_cards(target_text)
        if not all_cards:
            return await message.reply("No valid cards found!", reply_to_message_id=message.id)

        if len(all_cards) > mlimit:
            return await message.reply(
                f"You can check max {mlimit} cards as per your plan!",
                reply_to_message_id=message.id
            )

        # Check credits
        available_credits = user_data.get("plan", {}).get("credits", 0)
        card_count = len(all_cards)

        if available_credits != "inf":
            try:
                available_credits = int(available_credits)
                if card_count > available_credits:
                    return await message.reply(
                        "<pre>Notification</pre>\n"
                        "<b>Message :</b> <code>You Have Insufficient Credits</code>\n"
                        "<b>Get Credits To Use</b>\n"
                        "-------------------\n"
                        "<b>Type <code>/buy</code> to get Credits.</b>",
                        reply_to_message_id=message.id
                    )
            except Exception:
                return await message.reply(
                    "Error reading your credit balance.",
                    reply_to_message_id=message.id
                )

        checked_by = f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>"

        loader_msg = await message.reply(
            f"<pre>[$mau] | M-AutoStripe</pre>"
            f"<b>[>] Gateway -</b> <b>{gateway}</b>\n"
            f"<b>[>] CC Amount : {card_count}</b>\n"
            f"<b>[>] Checked By :</b> {checked_by} [<code>{plan} {badge}</code>]\n"
            f"<b>[>] Status :</b> <code>Processing Request..!</code>\n",
            reply_to_message_id=message.id
        )

        start_time = time.time()

        batch_size = 10
        final_results = []
        charged_count = 0
        approved_count = 0
        declined_count = 0

        for batch in chunk_cards(all_cards, batch_size):
            # Run check_card in parallel for current batch
            results = await asyncio.gather(*[
                check_card_autostripe(user_id, card) for card in batch
            ])

            # Process results from batch
            for card, raw_response in zip(batch, results):
                status_flag = get_status_flag(raw_response or "")
                
                if "Charged" in status_flag:
                    charged_count += 1
                    status_emoji = "[+]"
                elif "Approved" in status_flag:
                    approved_count += 1
                    status_emoji = "[~]"
                else:
                    declined_count += 1
                    status_emoji = "[-]"

                final_results.append(
                    f"<b>{status_emoji} Card :</b> <code>{card}</code>\n"
                    f"<b>{status_emoji} Status :</b> <code>{status_flag}</code>\n"
                    f"<b>{status_emoji} Result :</b> <code>{raw_response or '-'}</code>\n"
                    "-------------------"
                )

            # Edit after every batch
            try:
                await loader_msg.edit(
                    f"<pre>[$mau] | M-AutoStripe</pre>\n"
                    + "\n".join(final_results[-5:]) + "\n"  # Show last 5 results
                    f"<b>[>] Progress :</b> <code>{len(final_results)}/{card_count}</code>\n"
                    f"<b>[>] Checked By :</b> {checked_by} [<code>{plan} {badge}</code>]\n"
                    f"<b>[>] Dev :</b> <a href='https://t.me/syncblast'>SyncBlast</a>",
                    disable_web_page_preview=True
                )
            except Exception:
                pass  # Ignore edit errors

        end_time = time.time()
        timetaken = round(end_time - start_time, 2)

        # Deduct credits after processing
        if user_data["plan"].get("credits") != "inf":
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, deduct_credit_bulk, user_id, len(all_cards))

        # Build summary
        summary = f"""<pre>[$mau] | M-AutoStripe - Complete</pre>
-------------------
<b>[>] Total Cards :</b> <code>{card_count}</code>
<b>[+] Charged :</b> <code>{charged_count}</code>
<b>[~] Approved (CCN) :</b> <code>{approved_count}</code>
<b>[-] Declined :</b> <code>{declined_count}</code>
-------------------
<b>[>] Site :</b> <code>{site}</code>
<b>[>] Gateway :</b> <code>{gateway}</code>
<b>[>] T/t :</b> <code>{timetaken}s</code>
<b>[>] Checked By :</b> {checked_by} [<code>{plan} {badge}</code>]
<b>[>] Dev :</b> <a href='https://t.me/syncblast'>SyncBlast</a>"""

        # Send full results as text if many cards
        if card_count > 5:
            # Send summary first
            await loader_msg.edit(summary, disable_web_page_preview=True)
            
            # Send detailed results as separate message if needed
            full_results = "\n".join(final_results)
            if len(full_results) < 4000:
                await message.reply(
                    f"<pre>Detailed Results</pre>\n{full_results}",
                    disable_web_page_preview=True
                )
        else:
            # For few cards, show all results
            full_results = "\n".join(final_results)
            await loader_msg.edit(
                f"<pre>[$mau] | M-AutoStripe</pre>\n"
                f"{full_results}\n"
                f"<b>[>] T/t :</b> <code>{timetaken}s</code>\n"
                f"<b>[>] Checked By :</b> {checked_by} [<code>{plan} {badge}</code>]\n"
                f"<b>[>] Dev :</b> <a href='https://t.me/syncblast'>SyncBlast</a>",
                disable_web_page_preview=True
            )

    except Exception as e:
        await message.reply(f"Error: {e}", reply_to_message_id=message.id)

    finally:
        user_locks.pop(user_id, None)
