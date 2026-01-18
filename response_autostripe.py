import json
from TOOLS.getbin import get_bin_details
from start import load_users

def format_autostripe_response(cc, mes, ano, cvv, raw_response, timet, profile):
    """
    Format the autostripe response for Telegram message
    """
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
        site_info = sites.get(user_id, {})
        gateway = site_info.get("gate", "Autostripe")
        site = site_info.get("site", "Unknown")
    except Exception:
        gateway = "Autostripe"
        site = "Unknown"

    # Clean response
    raw_response = str(raw_response) if raw_response else "-"

    # Determine status based on response
    response_upper = raw_response.upper()
    
    if any(success in response_upper for success in ["CHARGED", "ORDER_PLACED", "THANK YOU", "SUCCESS"]):
        status_flag = "Charged"
    elif "CCN" in response_upper or any(cvv_err in response_upper for cvv_err in ["INVALID_CVC", "INCORRECT_CVC"]):
        status_flag = "CCN"
    elif any(approved in response_upper for approved in [
        "3DS_REQUIRED", "3D_SECURE", "INSUFFICIENT_FUNDS", 
        "MISMATCHED_BILLING", "MISMATCHED_PIN", "MISMATCHED_ZIP",
        "INCORRECT_ZIP", "INCORRECT_ADDRESS", "3D_AUTHENTICATION"
    ]):
        status_flag = "Approved"
    else:
        status_flag = "Declined"

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
<b>[#Autostripe] | Sync</b>
━━━━━━━━━━━━━━━
<b>[*] Card</b>- <code>{fullcc}</code>
<b>[*] Gateway</b> - <b>{gateway}</b>
<b>[*] Status</b>- <code>{status_flag}</code>
<b>[*] Response</b>- <code>{raw_response}</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Bin</b>: <code>{bin_info['bin']}</code>  
<b>[+] Info</b>: <code>{bin_info['vendor']} - {bin_info['type']} - {bin_info['level']}</code> 
<b>[+] Bank</b>: <code>{bin_info['bank']}</code>
<b>[+] Country</b>: <code>{bin_info['country']} {bin_info['flag']}</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[~] Checked By</b>: {profile} [<code>{plan} {badge}</code>]
<b>[~] Dev</b> -> <a href="https://t.me/syncblast">SyncBlast</a>
━━━━━━━━━━━━━━━
<b>[~] T/t</b>: <code>[{timet} s]</code>
"""
    return status_flag, result


def get_status_flag_autostripe(raw_response):
    """
    Get status flag from raw response for mass checking
    """
    response_upper = str(raw_response).upper()
    
    if any(success in response_upper for success in ["CHARGED", "ORDER_PLACED", "THANK YOU", "SUCCESS"]):
        return "Charged"
    elif "CCN" in response_upper or any(cvv_err in response_upper for cvv_err in ["INVALID_CVC", "INCORRECT_CVC"]):
        return "CCN"
    elif any(approved in response_upper for approved in [
        "3DS_REQUIRED", "3D_SECURE", "INSUFFICIENT_FUNDS", 
        "MISMATCHED_BILLING", "MISMATCHED_PIN", "MISMATCHED_ZIP",
        "INCORRECT_ZIP", "INCORRECT_ADDRESS", "3D_AUTHENTICATION"
    ]):
        return "Approved"
    else:
        return "Declined"
