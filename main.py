import asyncio
import json
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import websockets

# Servidor HTTP mejorado para evitar errores 501 / 500 con UptimeRobot
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot 24/7 de Discord Activo")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

    # Silenciar logs molestos en consola
    def log_message(self, format, *args):
        return

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_http_server, daemon=True).start()

# Cargar TOKEN de las variables de entorno de Render
TOKEN = os.getenv("TOKEN")
STATUS = os.getenv("STATUS", "online")
CUSTOM_STATUS = os.getenv("CUSTOM_STATUS", "✅ 1.5$ Rust, cheatvault.net")

if not TOKEN:
    print("Error: Falta la variable TOKEN en las configuraciones de Render.")
    exit(1)

headers = {"Authorization": TOKEN}

r = requests.get("https://discord.com/api/v10/users/@me", headers=headers)
if r.status_code != 200:
    print("Invalid token!")
    exit(1)

user = r.json()
print(f"Logged in as {user['username']} ({user['id']})!")

activity = {
    "name": "Custom Status",
    "type": 4,
    "state": CUSTOM_STATUS,
    "id": "custom"
}

async def discord_gateway():
    uri = "wss://gateway.discord.gg/?v=10&encoding=json"

    async with websockets.connect(uri) as ws:
        hello = json.loads(await ws.recv())
        heartbeat_interval = hello["d"]["heartbeat_interval"]

        async def heartbeat():
            while True:
                await asyncio.sleep(heartbeat_interval / 1000)
                await ws.send(json.dumps({"op": 1, "d": None}))

        asyncio.create_task(heartbeat())

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
                    "status": STATUS,
                    "afk": False,
                    "activities": [activity]
                }
            }
        }
        await ws.send(json.dumps(identify))

        while True:
            try:
                msg = await ws.recv()
                data = json.loads(msg)

                if data.get("op") == 11:
                    pass

            except Exception as e:
                print("Connection lost, reconnecting...", e)
                break

async def main():
    while True:
        await discord_gateway()
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
