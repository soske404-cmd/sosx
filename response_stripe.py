# AutoStripe Response Formatter

import json
from TOOLS.getbin import get_bin_details
from BOT.helper.start import load_users

SITES_PATH = "DATA/sites.json"

def format_autostripe_response(cc, mes, ano, cvv, raw_response, timet, profile):
    """Format the AutoStripe API response for display"""
    fullcc = f"{cc}|{mes}|{ano}|{cvv}"

    # Extract user_id from profile link
    try:
        user_id = profile.split("id=")[-1].split("'")[0]
    except Exception:
        user_id = None

    # Load gateway from DATA/sites.json
    try:
        with open(SITES_PATH, "r") as f:
            sites = json.load(f)
        site_info = sites.get(user_id, {})
        gateway = site_info.get("gate", "AutoStripe")
        site = site_info.get("site", "Unknown")
    except Exception:
        gateway = "AutoStripe"
        site = "Unknown"

    # Clean response
    raw_response = str(raw_response) if raw_response else "-"
    response_upper = raw_response.upper()

    # Determine status
    if any(x in response_upper for x in ["CHARGED", "SUCCESS", "ORDER_PLACED", "THANK YOU"]):
        status_flag = "Charged [+]"
    elif any(x in response_upper for x in [
        "CCN", "CVV", "CVC", "3DS", "3D_SECURE", "INSUFFICIENT", 
        "INCORRECT_ZIP", "AVS", "MISMATCHED", "AUTHENTICATION",
        "INVALID_CVC", "INCORRECT_CVC", "3DS_REQUIRED"
    ]):
        status_flag = "Approved (CCN) [~]"
    elif any(x in response_upper for x in [
        "DECLINED", "CARD_DECLINED", "DO_NOT_HONOR", "INVALID_CARD",
        "EXPIRED", "LOST", "STOLEN", "FRAUDULENT"
    ]):
        status_flag = "Declined [-]"
    elif "RATE" in response_upper:
        status_flag = "Rate Limited [!]"
    elif "SITE" in response_upper or "ERROR" in response_upper:
        status_flag = "Site Error [!]"
    else:
        status_flag = "Unknown Response [?]"

    # BIN lookup
    bin_data = get_bin_details(cc[:6]) or {}
    bin_info = {
        "bin": bin_data.get("bin", cc[:6]),
        "country": bin_data.get("country", "Unknown"),
        "flag": bin_data.get("flag", ""),
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
        badge = user_data.get("plan", {}).get("badge", "")
    except Exception:
        plan = "Unknown"
        badge = ""

    # Final formatted message
    result = f"""
<b>[#AutoStripe] | Sync</b>
-------------------
<b>[>] Card</b>- <code>{fullcc}</code>
<b>[>] Site</b> - <code>{site}</code>
<b>[>] Gateway</b> - <b>{gateway}</b>
<b>[>] Status</b>- <code>{status_flag}</code>
<b>[>] Response</b>- <code>{raw_response}</code>
-------------------
<b>[+] Bin</b>: <code>{bin_info['bin']}</code>  
<b>[+] Info</b>: <code>{bin_info['vendor']} - {bin_info['type']} - {bin_info['level']}</code> 
<b>[+] Bank</b>: <code>{bin_info['bank']}</code>
<b>[+] Country</b>: <code>{bin_info['country']} - [{bin_info['flag']}]</code>
-------------------
<b>[>] Checked By</b>: {profile} [<code>{plan} {badge}</code>]
<b>[>] Dev</b> -> <a href="https://t.me/syncblast">SyncBlast</a>
-------------------
<b>[>] T/t</b>: <code>[{timet} s]</code> <b>|P/x:</b> [<code>Live</code>]
"""
    return status_flag, result
