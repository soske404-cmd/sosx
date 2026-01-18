"""
Response formatter for Medium Stripe Checker
Provides formatted output for Telegram bot integration
"""


def get_status_info(status):
    """Get status emoji and description"""
    status_map = {
        'LIVE': ('✅', 'Live Card'),
        'CCN': ('⚠️', 'CVV Issue'),
        'DEAD': ('❌', 'Declined'),
        'RETRY': ('🔄', 'Retry'),
        'RATE_LIMITED': ('⏳', 'Rate Limited'),
        'Unknown': ('❓', 'Unknown')
    }
    return status_map.get(status, ('❓', 'Unknown'))


def format_medium_response(cc, mes, ano, cvv, result, time_taken, profile):
    """
    Format the checker response for Telegram bot
    
    Args:
        cc: Card number
        mes: Expiry month
        ano: Expiry year
        cvv: CVV
        result: Result dict from checker
        time_taken: Time taken in seconds
        profile: User profile HTML
        
    Returns:
        tuple: (status_flag, formatted_message)
    """
    fullcc = f"{cc}|{mes}|{ano}|{cvv}"
    status = result.get('status', 'Unknown')
    response = result.get('response', '-')
    
    emoji, status_text = get_status_info(status)
    
    # Card info from result
    brand = result.get('brand', 'Unknown').upper()
    funding = result.get('funding', 'Unknown').upper()
    country = result.get('country', 'Unknown')
    last4 = result.get('last4', cc[-4:] if len(cc) >= 4 else '****')
    
    # Status flag for categorization
    if status == 'LIVE':
        status_flag = "Approved ✅"
    elif status == 'CCN':
        status_flag = "CCN ⚠️"
    elif status == 'DEAD':
        status_flag = "Declined ❌"
    else:
        status_flag = f"{status} {emoji}"
    
    # Formatted message
    message = f"""
<b>[#Medium] | Stripe Checker</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{fullcc}</code>
<b>[•] Gateway</b> - <b>Medium Stripe 💳</b>
<b>[•] Status</b>- <code>{status_flag}</code>
<b>[•] Response</b>- <code>{response}</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Brand</b>: <code>{brand}</code>
<b>[+] Funding</b>: <code>{funding}</code>
<b>[+] Last4</b>: <code>{last4}</code>
<b>[+] Country</b>: <code>{country}</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[ﾒ] Checked By</b>: {profile}
<b>[ϟ] Gateway</b> ➺ <b>Medium.com</b>
━━━━━━━━━━━━━━━
<b>[ﾒ] T/t</b>: <code>[{time_taken} 𝐬]</code>
"""
    return status_flag, message.strip()


def format_simple(result):
    """
    Simple format for console/Pydroid3 output
    
    Args:
        result: Result dict from checker
        
    Returns:
        str: Formatted string
    """
    card = result.get('card', 'Unknown')
    status = result.get('status', 'Unknown')
    response = result.get('response', '-')
    emoji, _ = get_status_info(status)
    
    return f"{emoji} {card} | {status} | {response}"


def format_bulk_results(results):
    """
    Format bulk check results
    
    Args:
        results: Dict with categorized results
        
    Returns:
        str: Formatted summary
    """
    live_count = len(results.get('live', []))
    ccn_count = len(results.get('ccn', []))
    dead_count = len(results.get('dead', []))
    retry_count = len(results.get('retry', []))
    unknown_count = len(results.get('unknown', []))
    
    total = live_count + ccn_count + dead_count + retry_count + unknown_count
    
    output = f"""
╔══════════════════════════════════╗
║       BULK CHECK SUMMARY         ║
╠══════════════════════════════════╣
║ ✅ Live:    {live_count:>5}
║ ⚠️ CCN:     {ccn_count:>5}
║ ❌ Dead:    {dead_count:>5}
║ 🔄 Retry:   {retry_count:>5}
║ ❓ Unknown: {unknown_count:>5}
╠══════════════════════════════════╣
║ 📊 Total:   {total:>5}
╚══════════════════════════════════╝
"""
    
    # Add live cards if any
    if live_count > 0:
        output += "\n✅ LIVE CARDS:\n"
        for r in results['live']:
            output += f"  • {r['card']} | {r['response']}\n"
    
    # Add CCN cards if any
    if ccn_count > 0:
        output += "\n⚠️ CCN CARDS:\n"
        for r in results['ccn']:
            output += f"  • {r['card']} | {r['response']}\n"
    
    return output


def format_for_file(results, category='live'):
    """
    Format results for file saving
    
    Args:
        results: Dict with categorized results
        category: Which category to format
        
    Returns:
        str: Newline-separated cards
    """
    cards = results.get(category, [])
    return '\n'.join([r['card'] for r in cards])
