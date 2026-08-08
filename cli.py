"""A.N.K.A test CLI'i - Core API'ye WebSocket ile baglanir.

Kullanim:
    python cli.py                     # localhost:8000'e baglanir
    python cli.py ws://sunucu:8000    # baska adres

Gereksinim: pip install websockets
"""
from __future__ import annotations

import asyncio
import json
import sys

import websockets

DEFAULT_URL = "ws://localhost:8000/ws/chat"


async def main() -> None:
    base = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    url = base if base.endswith("/ws/chat") else base.rstrip("/") + "/ws/chat"

    print(f"A.N.K.A'ya baglaniliyor: {url}")
    async with websockets.connect(url) as ws:
        print("Baglandi. Cikmak icin 'exit' yaz.\n")
        while True:
            try:
                message = input("sen > ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not message:
                continue
            if message.lower() in ("exit", "quit", "q"):
                break

            await ws.send(json.dumps({"session_id": "cli", "message": message}))

            while True:
                event = json.loads(await ws.recv())
                if event["type"] == "tool_call":
                    print(f"  [arac] {event['name']}({event['args']})")
                elif event["type"] == "tool_result":
                    pass  # sonuc detayi istenirse acilabilir
                elif event["type"] == "final":
                    print(f"anka > {event['text']}\n")
                    break
                elif event["type"] == "error":
                    print(f"  [hata] {event['detail']}\n")
                    break


if __name__ == "__main__":
    asyncio.run(main())
