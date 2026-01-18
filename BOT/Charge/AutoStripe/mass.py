# AutoStripe Mass Checker - /mau command
import re
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.enums import ChatType
from BOT.Charge.AutoStripe.api import check_card, get_user_site
from BOT.Charge.AutoStripe.response import get_status_from_response
from BOT.helper.start import load_users
from BOT.tools.proxy import get_proxy
from BOT.helper.permissions import check_private_access, load_allowed_groups, is_premium_user
from BOT.gc.credit import deduct_credit_bulk
import json

user_locks = {}

def chunk_cards(cards, size):
    """Chunk cards into batches"""
    for i in range(0, len(cards), size):
        yield cards[i:i + size]

def extract_cards(text):
    """Extract all cards from text"""
    return re.findall(r'(\d{12,19}\|\d{1,2}\|\d{2,4}\|\d{3,4})', text)

def load_sites():
    """Load sites from JSON file"""
    try:
        with open("DATA/sites.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


@Client.on_message(filters.command("mau") | filters.regex(r"^\.mau(\s|$)"))
async def mau_handler(client, message):
    """Handle /mau command for mass card checking via AutoStripe"""
    user_id = str(message.from_user.id)

    if not message.from_user:
        return await message.reply("❌ Cannot process this message. Comes From Channel")

    if user_id in user_locks:
        return await message.reply(
            "<pre>⚠️ Wait!</pre>\n"
            "<b>Your previous</b> <code>/mau</code> <b>request is still processing.</b>\n"
            "<b>Please wait until it finishes.</b>", reply_to_message_id=message.id
        )

    user_locks[user_id] = True

    try:
        users = load_users()

        if user_id not in users:
            return await message.reply(
                "<pre>Access Denied 🚫</pre>\n"
                "<b>You have to register first using</b> <code>/register</code> <b>command.</b>",
                reply_to_message_id=message.id
            )

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

        if not await check_private_access(message):
            return

        proxy = get_proxy(user_id)
        if proxy == None:
            return await message.reply(
                "<pre>Proxy Error ❗️</pre>\n"
                "<b>~ Message :</b> <code>You Have To Add Proxy For Mass checking</code>\n"
                "<b>~ Command  →</b> <b>/setpx</b>\n",
                reply_to_message_id=message.id
            )
        
        user_data = users[user_id]
        plan_info = user_data.get("plan", {})
        mlimit = plan_info.get("mlimit")
        plan = plan_info.get("plan", "Free")
        badge = plan_info.get("badge", "🎟️")

        # Default unlimited if None
        if mlimit is None or str(mlimit).lower() in ["null", "none"]:
            mlimit = 10_000
        else:
            mlimit = int(mlimit)

        sites = load_sites()
        if user_id not in sites:
            await message.reply(
                "<pre>Site Not Found ⚠️</pre>\n"
                "Error : <code>Please Set Site First</code>\n"
                "~ <code>Using /addurl in Bot's Private</code>",
                reply_to_message_id=message.id
            )
            return

        user_site_info = sites[user_id]
        site = user_site_info["site"]
        gateway = user_site_info.get("gate", "AutoStripe")

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

        if len(all_cards) > mlimit:
            return await message.reply(
                f"❌ You can check max {mlimit} cards as per your plan!",
                reply_to_message_id=message.id
            )

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

        loader_msg = await message.reply(
            f"<pre>✦ [$mau] | M-AutoStripe</pre>"
            f"<b>[⚬] Gateway -</b> <b>{gateway}</b>\n"
            f"<b>[⚬] Site -</b> <code>{site}</code>\n"
            f"<b>[⚬] CC Amount : {card_count}</b>\n"
            f"<b>[⚬] Checked By :</b> {checked_by} [<code>{plan} {badge}</code>]\n"
            f"<b>[⚬] Status :</b> <code>Processing Request..!</code>\n",
            reply_to_message_id=message.id
        )

        start_time = time.time()

        batch_size = 5  # Process 5 cards at a time
        final_results = []

        for batch in chunk_cards(all_cards, batch_size):
            # Run check_card in parallel for current batch
            results = await asyncio.gather(*[
                check_card(user_id, card) for card in batch
            ])

            # Process results from batch
            for card, raw_response in zip(batch, results):
                status_flag = get_status_from_response(raw_response or "")

                final_results.append(
                    f"• <b>Card :</b> <code>{card}</code>\n"
                    f"• <b>Status :</b> <code>{status_flag}</code>\n"
                    f"• <b>Result :</b> <code>{raw_response or '-'}</code>\n"
                    "━ ━ ━ ━ ━ ━━━ ━ ━ ━ ━ ━"
                )

            # Edit after every batch
            try:
                await loader_msg.edit(
                    f"<pre>✦ [$mau] | M-AutoStripe</pre>\n"
                    + "\n".join(final_results) + "\n"
                    f"<b>[⚬] Checked By :</b> {checked_by} [<code>{plan} {badge}</code>]\n"
                    f"<b>[⚬] Dev :</b> <a href='https://t.me/syncblast'>𝙁𝙪𝙧𝙠𝙖𝙣</a>",
                    disable_web_page_preview=True
                )
            except Exception as e:
                print(f"Error updating message: {e}")

        end_time = time.time()
        timetaken = round(end_time - start_time, 2)

        # Deduct credits after processing
        if user_data["plan"].get("credits") != "∞":
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, deduct_credit_bulk, user_id, len(all_cards))

        # Final edit
        try:
            final_result_text = "\n".join(final_results)
            await loader_msg.edit(
                f"<pre>✦ [$mau] | M-AutoStripe</pre>\n"
                f"{final_result_text}\n"
                f"<b>[⚬] T/t :</b> <code>{timetaken}s</code>\n"
                f"<b>[⚬] Checked By :</b> {checked_by} [<code>{plan} {badge}</code>]\n"
                f"<b>[⚬] Dev :</b> <a href='https://t.me/syncblast'>𝙁𝙪𝙧𝙠𝙖𝙣</a>",
                disable_web_page_preview=True
            )
        except Exception as e:
            print(f"Error in final edit: {e}")

    except Exception as e:
        await message.reply(f"⚠️ Error: {e}", reply_to_message_id=message.id)

    finally:
        user_locks.pop(user_id, None)
