import asyncio
import json
import os
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytz
import requests
import websockets
from colorama import Fore, init

init(autoreset=True)

# ----------------- CONFIGURACION -----------------
TIMEZONE = pytz.timezone("America/Argentina/Buenos_Aires")


def get_local_time():
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")


TOKEN = os.environ.get("DISCORD_TOKEN", "").strip()
CUSTOM_STATUS_TEXT = os.environ.get("STATUS_TEXT", "Online 24/7")
STATUS = os.environ.get("STATUS_MODE", "online")

if not TOKEN:
    print(f"{Fore.RED}[!] ERROR: DISCORD_TOKEN no está configurado.")
    sys.exit(1)

current_status = STATUS
current_custom_text = CUSTOM_STATUS_TEXT
bot_user_id = None
HEADERS = {"Authorization": TOKEN, "Content-Type": "application/json"}


# ----------------- VERIFICACION DEL TOKEN -----------------
def verify_token():
    try:
        r = requests.get("https://discord.com/api/v9/users/@me", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            user = r.json()
            print(f"{Fore.GREEN}[+] Token válido. Conectado como {user['username']} ({user['id']})")
            return user["id"]
        print(f"{Fore.RED}[-] Token inválido. Código: {r.status_code}")
    except Exception as e:
        print(f"{Fore.RED}[-] Error al verificar token: {e}")
    return None


# ----------------- SERVIDOR WEB PARA RENDER -----------------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(
            f"Bot Online\nStatus: {current_status}\nText: {current_custom_text}\nTime: {get_local_time()}".encode()
        )

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return


def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()


# ----------------- ENVIAR DM -----------------
def send_dm(user_id, message):
    try:
        r = requests.post(
            "https://discord.com/api/v9/users/@me/channels",
            json={"recipient_id": user_id}, headers=HEADERS, timeout=10,
        )
        if r.status_code != 200:
            print(f"{Fore.RED}[-] Error al crear DM: {r.status_code}")
            return False
        channel_id = r.json()["id"]
        r2 = requests.post(
            f"https://discord.com/api/v9/channels/{channel_id}/messages",
            json={"content": message}, headers=HEADERS, timeout=10,
        )
        if r2.status_code == 200:
            print(f"{Fore.GREEN}[+] DM enviado a {user_id}")
            return True
        print(f"{Fore.RED}[-] Error al enviar DM: {r2.status_code}")
    except Exception as e:
        print(f"{Fore.RED}[-] Excepción en send_dm: {e}")
    return False


async def dm(user_id, message):
    # requests es bloqueante; lo mandamos a un hilo para no frenar el heartbeat
    await asyncio.to_thread(send_dm, user_id, message)


def make_activity():
    return {"name": "Custom Status", "type": 4, "state": current_custom_text, "id": "custom"}


HELP_MSG = (
    "📖 **Comandos:**\n"
    "• `rezty on` / `rezy on` → Online\n"
    "• `rezty idle` → Ausente\n"
    "• `rezty dnd` → No molestar\n"
    "• `rezty offline` → Invisible\n"
    "• `rezty status: texto` → Cambiar texto\n"
    "• `rezty help` → Esta ayuda"
)


# ----------------- GATEWAY -----------------
async def discord_gateway():
    """Una sesión del gateway. Retorna cuando se cierra o hay que reconectar."""
    global bot_user_id, current_status, current_custom_text
    uri = "wss://gateway.discord.gg/?v=10&encoding=json"
    seq = None
    hb_task = None

    try:
        async with websockets.connect(uri, max_size=10 * 1024 * 1024) as ws:
            hello = json.loads(await ws.recv())
            heartbeat_interval = hello["d"]["heartbeat_interval"] / 1000
            print(f"{Fore.CYAN}[*] Intervalo de heartbeat: {heartbeat_interval}s")

            async def heartbeat():
                while True:
                    await asyncio.sleep(heartbeat_interval)
                    await ws.send(json.dumps({"op": 1, "d": seq}))

            hb_task = asyncio.create_task(heartbeat())

            await ws.send(json.dumps({
                "op": 2,
                "d": {
                    "token": TOKEN,
                    "properties": {"os": "Windows", "browser": "Chrome", "device": ""},
                    "presence": {
                        "status": current_status,
                        "afk": False,
                        "since": 0,
                        "activities": [make_activity()],
                    },
                },
            }))
            print(f"{Fore.GREEN}[+] Identificado con Discord. Esperando READY...")

            async def update(new_status=None, new_text=None, reply=None, to=None):
                global current_status, current_custom_text
                if new_status:
                    current_status = new_status
                if new_text:
                    current_custom_text = new_text
                await ws.send(json.dumps({
                    "op": 3,
                    "d": {
                        "status": current_status,
                        "afk": False,
                        "since": 0,
                        "activities": [make_activity()],
                    },
                }))
                print(f"{Fore.GREEN}[+] Presencia actualizada a {current_status}")
                if reply:
                    await dm(to, reply)

            while True:
                data = json.loads(await ws.recv())
                op = data.get("op")
                if data.get("s") is not None:
                    seq = data["s"]

                if op == 1:  # Discord pide heartbeat ya
                    await ws.send(json.dumps({"op": 1, "d": seq}))
                elif op == 7:
                    print(f"{Fore.YELLOW}[!] Reconnect solicitado")
                    return
                elif op == 9:
                    print(f"{Fore.RED}[-] Sesión inválida, reconectando...")
                    return
                elif op == 0:
                    t = data.get("t")
                    d = data.get("d", {})
                    if t == "READY":
                        bot_user_id = d["user"]["id"]
                        print(f"{Fore.GREEN}[+] READY! User ID: {bot_user_id}")
                        print(f"{Fore.GREEN}[+] ESTADO: {current_status.upper()}")
                        print(f"{Fore.CYAN}[*] Comandos por DM: rezty on | idle | dnd | offline | status: texto | help")
                    elif t == "MESSAGE_CREATE" and d.get("guild_id") is None:
                        author = d.get("author", {})
                        author_id = author.get("id")
                        content = d.get("content", "").strip()
                        if author_id == bot_user_id:
                            continue
                        print(f"{Fore.YELLOW}[*] DM de {author.get('username')}: {content}")

                        lower = content.lower()
                        if not (lower.startswith("rezty ") or lower.startswith("rezy ")):
                            continue
                        cmd = lower.split(" ", 1)[1].strip()

                        if cmd == "on":
                            await update("online", reply="✅ Estado cambiado a **ONLINE**", to=author_id)
                        elif cmd == "idle":
                            await update("idle", reply="💤 Estado cambiado a **IDLE**", to=author_id)
                        elif cmd == "dnd":
                            await update("dnd", reply="🚫 Estado cambiado a **DO NOT DISTURB**", to=author_id)
                        elif cmd == "offline":
                            await update("invisible", reply="🌙 Estado cambiado a **INVISIBLE**", to=author_id)
                        elif cmd.startswith("status:"):
                            new_text = cmd[7:].strip()
                            if new_text:
                                await update(new_text=new_text, reply=f"📝 Texto personalizado cambiado a: **{new_text}**", to=author_id)
                            else:
                                await dm(author_id, "❌ Escribe: `rezty status: nuevo texto`")
                        elif cmd == "help":
                            await dm(author_id, HELP_MSG)
                        else:
                            await dm(author_id, "❌ Comando no reconocido. Usa `rezty help`")

    except websockets.exceptions.ConnectionClosed as e:
        print(f"{Fore.YELLOW}[!] Conexión cerrada (código {e.code})")
        if e.code == 4004:
            print(f"{Fore.RED}[-] Token rechazado por Discord (4004). Saca un token nuevo.")
            await asyncio.sleep(300)
    except Exception as e:
        print(f"{Fore.RED}[-] Error en el gateway: {e}")
    finally:
        if hb_task:
            hb_task.cancel()


# ----------------- RECONEXION -----------------
async def main():
    print(f"{Fore.YELLOW}[*] ═══════════════════════════════════")
    print(f"{Fore.YELLOW}[*] Bot SelfBot - Versión Estable (con reconexión)")
    print(f"{Fore.YELLOW}[*] ═══════════════════════════════════")
    print(f"{Fore.CYAN}[*] Status Text: {CUSTOM_STATUS_TEXT}")
    print(f"{Fore.CYAN}[*] Status Mode: {STATUS}")

    if not verify_token():
        print(f"{Fore.RED}[!] Token inválido. Revisa tu variable DISCORD_TOKEN.")

    attempt = 0
    while True:
        started = time.monotonic()
        await discord_gateway()
        # Sesión corta = algo anda mal: espera creciente para no spamear a Discord
        if time.monotonic() - started < 30:
            attempt += 1
        else:
            attempt = 0
        wait = min(5 * (2 ** attempt), 300) if attempt else 5
        print(f"{Fore.YELLOW}[!] Reconectando en {wait}s (intento {attempt})")
        await asyncio.sleep(wait)


if __name__ == "__main__":
    threading.Thread(target=run_http_server, daemon=True).start()
    print(f"{Fore.CYAN}[*] Servidor web iniciado en puerto {os.environ.get('PORT', 8080)}")
    asyncio.run(main())
