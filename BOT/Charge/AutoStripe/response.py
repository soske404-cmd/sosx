# AutoStripe Response Formatter
import json
from BOT.helper.start import load_users
from TOOLS.getbin import get_bin_details

def get_status_from_response(raw_response: str) -> str:
    """Determine status flag from API response"""
    response_upper = raw_response.upper() if raw_response else ""
    
    # Charged patterns
    charged_patterns = [
        "CHARGED", "ORDER_PLACED", "THANK YOU", "SUCCESS", 
        "APPROVED", "PAYMENT_COMPLETE", "COMPLETED"
    ]
    
    # CCN/CVV patterns (approved but needs verification)
    ccn_patterns = [
        "3D CC", "3DS_REQUIRED", "3D_AUTHENTICATION", "3D_SECURE",
        "MISMATCHED_BILLING", "MISMATCHED_PIN", "MISMATCHED_ZIP",
        "INSUFFICIENT_FUNDS", "INVALID_CVC", "INCORRECT_CVC",
        "MISMATCHED_BILL", "INCORRECT_ZIP", "INCORRECT_ADDRESS",
        "CVV", "CVC", "AUTHENTICATION_REQUIRED", "CCN"
    ]
    
    for pattern in charged_patterns:
        if pattern in response_upper:
            return "Charged 💎"
    
    for pattern in ccn_patterns:
        if pattern in response_upper:
            return "CCN ✅"
    
    return "Declined ❌"


def format_autostripe_response(cc, mes, ano, cvv, raw_response, timet, profile):
    """Format the response for AutoStripe checker"""
    fullcc = f"{cc}|{mes}|{ano}|{cvv}"

    # Extract user_id
    try:
        user_id = profile.split("id=")[-1].split("'")[0]
    except Exception:
        user_id = None

    # Load gateway from DATA/sites.json
    try:
        with open("DATA/sites.json", "r") as f:
            sites = json.load(f)
        site_info = sites.get(user_id, {})
        gateway = site_info.get("gate", "AutoStripe")
        site = site_info.get("site", "Unknown")
    except Exception:
        gateway = "AutoStripe"
        site = "Unknown"

    # Clean response
    raw_response = str(raw_response) if raw_response else "-"

    # Determine status
    status_flag = get_status_from_response(raw_response)

    # BIN lookup
    bin_data = get_bin_details(cc[:6]) if len(cc) >= 6 else {}
    bin_info = {
        "bin": bin_data.get("bin", cc[:6] if len(cc) >= 6 else "N/A"),
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
<b>[•] Site</b> - <code>{site}</code>
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
<b>[ﾒ] T/t</b>: <code>[{timet} 𝐬]</code>
"""
    return status_flag, result
