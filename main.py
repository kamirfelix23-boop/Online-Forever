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

# Variables de control global
bot_running = True
current_status = STATUS
current_custom_text = CUSTOM_STATUS_TEXT

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

# ----------------- SERVIDOR WEB PARA RENDER (EVITA SLEEP) -----------------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        status_msg = f"Discord Self-Bot Running\nStatus: {current_status}\nCustom Status: {current_custom_text}\nTime: {get_local_time()}\nUptime: Active"
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
            return user
        else:
            print(f"{Fore.RED}[-] Invalid token! Status: {response.status_code}")
            return None
    except Exception as e:
        print(f"{Fore.RED}[-] Token verification error: {e}")
        return None

# ----------------- ACTUALIZAR STATUS POR COMANDO -----------------
def update_status(new_status=None, new_text=None):
    """Actualiza las variables globales de estado"""
    global current_status, current_custom_text
    
    if new_status:
        current_status = new_status
    if new_text:
        current_custom_text = new_text
    
    print(f"{Fore.CYAN}[*] Status updated to: {current_status}")
    print(f"{Fore.CYAN}[*] Custom text: {current_custom_text}")

# ----------------- GATEWAY WEBSOCKET CON COMANDOS DM -----------------
async def discord_gateway():
    """Conecta al gateway con soporte para comandos por DM"""
    
    import websockets
    
    uri = "wss://gateway.discord.gg/?v=10&encoding=json"
    
    try:
        async with websockets.connect(uri) as ws:
            # Recibir hello
            hello = json.loads(await ws.recv())
            heartbeat_interval = hello["d"]["heartbeat_interval"] / 1000
            print(f"{Fore.CYAN}[*] Heartbeat interval: {heartbeat_interval}s")

            # Tarea de heartbeat CON JITTER
            async def heartbeat_task():
                while True:
                    jitter = random.uniform(-0.3, 0.3)
                    await asyncio.sleep(heartbeat_interval + jitter)
                    await ws.send(json.dumps({"op": 1, "d": None}))
                    local_time = get_local_time()
                    print(f"{Fore.GREEN}[{local_time}] Heartbeat sent")

            asyncio.create_task(heartbeat_task())

            # IDENTIFY con presencia
            activity = {
                "name": "Custom Status",
                "type": 4,
                "state": current_custom_text,
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
                        "status": current_status,
                        "afk": False,
                        "activities": [activity]
                    },
                    "compress": False,
                    "large_threshold": 250
                }
            }
            
            await ws.send(json.dumps(identify))
            print(f"{Fore.GREEN}[+] Identified with Discord!")
            print(f"{Fore.CYAN}[*] Status: {current_status}")
            print(f"{Fore.CYAN}[*] Custom Status: {current_custom_text}")

            # Esperar READY
            ready_event = await ws.recv()
            ready_data = json.loads(ready_event)
            if ready_data.get("t") == "READY":
                user_id = ready_data['d']['user']['id']
                print(f"{Fore.GREEN}[+] ✅ READY! User ID: {user_id}")
                print(f"{Fore.GREEN}[+] 🟢 You are NOW ONLINE!")
                print(f"{Fore.CYAN}[*] 💬 Send 'rezty on' to set online")
                print(f"{Fore.CYAN}[*] 💬 Send 'rezty idle' to set idle")
                print(f"{Fore.CYAN}[*] 💬 Send 'rezty dnd' to set DND")
                print(f"{Fore.CYAN}[*] 💬 Send 'rezty offline' to set offline")
                print(f"{Fore.CYAN}[*] 💬 Send 'rezty status: texto' to change custom status")

            # Bucle principal - ESCUCHA COMANDOS
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
                    elif op_code == 0:  # Dispatch event
                        event_type = data.get("t")
                        
                        # --- PROCESAR MENSAJES DIRECTOS ---
                        if event_type == "MESSAGE_CREATE":
                            msg_data = data.get("d", {})
                            channel_id = msg_data.get("channel_id")
                            content = msg_data.get("content", "").lower().strip()
                            author_id = msg_data.get("author", {}).get("id")
                            
                            # Verificar si es DM (channel_id == author_id en DMs)
                            if channel_id == author_id:
                                print(f"{Fore.YELLOW}[*] DM from {author_id}: {content}")
                                
                                # Procesar comandos
                                if content.startswith("rezty "):
                                    command = content[6:].strip()
                                    
                                    # Comando: rezty on/offline/idle/dnd
                                    if command == "on":
                                        update_status("online")
                                        await send_presence_update(ws)
                                        await send_dm_response(ws, author_id, "✅ Status set to ONLINE")
                                    
                                    elif command == "idle":
                                        update_status("idle")
                                        await send_presence_update(ws)
                                        await send_dm_response(ws, author_id, "💤 Status set to IDLE")
                                    
                                    elif command == "dnd":
                                        update_status("dnd")
                                        await send_presence_update(ws)
                                        await send_dm_response(ws, author_id, "🚫 Status set to DO NOT DISTURB")
                                    
                                    elif command == "offline":
                                        update_status("invisible")
                                        await send_presence_update(ws)
                                        await send_dm_response(ws, author_id, "🌙 Status set to OFFLINE (invisible)")
                                    
                                    # Comando: rezty status: nuevo texto
                                    elif command.startswith("status:"):
                                        new_text = command[7:].strip()
                                        if new_text:
                                            update_status(None, new_text)
                                            await send_presence_update(ws)
                                            await send_dm_response(ws, author_id, f"📝 Custom status changed to: {new_text}")
                                        else:
                                            await send_dm_response(ws, author_id, "❌ Please provide text: `rezty status: nuevo texto`")
                                    
                                    # Comando: rezty help
                                    elif command == "help":
                                        help_msg = (
                                            "📖 **Comandos disponibles:**\n"
                                            "• `rezty on` - Set online\n"
                                            "• `rezty idle` - Set idle\n"
                                            "• `rezty dnd` - Set Do Not Disturb\n"
                                            "• `rezty offline` - Set offline (invisible)\n"
                                            "• `rezty status: texto` - Change custom status text\n"
                                            "• `rezty help` - Show this message"
                                        )
                                        await send_dm_response(ws, author_id, help_msg)
                                    else:
                                        await send_dm_response(ws, author_id, "❌ Unknown command. Send `rezty help` for available commands.")

                    # Enviar presencia actualizada (reconexión)
                    if op_code == 10:  # Hello
                        print(f"{Fore.CYAN}[*] Reconnecting...")

                except websockets.exceptions.ConnectionClosed:
                    print(f"{Fore.YELLOW}[!] Connection closed")
                    break
                except Exception as e:
                    print(f"{Fore.RED}[-] Error in gateway: {e}")
                    break

    except Exception as e:
        print(f"{Fore.RED}[-] Failed to connect to gateway: {e}")
        await asyncio.sleep(5)

# ----------------- FUNCIONES DE ENVIO POR DM -----------------
async def send_presence_update(ws):
    """Envía una actualización de presencia al WebSocket"""
    activity = {
        "name": "Custom Status",
        "type": 4,
        "state": current_custom_text,
        "id": "custom"
    }
    
    presence_update = {
        "op": 3,  # Presence Update
        "d": {
            "status": current_status,
            "afk": False,
            "activities": [activity],
            "since": 0
        }
    }
    
    await ws.send(json.dumps(presence_update))
    print(f"{Fore.GREEN}[+] Presence updated to: {current_status}")

async def send_dm_response(ws, user_id, message):
    """Envía un mensaje directo al usuario que envió el comando"""
    # Crear channel DM
    create_dm = {
        "op": 0,
        "d": {
            "recipient_id": user_id
        }
    }
    # Nota: Para enviar mensajes se necesita una petición HTTP, no WebSocket
    # Vamos a usar HTTP para enviar la respuesta
    try:
        # Primero obtener el DM channel
        dm_response = curl_requests.post(
            "https://discord.com/api/v9/users/@me/channels",
            json={"recipient_id": user_id},
            headers=build_headers(),
            impersonate="chrome120"
        )
        
        if dm_response.status_code == 200:
            channel_id = dm_response.json()["id"]
            # Enviar mensaje
            send_response = curl_requests.post(
                f"https://discord.com/api/v9/channels/{channel_id}/messages",
                json={"content": message},
                headers=build_headers(),
                impersonate="chrome120"
            )
            if send_response.status_code == 200:
                print(f"{Fore.GREEN}[+] DM sent to {user_id}")
            else:
                print(f"{Fore.RED}[-] Failed to send DM: {send_response.status_code}")
        else:
            print(f"{Fore.RED}[-] Failed to create DM channel: {dm_response.status_code}")
    except Exception as e:
        print(f"{Fore.RED}[-] Error sending DM: {e}")

# ----------------- RECONEXION AUTOMATICA CON BACKOFF -----------------
async def main():
    print(f"{Fore.YELLOW}[*] ═══════════════════════════════════")
    print(f"{Fore.YELLOW}[*] Starting Discord Self-Bot (With Commands)")
    print(f"{Fore.YELLOW}[*] ═══════════════════════════════════")
    print(f"{Fore.CYAN}[*] Token: {TOKEN[:10]}...{TOKEN[-10:]}")
    print(f"{Fore.CYAN}[*] Status Text: {CUSTOM_STATUS_TEXT}")
    print(f"{Fore.CYAN}[*] Status Mode: {STATUS}")
    print(f"{Fore.CYAN}[*] Local time: {get_local_time()}")
    
    user = verify_token()
    if not user:
        print(f"{Fore.RED}[!] Token verification failed. Retrying in 30s...")
        await asyncio.sleep(30)
    else:
        print(f"{Fore.GREEN}[+] Bot ready! Commands active!")
    
    retry_count = 0
    while True:
        try:
            await discord_gateway()
            retry_count = 0
        except Exception as e:
            print(f"{Fore.RED}[-] Gateway error: {e}")
            retry_count += 1
        
        # Backoff exponencial con máximo de 60s
        wait_time = min(5 + (retry_count * 5), 60)
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
