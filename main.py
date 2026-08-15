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

# ----------------- GATEWAY WEBSOCKET (VERSION SIMPLIFICADA) -----------------
async def discord_gateway():
    """Conecta al gateway de Discord usando WebSocket (basado en el código que funcionaba)"""
    
    import websockets
    
    uri = "wss://gateway.discord.gg/?v=10&encoding=json"
    
    try:
        async with websockets.connect(uri) as ws:
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

            # Identificar con presencia (ESTE ES EL PASO CLAVE)
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
                        "status": STATUS,  # online, idle, dnd
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
            
            # Verificar que la conexión está activa
            ready_event = await ws.recv()
            ready_data = json.loads(ready_event)
            if ready_data.get("t") == "READY":
                print(f"{Fore.GREEN}[+] Ready! Session ID: {ready_data['d']['session_id']}")
                print(f"{Fore.GREEN}[+] Bot is now online with presence active!")

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
                    elif op_code == 0:
                        t = data.get("t")
                        if t == "PRESENCE_UPDATE":
                            pass  # Silenciar actualizaciones de presencia
                        
                except websockets.exceptions.ConnectionClosed:
                    print(f"{Fore.YELLOW}[!] Connection closed")
                    break
                except Exception as e:
                    print(f"{Fore.RED}[-] Error: {e}")
                    break

    except Exception as e:
        print(f"{Fore.RED}[-] Failed to connect: {e}")
        await asyncio.sleep(5)

# ----------------- RECONEXION AUTOMATICA -----------------
async def main():
    print(f"{Fore.YELLOW}[*] Starting Discord Self-Bot...")
    print(f"{Fore.CYAN}[*] Token: {TOKEN[:10]}...{TOKEN[-10:]}")
    print(f"{Fore.CYAN}[*] Status Text: {CUSTOM_STATUS_TEXT}")
    print(f"{Fore.CYAN}[*] Status Mode: {STATUS}")
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
