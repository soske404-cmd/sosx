import httpx

def get_bin_details(bin_number: str) -> dict:
    """
    Get BIN details from lookup API
    """
    try:
        bin_number = str(bin_number)[:6]
        url = f"https://bins.antipublic.cc/bins/{bin_number}"
        
        response = httpx.get(url, timeout=10.0)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "bin": bin_number,
                "country": data.get("country", "Unknown"),
                "flag": data.get("country_flag", data.get("flag", "")),
                "vendor": data.get("brand", data.get("vendor", "Unknown")),
                "type": data.get("type", "Unknown"),
                "level": data.get("level", "Unknown"),
                "bank": data.get("bank", "Unknown")
            }
    except Exception as e:
        print(f"BIN lookup error: {e}")
    
    # Return default if lookup fails
    return {
        "bin": bin_number,
        "country": "Unknown",
        "flag": "",
        "vendor": "Unknown",
        "type": "Unknown",
        "level": "Unknown",
        "bank": "Unknown"
    }
