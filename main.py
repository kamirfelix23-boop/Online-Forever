import asyncio
import json
import os
import threading
import random
import time
import base64
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import pytz

# ----------------- ANTI-DETECCION CON TLS SPOOFING -----------------
try:
    from curl_cffi import requests as curl_requests
except ImportError:
    os.system("pip install curl_cffi")
    from curl_cffi import requests as curl_requests

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
except ImportError:
    class Fore:
        RED = '\033[91m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        CYAN = '\033[96m'
    Style = None
    def init():
        pass

# ----------------- CONFIGURACION -----------------
TIMEZONE = pytz.timezone('America/Argentina/Buenos_Aires')

def get_local_time():
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")

TOKEN = os.environ.get("DISCORD_TOKEN")
CUSTOM_STATUS_TEXT = os.environ.get("STATUS_TEXT", "Online 24/7")
STATUS = os.environ.get("STATUS_MODE", "online")

if not TOKEN:
    print(f"{Fore.RED}[!] ERROR: DISCORD_TOKEN environment variable not set!")
    sys.exit(1)

# ----------------- FUNCIONES DE ANTI-DETECCION -----------------
def generate_super_properties():
    build_number = random.randint(250000, 310000)
    properties = {
        "os": "Windows",
        "browser": "Chrome",
        "device": "",
        "system_locale": "es-AR",
        "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "browser_version": "120.0.0.0",
        "os_version": "10",
        "referrer": "",
        "referring_domain": "",
        "referrer_current": "",
        "referring_domain_current": "",
        "release_channel": "stable",
        "client_build_number": build_number,
        "client_event_source": None,
        "has_client_mods": False
    }
    return base64.b64encode(json.dumps(properties).encode()).decode()

def build_headers():
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    ]
    return {
        "Authorization": TOKEN,
        "Content-Type": "application/json",
        "User-Agent": random.choice(user_agents),
        "X-Super-Properties": generate_super_properties(),
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

# ----------------- SERVIDOR WEB PARA RENDER -----------------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        status_msg = f"Discord Self-Bot Running\nStatus: {STATUS}\nCustom Status: {CUSTOM_STATUS_TEXT}\nTime: {get_local_time()}"
        self.wfile.write(status_msg.encode())
    
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
    
    def log_message(self, format, *args):
        return

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

threading.Thread(target=run_http_server, daemon=True).start()

# ----------------- VERIFICACION DE TOKEN -----------------
def verify_token():
    try:
        response = curl_requests.get(
            "https://discord.com/api/v9/users/@me",
            headers=build_headers(),
            timeout=15,
            impersonate="chrome120"
        )
        if response.status_code == 200:
            user = response.json()
            print(f"{Fore.GREEN}[+] Logged in as {user['username']} ({user['id']})!")
            return True
        else:
            print(f"{Fore.RED}[-] Invalid token! Status: {response.status_code}")
            return False
    except Exception as e:
        print(f"{Fore.RED}[-] Token verification error: {e}")
        return False

# ----------------- GATEWAY WEBSOCKET (BASADO EN EL CODIGO DE GEMINI) -----------------
async def discord_gateway():
    """Conecta al gateway usando WebSocket (mismo método que funcionaba)"""
    
    import websockets
    
    uri = "wss://gateway.discord.gg/?v=10&encoding=json"
    
    try:
        async with websockets.connect(uri) as ws:
            # Recibir hello
            hello = json.loads(await ws.recv())
            heartbeat_interval = hello["d"]["heartbeat_interval"] / 1000
            print(f"{Fore.CYAN}[*] Heartbeat interval: {heartbeat_interval}s")

            # Tarea de heartbeat CON JITTER (para anti-detección)
            async def heartbeat_task():
                while True:
                    jitter = random.uniform(-0.3, 0.3)
                    await asyncio.sleep(heartbeat_interval + jitter)
                    await ws.send(json.dumps({"op": 1, "d": None}))
                    local_time = get_local_time()
                    print(f"{Fore.GREEN}[{local_time}] Heartbeat sent")

            asyncio.create_task(heartbeat_task())

            # --- IDENTIFY (IGUAL QUE EL CODIGO DE GEMINI QUE FUNCIONABA) ---
            # Esta es la estructura que funcionaba para establecer presencia online
            activity = {
                "name": "Custom Status",
                "type": 4,  # 4 = Custom Status
                "state": CUSTOM_STATUS_TEXT,
                "id": "custom"
            }
            
            identify = {
                "op": 2,
                "d": {
                    "token": TOKEN,
                    "properties": {
                        "$os": "windows",
                        "$browser": "chrome",
                        "$device": "pc"
                    },
                    "presence": {
                        "status": STATUS,      # online, idle, dnd
                        "afk": False,
                        "activities": [activity]
                    },
                    "compress": False,
                    "large_threshold": 250
                }
            }
            
            await ws.send(json.dumps(identify))
            print(f"{Fore.GREEN}[+] Identified with Discord!")
            print(f"{Fore.CYAN}[*] Status: {STATUS}")
            print(f"{Fore.CYAN}[*] Custom Status: {CUSTOM_STATUS_TEXT}")

            # Esperar el evento READY
            ready_event = await ws.recv()
            ready_data = json.loads(ready_event)
            if ready_data.get("t") == "READY":
                print(f"{Fore.GREEN}[+] ✅ READY! Session ID: {ready_data['d']['session_id']}")
                print(f"{Fore.GREEN}[+] 🟢 You are NOW ONLINE with presence active!")
                print(f"{Fore.GREEN}[+] ✅ Your status is visible to others!")

            # Bucle principal
            while True:
                try:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    op_code = data.get("op")
                    
                    if op_code == 11:  # Heartbeat ACK
                        pass
                    elif op_code == 7:  # Reconnect
                        print(f"{Fore.YELLOW}[!] Reconnect requested")
                        break
                    elif op_code == 9:  # Invalid session
                        print(f"{Fore.RED}[-] Invalid session")
                        break
                        
                except websockets.exceptions.ConnectionClosed:
                    print(f"{Fore.YELLOW}[!] Connection closed")
                    break
                except Exception as e:
                    print(f"{Fore.RED}[-] Error in gateway: {e}")
                    break

    except Exception as e:
        print(f"{Fore.RED}[-] Failed to connect to gateway: {e}")
        await asyncio.sleep(5)

# ----------------- RECONEXION AUTOMATICA -----------------
async def main():
    print(f"{Fore.YELLOW}[*] ═══════════════════════════════════")
    print(f"{Fore.YELLOW}[*] Starting Discord Self-Bot (Fixed)")
    print(f"{Fore.YELLOW}[*] ═══════════════════════════════════")
    print(f"{Fore.CYAN}[*] Token: {TOKEN[:10]}...{TOKEN[-10:]}")
    print(f"{Fore.CYAN}[*] Status Text: {CUSTOM_STATUS_TEXT}")
    print(f"{Fore.CYAN}[*] Status Mode: {STATUS}")
    print(f"{Fore.CYAN}[*] Local time: {get_local_time()}")
    
    if not verify_token():
        print(f"{Fore.RED}[!] Token verification failed. Retrying in 30s...")
        await asyncio.sleep(30)
    
    retry_count = 0
    while True:
        try:
            await discord_gateway()
            retry_count = 0
        except Exception as e:
            print(f"{Fore.RED}[-] Gateway error: {e}")
            retry_count += 1
        
        wait_time = min(5 + (retry_count * 2), 30)
        print(f"{Fore.YELLOW}[!] Reconnecting in {wait_time} seconds...")
        await asyncio.sleep(wait_time)

# ----------------- EJECUTAR -----------------
if __name__ == "__main__":
    try:
        import websockets
    except ImportError:
        os.system("pip install websockets")
        import websockets
    
    asyncio.run(main())
