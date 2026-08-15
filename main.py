import json
import base64
import random
import time
import os
import sys
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import pytz  # Necesario para zonas horarias

# Try to import curl_cffi, install if missing
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

# ----------------- CONFIGURACION DE ZONA HORARIA -----------------
# Argentina: UTC-3
TIMEZONE = pytz.timezone('America/Argentina/Buenos_Aires')

def get_local_time():
    """Retorna la hora actual en la zona horaria de Argentina"""
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")

def get_local_time_http():
    """Retorna la hora actual en la zona horaria de Argentina para el servidor web"""
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")

# ----------------- CONFIGURATION -----------------
TOKEN = os.environ.get("DISCORD_TOKEN")
CUSTOM_STATUS_TEXT = os.environ.get("STATUS_TEXT", "Online 24/7")
STATUS = "online"  # online, idle, dnd, invisible
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
        "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "browser_version": "120.0.0.0",
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
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0"
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
    """Sets the user's online status AND custom status."""
    
    # 1. Primero, establecer la presencia online (verde/amarillo/rojo)
    presence_payload = {
        "status": STATUS  # online, idle, dnd
    }
    
    # 2. Luego, establecer el custom status (texto debajo del nombre)
    custom_payload = {
        "custom_status": {
            "text": CUSTOM_STATUS_TEXT
        }
    }
    
    try:
        # Actualizar presencia online
        presence_response = curl_requests.patch(
            "https://discord.com/api/v9/users/@me/settings",
            json=presence_payload,
            headers=build_headers(),
            timeout=15,
            impersonate="chrome120"
        )
        
        if presence_response.status_code != 200:
            print(f"{Fore.RED}[-] Failed to update online presence. Status Code: {presence_response.status_code}")
            return False
        
        print(f"{Fore.GREEN}[+] Online presence set to: {STATUS}")
        
        # Actualizar custom status (texto)
        custom_response = curl_requests.patch(
            "https://discord.com/api/v9/users/@me/settings",
            json=custom_payload,
            headers=build_headers(),
            timeout=15,
            impersonate="chrome120"
        )
        
        if custom_response.status_code == 200:
            print(f"{Fore.GREEN}[+] Custom status updated successfully!")
            print(f"{Fore.CYAN}[+] Status: {STATUS}")
            print(f"{Fore.CYAN}[+] Custom Status Text: {CUSTOM_STATUS_TEXT}")
            return True
        else:
            print(f"{Fore.RED}[-] Failed to update custom status. Status Code: {custom_response.status_code}")
            try:
                print(f"{Fore.YELLOW}[!] Response: {custom_response.text}")
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
            impersonate="chrome120"
        )

        if response.status_code == 200:
            local_time = get_local_time()
            print(f"{Fore.GREEN}[{local_time}] Heartbeat successful.")
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

# ----------------- WEB SERVER FOR RENDER (REQUIRED) -----------------
class HealthHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler that responds to health checks"""
    
    def do_GET(self):
        """Handle GET requests - respond with status"""
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        
        # Usar hora local de Argentina
        local_time = get_local_time_http()
        status_msg = f"Discord Self-Bot Running\nStatus: {STATUS}\nCustom Status: {CUSTOM_STATUS_TEXT}\nLocal Time (Argentina): {local_time}\nServer Time (UTC): {time.strftime('%Y-%m-%d %H:%M:%S')}"
        self.wfile.write(status_msg.encode())
    
    def do_HEAD(self):
        """Handle HEAD requests - just respond with 200"""
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress web server logs to keep console clean"""
        pass

def run_web_server():
    """Runs a web server on the port Render expects"""
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    local_time = get_local_time()
    print(f"{Fore.CYAN}[*] Web server running on port {port}")
    print(f"{Fore.CYAN}[*] Health check available at: http://0.0.0.0:{port}/")
    print(f"{Fore.CYAN}[*] Local time (Argentina): {local_time}")
    server.serve_forever()

# ----------------- MAIN BOT FUNCTION -----------------
def run_bot():
    """Main bot loop"""
    print(f"{Fore.YELLOW}[*] Initializing Anti-Detection Self-Bot...")
    
    local_time = get_local_time()
    print(f"{Fore.CYAN}[*] Local time (Argentina): {local_time}")
    
    if TOKEN:
        masked_token = TOKEN[:10] + "..." + TOKEN[-10:] if len(TOKEN) > 20 else "***"
        print(f"{Fore.CYAN}[*] Token: {masked_token}")
    print(f"{Fore.CYAN}[*] Status Text: {CUSTOM_STATUS_TEXT}")
    print(f"{Fore.CYAN}[*] Status Mode: {STATUS}")
    print(f"{Fore.CYAN}[*] Python Version: {sys.version}")

    print(f"{Fore.YELLOW}[*] Testing connection to Discord...")
    try:
        test_response = curl_requests.get(
            "https://discord.com/api/v9/users/@me",
            headers=build_headers(),
            timeout=10,
            impersonate="chrome120"
        )
        if test_response.status_code == 200:
            print(f"{Fore.GREEN}[+] Connection successful!")
        else:
            print(f"{Fore.RED}[-] Connection test failed. Status: {test_response.status_code}")
    except Exception as e:
        print(f"{Fore.RED}[-] Connection test error: {e}")

    if set_status():
        print(f"{Fore.GREEN}[+] Bot is now operational. Staying online...")
    else:
        print(f"{Fore.RED}[-] Failed to start. Check your token and network.")
        print(f"{Fore.YELLOW}[!] Will retry in 30 seconds...")
        time.sleep(30)

    print(f"{Fore.YELLOW}[!] Press CTRL+C to stop the bot.")

    retry_count = 0
    try:
        while True:
            human_like_delay()

            if heartbeat():
                retry_count = 0
            else:
                retry_count += 1
                if retry_count > 3:
                    print(f"{Fore.YELLOW}[!] Multiple failures, refreshing state...")
                    set_status()
                    retry_count = 0

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[!] Bot stopped by user.")
    except Exception as e:
        print(f"{Fore.RED}[-] Fatal error: {e}")

# ----------------- STARTUP -----------------
if __name__ == "__main__":
    # Start web server in background thread
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print(f"{Fore.CYAN}[*] Web server thread started")
    
    # Run the bot in the main thread
    run_bot()
