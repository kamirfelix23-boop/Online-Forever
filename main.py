import asyncio
import json
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import websockets

# Servidor HTTP en segundo plano para engañar al Web Service de Render
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Online 24/7 Running!")

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# Iniciar servidor HTTP en un thread separado
threading.Thread(target=run_http_server, daemon=True).start()

# Lectura segura del TOKEN desde las variables de entorno de Render
TOKEN = os.getenv("TOKEN")
STATUS = os.getenv("STATUS", "online")  # online / dnd / idle
CUSTOM_STATUS = os.getenv("CUSTOM_STATUS", "Hey!")
USE_EMOJI = False

if not TOKEN:
    print("Error: No se encontró la variable de entorno 'TOKEN'. Agrégala en Render.")
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

if USE_EMOJI:
    activity["emoji"] = {
        "name": "🔥",
        "id": None,
        "animated": False
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
