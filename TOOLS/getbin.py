# BIN Lookup Tool
import httpx

def get_bin_details(bin_number: str) -> dict:
    """
    Get BIN (Bank Identification Number) details
    
    Args:
        bin_number: First 6-8 digits of a card
    
    Returns:
        dict with BIN information
    """
    try:
        # Try to get BIN info from lookup API
        response = httpx.get(f"https://lookup.binlist.net/{bin_number[:6]}", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            country_data = data.get("country", {})
            bank_data = data.get("bank", {})
            
            return {
                "bin": bin_number[:6],
                "country": country_data.get("name", "Unknown"),
                "flag": country_data.get("emoji", "🏳️"),
                "vendor": data.get("scheme", "Unknown").upper() if data.get("scheme") else "Unknown",
                "type": data.get("type", "Unknown").upper() if data.get("type") else "Unknown",
                "level": data.get("brand", "Unknown").upper() if data.get("brand") else "Unknown",
                "bank": bank_data.get("name", "Unknown")
            }
    except Exception as e:
        print(f"BIN lookup error: {e}")
    
    # Return default values if lookup fails
    return {
        "bin": bin_number[:6] if len(bin_number) >= 6 else bin_number,
        "country": "Unknown",
        "flag": "🏳️",
        "vendor": "Unknown",
        "type": "Unknown",
        "level": "Unknown",
        "bank": "Unknown"
    }
