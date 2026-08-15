import json
import base64
import random
import time
import os
import sys

try:
    import tls_client
except ImportError:
    print("ERROR: tls-client not installed. Please add 'tls-client' to requirements.txt")
    sys.exit(1)

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

def set_status(session, headers):
    """Sets the user's status and custom activity using a TLS-spoofed session."""
    status_payload = {
        "status": STATUS,
        "custom_status": {
            "text": CUSTOM_STATUS_TEXT
        }
    }

    try:
        response = session.patch(
            "https://discord.com/api/v9/users/@me/settings",
            headers=headers,
            json=status_payload,
            timeout=15
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

    # Initialize a TLS session that mimics Chrome
    try:
        session = tls_client.Session(
            client_identifier="chrome_126",
            random_tls_extension_order=True
        )
    except Exception as e:
        print(f"{Fore.RED}[-] Failed to initialize TLS session: {e}")
        print(f"{Fore.YELLOW}[!] Trying fallback with chrome_124...")
        try:
            session = tls_client.Session(
                client_identifier="chrome_124",
                random_tls_extension_order=True
            )
        except Exception as e2:
            print(f"{Fore.RED}[-] All TLS attempts failed: {e2}")
            sys.exit(1)

    headers = build_headers()

    # Initial status set
    if set_status(session, headers):
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

            # Slight header rotation to appear more human
            headers = build_headers()

            # Perform a benign, undetectable action: fetch user's own settings
            try:
                response = session.get("https://discord.com/api/v9/users/@me", headers=headers, timeout=10)

                if response.status_code == 200:
                    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                    print(f"{Fore.GREEN}[{current_time}] Heartbeat successful.")
                    retry_count = 0
                else:
                    print(f"{Fore.RED}[-] Heartbeat failed. Status Code: {response.status_code}")
                    retry_count += 1
                    
                    # If we get 401, token is invalid
                    if response.status_code == 401:
                        print(f"{Fore.RED}[!] Token is invalid or expired. Please check DISCORD_TOKEN")
                        time.sleep(60)
                        continue
                    
                    # Rebuild headers on repeated failures
                    if retry_count > 3:
                        print(f"{Fore.YELLOW}[!] Multiple failures, rebuilding headers...")
                        headers = build_headers()
                        retry_count = 0

            except Exception as e:
                print(f"{Fore.RED}[-] Heartbeat error: {e}")
                retry_count += 1
                if retry_count > 3:
                    print(f"{Fore.YELLOW}[!] Multiple errors, reinitializing session...")
                    try:
                        session = tls_client.Session(
                            client_identifier="chrome_126",
                            random_tls_extension_order=True
                        )
                    except:
                        pass
                    retry_count = 0

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[!] Bot stopped by user.")
    except Exception as e:
        print(f"{Fore.RED}[-] Fatal error: {e}")

if __name__ == "__main__":
    main()
