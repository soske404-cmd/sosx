import json

def get_bin_details(bin_number):
    """Get BIN details - placeholder for actual BIN lookup"""
    try:
        from TOOLS.getbin import get_bin_details as lookup_bin
        return lookup_bin(bin_number)
    except:
        return {
            "bin": bin_number,
            "country": "Unknown",
            "flag": "🏳️",
            "vendor": "Unknown",
            "type": "Unknown",
            "level": "Unknown",
            "bank": "Unknown"
        }

def load_users():
    """Load users from JSON file"""
    try:
        with open("DATA/users.json", "r") as f:
            return json.load(f)
    except:
        return {}

def format_autostripe_response(cc, mes, ano, cvv, raw_response, timet, profile):
    """Format AutoStripe checker response"""
    fullcc = f"{cc}|{mes}|{ano}|{cvv}"
    
    # Extract user_id from profile
    try:
        user_id = profile.split("id=")[-1].split("'")[0]
    except Exception:
        user_id = None
    
    # Load gateway from DATA/sites.json
    try:
        with open("DATA/sites.json", "r") as f:
            sites = json.load(f)
        gateway = sites.get(user_id, {}).get("gate", "AutoStripe")
    except Exception:
        gateway = "AutoStripe"
    
    # Clean response
    raw_response = str(raw_response) if raw_response else "-"
    
    # Determine status based on response
    response_upper = raw_response.upper()
    
    # Charged keywords
    if any(keyword in response_upper for keyword in ["CHARGED", "ORDER_PLACED", "THANK YOU", "PAYMENT SUCCESS"]):
        status_flag = "Charged 💎"
    # Approved keywords (including succeed)
    elif any(keyword in response_upper for keyword in [
        "SUCCEED", "SUCCESS", "3DS", "3D_SECURE", "3D SECURE",
        "INSUFFICIENT_FUNDS", "INSUFFICIENT FUNDS", 
        "INVALID_CVC", "INVALID CVC", "INCORRECT_CVC", "INCORRECT CVC",
        "CVV", "CVC", "AUTHENTICATION", "ZIP", "ADDRESS", "BILLING",
        "CARD_ERROR", "CARD ERROR", "RISK", "FRAUD", "LIMIT",
        "DO_NOT_HONOR", "DO NOT HONOR", "LOST", "STOLEN"
    ]):
        status_flag = "Approved ✅"
    # Declined keywords
    elif any(keyword in response_upper for keyword in [
        "DECLINED", "DECLINE", "REJECTED", "REJECT", "FAILED", "FAIL",
        "INVALID CARD", "INVALID_CARD", "CARD_DECLINED", "CARD DECLINED",
        "NOT SUPPORTED", "UNSUPPORTED", "EXPIRED", "DEAD"
    ]):
        status_flag = "Declined ❌"
    else:
        status_flag = "Declined ❌"
    
    # BIN lookup
    bin_data = get_bin_details(cc[:6]) or {}
    bin_info = {
        "bin": bin_data.get("bin", cc[:6]),
        "country": bin_data.get("country", "Unknown"),
        "flag": bin_data.get("flag", "🏳️"),
        "vendor": bin_data.get("vendor", "Unknown"),
        "type": bin_data.get("type", "Unknown"),
        "level": bin_data.get("level", "Unknown"),
        "bank": bin_data.get("bank", "Unknown")
    }
    
    # User Plan
    try:
        users = load_users()
        user_data = users.get(user_id, {})
        plan = user_data.get("plan", {}).get("plan", "Free")
        badge = user_data.get("plan", {}).get("badge", "🎟️")
    except Exception:
        plan = "Unknown"
        badge = "❔"
    
    # Final formatted message
    result = f"""
<b>[#AutoStripe] | Sync</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{fullcc}</code>
<b>[•] Gateway</b> - <b>{gateway}</b>
<b>[•] Status</b>- <code>{status_flag}</code>
<b>[•] Response</b>- <code>{raw_response}</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Bin</b>: <code>{bin_info['bin']}</code>  
<b>[+] Info</b>: <code>{bin_info['vendor']} - {bin_info['type']} - {bin_info['level']}</code> 
<b>[+] Bank</b>: <code>{bin_info['bank']}</code> 🏦
<b>[+] Country</b>: <code>{bin_info['country']} - [{bin_info['flag']}]</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[ﾒ] Checked By</b>: {profile} [<code>{plan} {badge}</code>]
<b>[ϟ] Dev</b> ➺ <a href="https://t.me/syncblast">𝙎𝙮𝙣𝙘𝘽𝙡𝙖𝙨𝙩</a>
━━━━━━━━━━━━━━━
<b>[ﾒ] T/t</b>: <code>[{timet} 𝐬]</code> <b>|P/x:</b> [<code>Live ⚡️</code>]
"""
    return status_flag, result


def get_status_flag(raw_response):
    """Determine status flag from response text"""
    response_upper = str(raw_response).upper()
    
    # Charged keywords
    if any(keyword in response_upper for keyword in ["CHARGED", "ORDER_PLACED", "THANK YOU", "PAYMENT SUCCESS"]):
        return "Charged 💎"
    # Approved keywords (including succeed)
    elif any(keyword in response_upper for keyword in [
        "SUCCEED", "SUCCESS", "3DS", "3D_SECURE", "3D SECURE",
        "INSUFFICIENT_FUNDS", "INSUFFICIENT FUNDS",
        "INVALID_CVC", "INVALID CVC", "INCORRECT_CVC", "INCORRECT CVC",
        "CVV", "CVC", "AUTHENTICATION", "ZIP", "ADDRESS", "BILLING", "MISMATCHED",
        "CARD_ERROR", "CARD ERROR", "RISK", "FRAUD", "LIMIT",
        "DO_NOT_HONOR", "DO NOT HONOR", "LOST", "STOLEN"
    ]):
        return "Approved ✅"
    # Declined keywords
    elif any(keyword in response_upper for keyword in [
        "DECLINED", "DECLINE", "REJECTED", "REJECT", "FAILED", "FAIL",
        "INVALID CARD", "INVALID_CARD", "CARD_DECLINED", "CARD DECLINED",
        "NOT SUPPORTED", "UNSUPPORTED", "EXPIRED", "DEAD"
    ]):
        return "Declined ❌"
    else:
        return "Declined ❌"
