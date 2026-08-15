import asyncio
import json
import os
import threading
import random
import time
import base64
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import pytz

# Intentar importar curl_cffi para TLS spoofing
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
STATUS = os.environ.get("STATUS_MODE", "online")  # online, idle, dnd

if not TOKEN:
    print(f"{Fore.RED}[!] ERROR: DISCORD_TOKEN environment variable not set!")
    exit(1)

# ----------------- SERVIDOR WEB PARA RENDER -----------------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(f"Discord Self-Bot Running\nStatus: {STATUS}\nCustom Status: {CUSTOM_STATUS_TEXT}\nTime: {get_local_time()}".encode())
    
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

# ----------------- FUNCIONES DE ANTI-DETECCION -----------------
def generate_super_properties():
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

# ----------------- GATEWAY WEBSOCKET CON ANTI-DETECCION -----------------
async def discord_gateway():
    """Conecta al gateway de Discord usando WebSocket con anti-detección"""
    
    # Verificar token primero
    try:
        r = curl_requests.get(
            "https://discord.com/api/v9/users/@me",
            headers=build_headers(),
            timeout=10,
            impersonate="chrome120"
        )
        if r.status_code != 200:
            print(f"{Fore.RED}[-] Invalid token! Status: {r.status_code}")
            return
        user = r.json()
        print(f"{Fore.GREEN}[+] Logged in as {user['username']} ({user['id']})!")
    except Exception as e:
        print(f"{Fore.RED}[-] Failed to verify token: {e}")
        return

    # Conectar al gateway
    uri = "wss://gateway.discord.gg/?v=9&encoding=json"
    
    try:
        # Usar websockets con headers personalizados
        import websockets
        extra_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        
        async with websockets.connect(uri, extra_headers=extra_headers) as ws:
            # Recibir hello
            hello = json.loads(await ws.recv())
            heartbeat_interval = hello["d"]["heartbeat_interval"] / 1000
            print(f"{Fore.CYAN}[*] Heartbeat interval: {heartbeat_interval}s")

            # Tarea de heartbeat
            async def heartbeat_task():
                while True:
                    await asyncio.sleep(heartbeat_interval)
                    await ws.send(json.dumps({"op": 1, "d": None}))
                    local_time = get_local_time()
                    print(f"{Fore.GREEN}[{local_time}] Heartbeat sent")

            asyncio.create_task(heartbeat_task())

            # Identificar con presencia
            identify = {
                "op": 2,
                "d": {
                    "token": TOKEN,
                    "properties": {
                        "$os": "Windows",
                        "$browser": "Chrome",
                        "$device": "pc",
                        "$referrer": "",
                        "$referring_domain": ""
                    },
                    "presence": {
                        "status": STATUS,
                        "afk": False,
                        "activities": [
                            {
                                "name": "Custom Status",
                                "type": 4,  # Custom status
                                "state": CUSTOM_STATUS_TEXT,
                                "id": "custom"
                            }
                        ]
                    },
                    "compress": False,
                    "large_threshold": 250,
                    "client_state": {
                        "guild_versions": {},
                        "highest_last_message_id": "0",
                        "read_state_version": 0,
                        "user_guild_settings_version": -1,
                        "user_settings_version": -1
                    }
                }
            }
            
            await ws.send(json.dumps(identify))
            print(f"{Fore.GREEN}[+] Identified with Discord!")
            print(f"{Fore.CYAN}[*] Status: {STATUS}")
            print(f"{Fore.CYAN}[*] Custom Status: {CUSTOM_STATUS_TEXT}")

            # Bucle principal
            while True:
                try:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    
                    op_code = data.get("op")
                    
                    # Heartbeat ACK
                    if op_code == 11:
                        pass
                    
                    # Ready event
                    elif op_code == 0 and data.get("t") == "READY":
                        print(f"{Fore.GREEN}[+] Ready! Session ID: {data['d']['session_id']}")
                    
                    # Reconnect
                    elif op_code == 7:
                        print(f"{Fore.YELLOW}[!] Reconnect requested, reconnecting...")
                        break
                    
                    # Invalid session
                    elif op_code == 9:
                        print(f"{Fore.RED}[-] Invalid session! Reconnecting...")
                        break
                    
                except websockets.exceptions.ConnectionClosed:
                    print(f"{Fore.YELLOW}[!] Connection closed, reconnecting...")
                    break
                except Exception as e:
                    print(f"{Fore.RED}[-] Error in gateway: {e}")
                    break

    except Exception as e:
        print(f"{Fore.RED}[-] Failed to connect to gateway: {e}")
        await asyncio.sleep(5)

# ----------------- RECONEXION AUTOMATICA -----------------
async def main():
    print(f"{Fore.YELLOW}[*] Starting Discord Self-Bot with Anti-Detection...")
    print(f"{Fore.CYAN}[*] Local time: {get_local_time()}")
    
    while True:
        try:
            await discord_gateway()
        except Exception as e:
            print(f"{Fore.RED}[-] Gateway error: {e}")
        
        print(f"{Fore.YELLOW}[!] Reconnecting in 5 seconds...")
        await asyncio.sleep(5)

# ----------------- EJECUTAR -----------------
if __name__ == "__main__":
    try:
        import websockets
    except ImportError:
        print("Installing websockets...")
        os.system("pip install websockets")
        import websockets
    
    asyncio.run(main())
