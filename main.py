import json
import base64
import random
import time
import os
import sys

try:
    from curl_cffi import requests as curl_requests
except ImportError:
    print("Installing curl_cffi...")
    os.system("pip install curl_cffi")
    from curl_cffi import requests as curl_requests

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
except ImportError:
    # Fallback if colorama is not installed
    class Fore:
        RED = '\033[91m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        CYAN = '\033[96m'
    Style = None
    def init():
        pass

# ----------------- CONFIGURATION -----------------
TOKEN = os.environ.get("DISCORD_TOKEN")
CUSTOM_STATUS_TEXT = os.environ.get("STATUS_TEXT", "Online 24/7")
STATUS = "online"  # online, idle, dnd
# -------------------------------------------------

if not TOKEN:
    print(f"{Fore.RED}[!] ERROR: DISCORD_TOKEN environment variable not set!")
    print(f"{Fore.YELLOW}[!] Please set DISCORD_TOKEN in Render environment variables")
    sys.exit(1)

def generate_super_properties():
    """Generates a dynamic X-Super-Properties header to mimic a real browser client."""
    properties = {
        "os": "Windows",
        "browser": "Chrome",
        "device": "",
        "system_locale": "en-US",
        "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "browser_version": "126.0.0.0",
        "os_version": "10",
        "referrer": "",
        "referring_domain": "",
        "referrer_current": "",
        "referring_domain_current": "",
        "release_channel": "stable",
        "client_build_number": random.randint(250000, 300000),
        "client_event_source": None,
        "has_client_mods": False
    }
    return base64.b64encode(json.dumps(properties).encode()).decode()

def build_headers():
    """Builds headers with the dynamic X-Super-Properties and randomized User-Agent."""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/126.0"
    ]
    return {
        "Authorization": TOKEN,
        "Content-Type": "application/json",
        "User-Agent": random.choice(user_agents),
        "X-Super-Properties": generate_super_properties(),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

def set_status():
    """Sets the user's status using curl_cffi which mimics browser TLS."""
    status_payload = {
        "status": STATUS,
        "custom_status": {
            "text": CUSTOM_STATUS_TEXT
        }
    }

    try:
        # Use curl_cffi with impersonate to mimic Chrome
        response = curl_requests.patch(
            "https://discord.com/api/v9/users/@me/settings",
            json=status_payload,
            headers=build_headers(),
            timeout=15,
            impersonate="chrome126"
        )

        if response.status_code == 200:
            print(f"{Fore.GREEN}[+] Status updated successfully!")
            print(f"{Fore.CYAN}[+] Status: {STATUS}")
            print(f"{Fore.CYAN}[+] Custom Status Text: {CUSTOM_STATUS_TEXT}")
            return True
        else:
            print(f"{Fore.RED}[-] Failed to update status. Status Code: {response.status_code}")
            try:
                print(f"{Fore.YELLOW}[!] Response: {response.text}")
            except:
                pass
            return False

    except Exception as e:
        print(f"{Fore.RED}[-] An error occurred: {e}")
        return False

def heartbeat():
    """Performs a heartbeat request to keep the account online."""
    try:
        response = curl_requests.get(
            "https://discord.com/api/v9/users/@me",
            headers=build_headers(),
            timeout=10,
            impersonate="chrome126"
        )

        if response.status_code == 200:
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"{Fore.GREEN}[{current_time}] Heartbeat successful.")
            return True
        else:
            print(f"{Fore.RED}[-] Heartbeat failed. Status Code: {response.status_code}")
            if response.status_code == 401:
                print(f"{Fore.RED}[!] Token is invalid or expired. Please check DISCORD_TOKEN")
            return False

    except Exception as e:
        print(f"{Fore.RED}[-] Heartbeat error: {e}")
        return False

def human_like_delay():
    """Adds a random, human-like delay between 1100ms and 3500ms to avoid rate limiting."""
    delay = random.uniform(1.1, 3.5)
    time.sleep(delay)

def main():
    print(f"{Fore.YELLOW}[*] Initializing Anti-Detection Self-Bot...")
    
    # Show current configuration (mask token)
    if TOKEN:
        masked_token = TOKEN[:10] + "..." + TOKEN[-10:] if len(TOKEN) > 20 else "***"
        print(f"{Fore.CYAN}[*] Token: {masked_token}")
    print(f"{Fore.CYAN}[*] Status Text: {CUSTOM_STATUS_TEXT}")
    print(f"{Fore.CYAN}[*] Python Version: {sys.version}")

    # Initial status set
    if set_status():
        print(f"{Fore.GREEN}[+] Bot is now operational. Staying online...")
    else:
        print(f"{Fore.RED}[-] Failed to start. Check your token and network.")
        print(f"{Fore.YELLOW}[!] Will retry in 30 seconds...")
        time.sleep(30)

    print(f"{Fore.YELLOW}[!] Press CTRL+C to stop the bot.")

    # Keep the account online with periodic, randomized activity
    retry_count = 0
    try:
        while True:
            human_like_delay()

            if heartbeat():
                retry_count = 0
            else:
                retry_count += 1
                
                # Rebuild headers on repeated failures
                if retry_count > 3:
                    print(f"{Fore.YELLOW}[!] Multiple failures, refreshing state...")
                    retry_count = 0

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[!] Bot stopped by user.")
    except Exception as e:
        print(f"{Fore.RED}[-] Fatal error: {e}")

if __name__ == "__main__":
    main()
