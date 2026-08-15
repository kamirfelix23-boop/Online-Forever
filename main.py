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
    print("[✓] curl_cffi loaded successfully")
except ImportError:
    print("[!] Installing curl_cffi...")
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
    """Genera X-Super-Properties dinámico (camuflaje)"""
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
    """Headers con User-Agent aleatorio y X-Super-Properties dinámico"""
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
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

def get_websocket_headers():
    """Headers para la conexión WebSocket (sin X-Super-Properties, solo User-Agent)"""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    ]
    return {
        "User-Agent": random.choice(user_agents),
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "Upgrade",
        "Upgrade": "websocket",
    }

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

# ----------------- VERIFICACION DE TOKEN CON TLS SPOOFING -----------------
def verify_token():
    """Verifica el token usando curl_cffi con impersonate (anti-detección)"""
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

# ----------------- GATEWAY WEBSOCKET CON HEADERS DINAMICOS -----------------
async def discord_gateway():
    """Conecta al gateway usando WebSocket con headers dinámicos"""
    
    import websockets
    
    uri = "wss://gateway.discord.gg/?v=10&encoding=json"
    ws_headers = get_websocket_headers()
    
    try:
        print(f"{Fore.CYAN}[*] Connecting to Discord gateway...")
        print(f"{Fore.CYAN}[*] Using User-Agent: {ws_headers['User-Agent']}")
        
        async with websockets.connect(uri, extra_headers=ws_headers) as ws:
            # Recibir hello
            hello = json.loads(await ws.recv())
            heartbeat_interval = hello["d"]["heartbeat_interval"] / 1000
            print(f"{Fore.CYAN}[*] Heartbeat interval: {heartbeat_interval}s")

            # Tarea de heartbeat con jitter (pequeña variación)
            async def heartbeat_task():
                while True:
                    # Jitter: variación aleatoria de ±0.5s para parecer humano
                    jitter = random.uniform(-0.5, 0.5)
                    await asyncio.sleep(heartbeat_interval + jitter)
                    await ws.send(json.dumps({"op": 1, "d": None}))
                    local_time = get_local_time()
                    print(f"{Fore.GREEN}[{local_time}] Heartbeat sent")

            asyncio.create_task(heartbeat_task())

            # Construir presence con custom status
            activity = {
                "name": "Custom Status",
                "type": 4,
                "state": CUSTOM_STATUS_TEXT,
                "id": "custom"
            }
            
            # Identify con propiedades detalladas (camuflaje)
            identify = {
                "op": 2,
                "d": {
                    "token": TOKEN,
                    "properties": {
                        "$os": "Windows",
                        "$browser": "Chrome",
                        "$device": "pc",
                        "$browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "$browser_version": "120.0.0.0",
                        "$os_version": "10",
                        "$referrer": "",
                        "$referring_domain": "",
                        "$referrer_current": "",
                        "$referring_domain_current": "",
                        "$release_channel": "stable",
                        "$client_build_number": random.randint(250000, 310000),
                        "$client_event_source": None
                    },
                    "presence": {
                        "status": STATUS,
                        "afk": False,
                        "activities": [activity]
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

            # Esperar el evento READY
            ready_event = await ws.recv()
            ready_data = json.loads(ready_event)
            if ready_data.get("t") == "READY":
                print(f"{Fore.GREEN}[+] Ready! Session ID: {ready_data['d']['session_id']}")
                print(f"{Fore.GREEN}[+] 🟢 Bot is ONLINE with presence active!")

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
                    elif op_code == 10:  # Hello (reconexión)
                        print(f"{Fore.CYAN}[*] Received new hello")
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
    print(f"{Fore.YELLOW}[*] Starting Discord Self-Bot (Hybrid)")
    print(f"{Fore.YELLOW}[*] ═══════════════════════════════════")
    print(f"{Fore.CYAN}[*] Token: {TOKEN[:10]}...{TOKEN[-10:]}")
    print(f"{Fore.CYAN}[*] Status Text: {CUSTOM_STATUS_TEXT}")
    print(f"{Fore.CYAN}[*] Status Mode: {STATUS}")
    print(f"{Fore.CYAN}[*] Local time: {get_local_time()}")
    
    # Verificar token con anti-detección
    if not verify_token():
        print(f"{Fore.RED}[!] Token verification failed. Retrying in 30s...")
        await asyncio.sleep(30)
    
    # Bucle principal con reconexión
    retry_count = 0
    while True:
        try:
            await discord_gateway()
            retry_count = 0
        except Exception as e:
            print(f"{Fore.RED}[-] Gateway error: {e}")
            retry_count += 1
        
        # Backoff exponencial: espera más si hay muchos fallos
        wait_time = min(5 + (retry_count * 2), 30)
        print(f"{Fore.YELLOW}[!] Reconnecting in {wait_time} seconds...")
        await asyncio.sleep(wait_time)

# ----------------- EJECUTAR -----------------
if __name__ == "__main__":
    try:
        import websockets
    except ImportError:
        print("Installing websockets...")
        os.system("pip install websockets")
        import websockets
    
    asyncio.run(main())
