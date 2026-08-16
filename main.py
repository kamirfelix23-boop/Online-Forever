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

# ----------------- ANTI-DETECCION TLS SPOOFING -----------------
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

# Variables globales de estado
current_status = STATUS
current_custom_text = CUSTOM_STATUS_TEXT
bot_user_id = None

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
        status_msg = f"Discord Self-Bot Running\nStatus: {current_status}\nCustom Status: {current_custom_text}\nTime: {get_local_time()}"
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
    global bot_user_id
    try:
        response = curl_requests.get(
            "https://discord.com/api/v9/users/@me",
            headers=build_headers(),
            timeout=15,
            impersonate="chrome120"
        )
        if response.status_code == 200:
            user = response.json()
            bot_user_id = user['id']
            print(f"{Fore.GREEN}[+] Logged in as {user['username']} ({user['id']})!")
            return True
        else:
            print(f"{Fore.RED}[-] Invalid token! Status: {response.status_code}")
            return False
    except Exception as e:
        print(f"{Fore.RED}[-] Token verification error: {e}")
        return False

# ----------------- ACTUALIZAR STATUS -----------------
def update_status(new_status=None, new_text=None):
    global current_status, current_custom_text
    if new_status:
        current_status = new_status
    if new_text:
        current_custom_text = new_text
    print(f"{Fore.CYAN}[*] Status updated to: {current_status}")
    print(f"{Fore.CYAN}[*] Custom text: {current_custom_text}")

# ----------------- ENVIAR MENSAJE DM POR HTTP -----------------
def send_dm_message(user_id, message):
    """Envía un mensaje directo usando HTTP con anti-detección"""
    try:
        # Crear canal DM
        dm_channel = curl_requests.post(
            "https://discord.com/api/v9/users/@me/channels",
            json={"recipient_id": user_id},
            headers=build_headers(),
            impersonate="chrome120",
            timeout=10
        )
        if dm_channel.status_code != 200:
            print(f"{Fore.RED}[-] Failed to create DM: {dm_channel.status_code} - {dm_channel.text}")
            return False
        
        channel_id = dm_channel.json()["id"]
        
        # Enviar mensaje
        send_msg = curl_requests.post(
            f"https://discord.com/api/v9/channels/{channel_id}/messages",
            json={"content": message},
            headers=build_headers(),
            impersonate="chrome120",
            timeout=10
        )
        if send_msg.status_code == 200:
            print(f"{Fore.GREEN}[+] DM sent to {user_id}")
            return True
        else:
            print(f"{Fore.RED}[-] Failed to send DM: {send_msg.status_code} - {send_msg.text}")
            return False
    except Exception as e:
        print(f"{Fore.RED}[-] Error sending DM: {e}")
        return False

# ----------------- GATEWAY WEBSOCKET CON COMANDOS -----------------
async def discord_gateway():
    import websockets
    uri = "wss://gateway.discord.gg/?v=10&encoding=json"
    
    try:
        async with websockets.connect(uri) as ws:
            # Hello
            hello = json.loads(await ws.recv())
            heartbeat_interval = hello["d"]["heartbeat_interval"] / 1000
            print(f"{Fore.CYAN}[*] Heartbeat interval: {heartbeat_interval}s")

            # Heartbeat con jitter
            async def heartbeat_task():
                while True:
                    jitter = random.uniform(-0.3, 0.3)
                    await asyncio.sleep(heartbeat_interval + jitter)
                    await ws.send(json.dumps({"op": 1, "d": None}))
                    local_time = get_local_time()
                    print(f"{Fore.GREEN}[{local_time}] Heartbeat sent")
            
            asyncio.create_task(heartbeat_task())

            # Identify (presencia)
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

            # Esperar READY
            ready_event = await ws.recv()
            ready_data = json.loads(ready_event)
            if ready_data.get("t") == "READY":
                user_id = ready_data['d']['user']['id']
                print(f"{Fore.GREEN}[+] ✅ READY! User ID: {user_id}")
                print(f"{Fore.GREEN}[+] 🟢 You are ONLINE!")
                print(f"{Fore.CYAN}[*] 💬 Send 'rezty on' or 'rezy on' to set online")
                print(f"{Fore.CYAN}[*] 💬 Send 'rezty idle' to set idle")
                print(f"{Fore.CYAN}[*] 💬 Send 'rezty dnd' to set DND")
                print(f"{Fore.CYAN}[*] 💬 Send 'rezty offline' to set offline")
                print(f"{Fore.CYAN}[*] 💬 Send 'rezty status: texto' to change custom status")

            # Bucle principal
            while True:
                try:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    op = data.get("op")
                    
                    if op == 11:
                        pass  # Heartbeat ACK
                    elif op == 7:
                        print(f"{Fore.YELLOW}[!] Reconnect requested")
                        break
                    elif op == 9:
                        print(f"{Fore.RED}[-] Invalid session")
                        break
                    elif op == 0:
                        event_type = data.get("t")
                        
                        # --- DETECTAR MENSAJES DIRECTOS ---
                        if event_type == "MESSAGE_CREATE":
                            msg_data = data.get("d", {})
                            # Es DM si NO tiene guild_id
                            if msg_data.get("guild_id") is None:
                                author = msg_data.get("author", {})
                                author_id = author.get("id")
                                content = msg_data.get("content", "").strip()
                                channel_id = msg_data.get("channel_id")
                                
                                # Ignorar mensajes del propio bot
                                if author_id == bot_user_id:
                                    continue
                                
                                print(f"{Fore.YELLOW}[*] DM from {author.get('username')} ({author_id}): {content}")
                                
                                # --- PROCESAR COMANDOS (soporta "rezty" y "rezy") ---
                                lower_content = content.lower()
                                if lower_content.startswith("rezty ") or lower_content.startswith("rezy "):
                                    # Extraer comando
                                    parts = lower_content.split(" ", 1)
                                    if len(parts) < 2:
                                        continue
                                    command = parts[1].strip()
                                    
                                    # Comandos de estado
                                    if command == "on":
                                        update_status("online")
                                        await send_presence_update(ws)
                                        send_dm_message(author_id, "✅ Status set to **ONLINE**")
                                    
                                    elif command == "idle":
                                        update_status("idle")
                                        await send_presence_update(ws)
                                        send_dm_message(author_id, "💤 Status set to **IDLE**")
                                    
                                    elif command == "dnd":
                                        update_status("dnd")
                                        await send_presence_update(ws)
                                        send_dm_message(author_id, "🚫 Status set to **DO NOT DISTURB**")
                                    
                                    elif command == "offline":
                                        update_status("invisible")
                                        await send_presence_update(ws)
                                        send_dm_message(author_id, "🌙 Status set to **OFFLINE** (invisible)")
                                    
                                    elif command.startswith("status:"):
                                        new_text = command[7:].strip()
                                        if new_text:
                                            update_status(None, new_text)
                                            await send_presence_update(ws)
                                            send_dm_message(author_id, f"📝 Custom status changed to: **{new_text}**")
                                        else:
                                            send_dm_message(author_id, "❌ Please provide text: `rezty status: nuevo texto`")
                                    
                                    elif command == "help":
                                        help_msg = (
                                            "📖 **Comandos disponibles:**\n"
                                            "• `rezty on` / `rezy on` - Set online\n"
                                            "• `rezty idle` - Set idle\n"
                                            "• `rezty dnd` - Set Do Not Disturb\n"
                                            "• `rezty offline` - Set offline (invisible)\n"
                                            "• `rezty status: texto` - Change custom status text\n"
                                            "• `rezty help` - Show this message"
                                        )
                                        send_dm_message(author_id, help_msg)
                                    else:
                                        send_dm_message(author_id, "❌ Unknown command. Send `rezty help` for available commands.")

                except websockets.exceptions.ConnectionClosed:
                    print(f"{Fore.YELLOW}[!] Connection closed")
                    break
                except Exception as e:
                    print(f"{Fore.RED}[-] Error in gateway: {e}")
                    break
    except Exception as e:
        print(f"{Fore.RED}[-] Failed to connect: {e}")
        await asyncio.sleep(5)

# ----------------- FUNCION PARA ACTUALIZAR PRESENCIA POR WS -----------------
async def send_presence_update(ws):
    activity = {
        "name": "Custom Status",
        "type": 4,
        "state": current_custom_text,
        "id": "custom"
    }
    presence = {
        "op": 3,
        "d": {
            "status": current_status,
            "afk": False,
            "activities": [activity],
            "since": 0
        }
    }
    await ws.send(json.dumps(presence))
    print(f"{Fore.GREEN}[+] Presence updated to {current_status} with text '{current_custom_text}'")

# ----------------- MAIN -----------------
async def main():
    print(f"{Fore.YELLOW}[*] ═══════════════════════════════════")
    print(f"{Fore.YELLOW}[*] Starting Discord Self-Bot (Commands)")
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
        
        wait_time = min(5 + (retry_count * 5), 60)
        print(f"{Fore.YELLOW}[!] Reconnecting in {wait_time} seconds...")
        await asyncio.sleep(wait_time)

if __name__ == "__main__":
    try:
        import websockets
    except ImportError:
        os.system("pip install websockets")
        import websockets
    asyncio.run(main())
