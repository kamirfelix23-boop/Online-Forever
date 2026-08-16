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

TOKEN = os.environ.get("DISCORD_TOKEN", "").strip()  # Eliminar espacios
CUSTOM_STATUS_TEXT = os.environ.get("STATUS_TEXT", "Online 24/7")
STATUS = os.environ.get("STATUS_MODE", "online")

if not TOKEN:
    print(f"{Fore.RED}[!] ERROR: DISCORD_TOKEN no está configurado.")
    sys.exit(1)

# Variables globales
current_status = STATUS
current_custom_text = CUSTOM_STATUS_TEXT
bot_user_id = None

# ----------------- VERIFICACION DEL TOKEN (ANTES DE CONECTAR) -----------------
def verify_token():
    """Comprueba si el token es válido con una llamada REST."""
    try:
        headers = {"Authorization": TOKEN, "Content-Type": "application/json"}
        r = requests.get("https://discord.com/api/v9/users/@me", headers=headers, timeout=10)
        if r.status_code == 200:
            user = r.json()
            print(f"{Fore.GREEN}[+] Token válido. Conectado como {user['username']} ({user['id']})")
            return user['id']
        else:
            print(f"{Fore.RED}[-] Token inválido. Código: {r.status_code}")
            print(f"{Fore.RED}[-] Respuesta: {r.text[:200]}")
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

# ----------------- GATEWAY WEBSOCKET (CON PAYLOAD CORREGIDO) -----------------
async def discord_gateway():
    global bot_user_id, current_status, current_custom_text
    uri = "wss://gateway.discord.gg/?v=10&encoding=json"

    try:
        async with websockets.connect(uri) as ws:
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

            # --- IDENTIFY (PAYLOAD CORRECTO Y COMPLETO) ---
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

            # Esperar el evento READY (con timeout)
            try:
                ready_event = await asyncio.wait_for(ws.recv(), timeout=30)
                ready_data = json.loads(ready_event)
                if ready_data.get("t") == "READY":
                    bot_user_id = ready_data['d']['user']['id']
                    print(f"{Fore.GREEN}[+] ✅ READY! User ID: {bot_user_id}")
                    print(f"{Fore.GREEN}[+] 🟢 ESTADO: {current_status.upper()}")
                    print(f"{Fore.CYAN}[*] 💬 Comandos por DM: rezty on | idle | dnd | offline | status: texto | help")
                else:
                    print(f"{Fore.YELLOW}[!] No se recibió READY, pero la conexión está activa.")
            except asyncio.TimeoutError:
                print(f"{Fore.YELLOW}[!] Timeout esperando READY, pero la conexión podría estar activa.")
            except Exception as e:
                print(f"{Fore.RED}[-] Error al recibir READY: {e}")
                return

            # Bucle principal - ESCUCHAR MENSAJES
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
                        if event_type == "MESSAGE_CREATE":
                            msg_data = data.get("d", {})
                            # DETECTAR DM: si no tiene guild_id
                            if msg_data.get("guild_id") is None:
                                author = msg_data.get("author", {})
                                author_id = author.get("id")
                                content = msg_data.get("content", "").strip()
                                if author_id == bot_user_id:
                                    continue
                                print(f"{Fore.YELLOW}[*] DM de {author.get('username')}: {content}")

                                # Procesar comando (soporta "rezty" y "rezy")
                                lower = content.lower()
                                if lower.startswith("rezty ") or lower.startswith("rezy "):
                                    cmd = lower.split(" ", 1)[1].strip() if " " in lower else ""

                                    async def do_update(new_status=None, new_text=None, reply=None):
                                        global current_status, current_custom_text
                                        if new_status:
                                            current_status = new_status
                                        if new_text:
                                            current_custom_text = new_text
                                        # Enviar actualización de presencia (op 3)
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
                                        print(f"{Fore.GREEN}[+] Presencia actualizada a {current_status} con texto '{current_custom_text}'")
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
                    break

    except Exception as e:
        print(f"{Fore.RED}[-] Error al conectar al gateway: {e}")
        await asyncio.sleep(5)

# ----------------- RECONEXION CON VERIFICACION PREVIA -----------------
async def main():
    print(f"{Fore.YELLOW}[*] ═══════════════════════════════════")
    print(f"{Fore.YELLOW}[*] Bot SelfBot - Versión Estable")
    print(f"{Fore.YELLOW}[*] ═══════════════════════════════════")
    print(f"{Fore.CYAN}[*] Token: {TOKEN[:10]}...{TOKEN[-10:]}")
    print(f"{Fore.CYAN}[*] Status Text: {CUSTOM_STATUS_TEXT}")
    print(f"{Fore.CYAN}[*] Status Mode: {STATUS}")

    # Verificar token antes de intentar conectar
    user_id = verify_token()
    if not user_id:
        print(f"{Fore.RED}[!] El token es inválido. Revisa tu variable DISCORD_TOKEN en Render.")
        print(f"{Fore.YELLOW}[!] Esperando 60 segundos antes de reintentar...")
        await asyncio.sleep(60)
        # Podríamos salir, pero mejor reintentar por si se actualiza la variable
        # return

    while True:
        try:
            await discord_gateway()
        except Exception as e:
            print(f"{Fore.RED}[-] Error crítico: {e}")
        print(f"{Fore.YELLOW}[!] Reconectando en 5 segundos...")
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
