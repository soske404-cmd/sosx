"""
Medium Card Checker Response Formatter
"""

import json

def get_bin_details_safe(bin_number):
    """
    Safely get BIN details - fallback if TOOLS not available
    """
    try:
        from TOOLS.getbin import get_bin_details
        return get_bin_details(bin_number)
    except ImportError:
        # Fallback for Pydroid3 standalone
        return None


def format_medium_response(cc, mes, ano, cvv, status, message, raw_response, timet, profile, user_id=None):
    """
    Format the Medium checker response for Telegram
    
    Args:
        cc: Card number
        mes: Month
        ano: Year
        cvv: CVV
        status: Status string (LIVE, APPROVED, CCN, DECLINED, ERROR)
        message: Response message
        raw_response: Raw response from API
        timet: Time taken
        profile: User profile HTML
        user_id: User ID (optional)
    
    Returns:
        (status_flag, formatted_message)
    """
    fullcc = f"{cc}|{mes}|{ano}|{cvv}"
    gateway = "Medium Stripe 💳"
    
    # Determine status flag and emoji
    if status == "LIVE":
        status_flag = "Charged 💎"
    elif status == "APPROVED":
        status_flag = "Approved ✅"
    elif status == "CCN":
        status_flag = "Invalid CCN ❌"
    elif status == "DECLINED":
        status_flag = "Declined ❌"
    else:
        status_flag = "Error ⚠️"
    
    # Get BIN information
    bin_data = get_bin_details_safe(cc[:6]) or {}
    bin_info = {
        "bin": bin_data.get("bin", cc[:6]),
        "country": bin_data.get("country", "Unknown"),
        "flag": bin_data.get("flag", "🏳️"),
        "vendor": bin_data.get("vendor", "Unknown"),
        "type": bin_data.get("type", "Unknown"),
        "level": bin_data.get("level", "Unknown"),
        "bank": bin_data.get("bank", "Unknown")
    }
    
    # Get user plan info
    plan = "Free"
    badge = "🎟️"
    
    try:
        from BOT.helper.start import load_users
        users = load_users()
        if user_id:
            user_data = users.get(str(user_id), {})
            plan = user_data.get("plan", {}).get("plan", "Free")
            badge = user_data.get("plan", {}).get("badge", "🎟️")
    except:
        pass
    
    # Format response message
    result = f"""
<b>[#Medium] | Stripe Auth</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{fullcc}</code>
<b>[•] Gateway</b> - <b>{gateway}</b>
<b>[•] Status</b>- <code>{status_flag}</code>
<b>[•] Response</b>- <code>{message}</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Bin</b>: <code>{bin_info['bin']}</code>  
<b>[+] Info</b>: <code>{bin_info['vendor']} - {bin_info['type']} - {bin_info['level']}</code> 
<b>[+] Bank</b>: <code>{bin_info['bank']}</code> 🏦
<b>[+] Country</b>: <code>{bin_info['country']} - [{bin_info['flag']}]</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[ﾒ] Checked By</b>: {profile} [<code>{plan} {badge}</code>]
<b>[ϟ] Dev</b> ➺ <a href="https://t.me/syncblast">𝙎𝙮𝙣𝙘𝘽𝙡𝙖𝙨𝙩</a>
━━━━━━━━━━━━━━━
<b>[ﾒ] T/t</b>: <code>[{timet} 𝐬]</code> <b>|Gate:</b> [<code>Medium ⚡️</code>]
"""
    return status_flag, result


def format_medium_response_simple(fullcc, status, message, raw_response):
    """
    Simple response format for mass checking
    """
    if status == "LIVE":
        status_flag = "Charged 💎"
    elif status == "APPROVED":
        status_flag = "Approved ✅"
    elif status == "CCN":
        status_flag = "Invalid CCN ❌"
    elif status == "DECLINED":
        status_flag = "Declined ❌"
    else:
        status_flag = "Error ⚠️"
    
    return f"""• <b>Card :</b> <code>{fullcc}</code>
• <b>Status :</b> <code>{status_flag}</code>
• <b>Result :</b> <code>{message}</code>
━ ━ ━ ━ ━ ━━━ ━ ━ ━ ━ ━"""


def get_status_emoji(status):
    """Get emoji for status"""
    status_map = {
        "LIVE": "💎",
        "APPROVED": "✅", 
        "CCN": "❌",
        "DECLINED": "❌",
        "ERROR": "⚠️"
    }
    return status_map.get(status, "❓")


def is_hit(status):
    """Check if the result is a hit (LIVE or APPROVED)"""
    return status in ("LIVE", "APPROVED")


def is_live(status):
    """Check if the card is fully live"""
    return status == "LIVE"
