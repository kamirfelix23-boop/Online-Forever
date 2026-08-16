import asyncio
import json
import os
import threading
import time
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import pytz

# Instalar websockets si no está
try:
    import websockets
except ImportError:
    os.system("pip install websockets")
    import websockets

try:
    import requests
except ImportError:
    os.system("pip install requests")
    import requests

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

TOKEN = os.environ.get("DISCORD_TOKEN", "").strip()
CUSTOM_STATUS_TEXT = os.environ.get("STATUS_TEXT", "Online 24/7")
STATUS = os.environ.get("STATUS_MODE", "online")

if not TOKEN:
    print(f"{Fore.RED}[!] ERROR: DISCORD_TOKEN no está configurado.")
    sys.exit(1)

# Variables globales
current_status = STATUS
current_custom_text = CUSTOM_STATUS_TEXT
bot_user_id = None

# ----------------- VERIFICACION DEL TOKEN -----------------
def verify_token():
    try:
        headers = {"Authorization": TOKEN, "Content-Type": "application/json"}
        r = requests.get("https://discord.com/api/v9/users/@me", headers=headers, timeout=10)
        if r.status_code == 200:
            user = r.json()
            print(f"{Fore.GREEN}[+] Token válido. Conectado como {user['username']} ({user['id']})")
            return user['id']
        else:
            print(f"{Fore.RED}[-] Token inválido. Código: {r.status_code}")
            return None
    except Exception as e:
        print(f"{Fore.RED}[-] Error al verificar token: {e}")
        return None

# ----------------- SERVIDOR WEB PARA RENDER -----------------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(f"Bot Online\nStatus: {current_status}\nText: {current_custom_text}\nTime: {get_local_time()}".encode())
    def log_message(self, format, *args):
        return

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

threading.Thread(target=run_http_server, daemon=True).start()
print(f"{Fore.CYAN}[*] Servidor web iniciado en puerto {os.environ.get('PORT', 8080)}")

# ----------------- FUNCION PARA ENVIAR DM -----------------
def send_dm(user_id, message):
    try:
        headers = {"Authorization": TOKEN, "Content-Type": "application/json"}
        r = requests.post("https://discord.com/api/v9/users/@me/channels", json={"recipient_id": user_id}, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"{Fore.RED}[-] Error al crear DM: {r.status_code}")
            return False
        channel_id = r.json()["id"]
        r2 = requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", json={"content": message}, headers=headers, timeout=10)
        if r2.status_code == 200:
            print(f"{Fore.GREEN}[+] DM enviado a {user_id}")
            return True
        else:
            print(f"{Fore.RED}[-] Error al enviar DM: {r2.status_code}")
            return False
    except Exception as e:
        print(f"{Fore.RED}[-] Excepción en send_dm: {e}")
        return False

# ----------------- GATEWAY WEBSOCKET CON max_size AUMENTADO -----------------
async def discord_gateway():
    global bot_user_id, current_status, current_custom_text
    uri = "wss://gateway.discord.gg/?v=10&encoding=json"

    try:
        # 🔥 Aumentamos el límite de tamaño de mensaje a 10 MB (10485760 bytes)
        async with websockets.connect(uri, max_size=10 * 1024 * 1024) as ws:
            # Recibir hello
            hello = json.loads(await ws.recv())
            heartbeat_interval = hello["d"]["heartbeat_interval"] / 1000
            print(f"{Fore.CYAN}[*] Intervalo de heartbeat: {heartbeat_interval}s")

            # Heartbeat
            async def heartbeat_task():
                while True:
                    await asyncio.sleep(heartbeat_interval)
                    try:
                        await ws.send(json.dumps({"op": 1, "d": None}))
                    except Exception as e:
                        print(f"{Fore.RED}[-] Heartbeat error: {e}")
                        break
            asyncio.create_task(heartbeat_task())

            # --- IDENTIFY ---
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
                        "$client_build_number": 300000,
                        "$client_event_source": None
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
            print(f"{Fore.GREEN}[+] Identificado con Discord. Esperando READY...")

            # ⚠️ Ya no esperamos el READY de forma bloqueante,
            # simplemente iniciamos el bucle de mensajes y manejamos el READY cuando llegue.

            # Bucle principal
            while True:
                try:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    op = data.get("op")

                    if op == 11:  # Heartbeat ACK
                        pass
                    elif op == 7:  # Reconnect
                        print(f"{Fore.YELLOW}[!] Reconnect solicitado")
                        break
                    elif op == 9:  # Invalid session
                        print(f"{Fore.RED}[-] Sesión inválida, reconectando...")
                        break
                    elif op == 0:
                        event_type = data.get("t")
                        if event_type == "READY" and bot_user_id is None:
                            # Guardamos el ID del bot cuando llega el READY
                            bot_user_id = data['d']['user']['id']
                            print(f"{Fore.GREEN}[+] ✅ READY! User ID: {bot_user_id}")
                            print(f"{Fore.GREEN}[+] 🟢 ESTADO: {current_status.upper()}")
                            print(f"{Fore.CYAN}[*] 💬 Comandos por DM: rezty on | idle | dnd | offline | status: texto | help")

                        elif event_type == "MESSAGE_CREATE":
                            msg_data = data.get("d", {})
                            if msg_data.get("guild_id") is None:  # Es DM
                                author = msg_data.get("author", {})
                                author_id = author.get("id")
                                content = msg_data.get("content", "").strip()
                                if author_id == bot_user_id:
                                    continue
                                print(f"{Fore.YELLOW}[*] DM de {author.get('username')}: {content}")

                                # Procesar comando
                                lower = content.lower()
                                if lower.startswith("rezty ") or lower.startswith("rezy "):
                                    cmd = lower.split(" ", 1)[1].strip() if " " in lower else ""

                                    async def do_update(new_status=None, new_text=None, reply=None):
                                        global current_status, current_custom_text
                                        if new_status:
                                            current_status = new_status
                                        if new_text:
                                            current_custom_text = new_text
                                        act = {
                                            "name": "Custom Status",
                                            "type": 4,
                                            "state": current_custom_text,
                                            "id": "custom"
                                        }
                                        presence_payload = {
                                            "op": 3,
                                            "d": {
                                                "status": current_status,
                                                "afk": False,
                                                "activities": [act],
                                                "since": 0
                                            }
                                        }
                                        await ws.send(json.dumps(presence_payload))
                                        print(f"{Fore.GREEN}[+] Presencia actualizada a {current_status}")
                                        if reply:
                                            send_dm(author_id, reply)

                                    if cmd == "on":
                                        await do_update(new_status="online", reply="✅ Estado cambiado a **ONLINE**")
                                    elif cmd == "idle":
                                        await do_update(new_status="idle", reply="💤 Estado cambiado a **IDLE**")
                                    elif cmd == "dnd":
                                        await do_update(new_status="dnd", reply="🚫 Estado cambiado a **DO NOT DISTURB**")
                                    elif cmd == "offline":
                                        await do_update(new_status="invisible", reply="🌙 Estado cambiado a **INVISIBLE**")
                                    elif cmd.startswith("status:"):
                                        new_text = cmd[7:].strip()
                                        if new_text:
                                            await do_update(new_text=new_text, reply=f"📝 Texto personalizado cambiado a: **{new_text}**")
                                        else:
                                            send_dm(author_id, "❌ Escribe: `rezty status: nuevo texto`")
                                    elif cmd == "help":
                                        help_msg = (
                                            "📖 **Comandos:**\n"
                                            "• `rezty on` / `rezy on` → Online\n"
                                            "• `rezty idle` → Ausente\n"
                                            "• `rezty dnd` → No molestar\n"
                                            "• `rezty offline` → Invisible\n"
                                            "• `rezty status: texto` → Cambiar texto\n"
                                            "• `rezty help` → Esta ayuda"
                                        )
                                        send_dm(author_id, help_msg)
                                    else:
                                        send_dm(author_id, "❌ Comando no reconocido. Usa `rezty help`")

                except websockets.exceptions.ConnectionClosed:
                    print(f"{Fore.YELLOW}[!] Conexión cerrada")
                    break
                except Exception as e:
                    print(f"{Fore.RED}[-] Error en el bucle: {e}")
                    # Si el error es por mensaje demasiado grande, lo ignoramos y seguimos
                    if "message too big" in str(e):
                        continue
                    break

    except Exception as e:
        print(f"{Fore.RED}[-] Error al conectar al gateway: {e}")
        await asyncio.sleep(5)

# ----------------- RECONEXION -----------------
async def main():
    print(f"{Fore.YELLOW}[*] ═══════════════════════════════════")
    print(f"{Fore.YELLOW}[*] Bot SelfBot - Versión Estable (con reconexión)")
    print(f"{Fore.YELLOW}[*] ═══════════════════════════════════")
    print(f"{Fore.CYAN}[*] Token: {TOKEN[:10]}...{TOKEN[-10:]}")
    print(f"{Fore.CYAN}[*] Status Text: {CUSTOM_STATUS_TEXT}")
    print(f"{Fore.CYAN}[*] Status Mode: {STATUS}")

    # Verificar token
    user_id = verify_token()
    if not user_id:
        print(f"{Fore.RED}[!] Token inválido. Revisa tu variable DISCORD_TOKEN.")
        await asyncio.sleep(60)

    attempt = 0
    while True:
        try:
            await discord_gateway()
            attempt = 0  # Resetear si la conexión fue exitosa
        except Exception as e:
            print(f"{Fore.RED}[-] Error crítico: {e}")
            attempt += 1
            # Espera exponencial: 5s, 10s, 20s, 30s... máximo 120s
            wait = min(5 * (2 ** (attempt - 1)), 120)
            print(f"{Fore.YELLOW}[!] Reconectando en {wait} segundos... (intento {attempt})")
            await asyncio.sleep(wait)
