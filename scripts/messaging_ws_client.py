#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import websockets


async def reader(ws: websockets.WebSocketClientProtocol) -> None:
    try:
        async for message in ws:
            print(f"< {message}")
    except websockets.exceptions.ConnectionClosed:
        print("Connection closed by server.")


async def writer(ws: websockets.WebSocketClientProtocol) -> None:
    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            # Validate JSON
            json.loads(line)
            await ws.send(line)
        except json.JSONDecodeError:
            print("Invalid JSON, skipping.")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Messaging WebSocket Client")
    parser.add_argument("--url", default="ws://localhost:8000/api/v1/messaging/ws", help="WebSocket URL")
    parser.add_argument("--token", default=os.getenv("MESSAGING_TOKEN"), help="Access token")
    args = parser.parse_args()

    token = args.token
    if not token:
        print("Error: --token or MESSAGING_TOKEN environment variable required.")
        sys.exit(1)

    print(f"Connecting to {args.url}...")
    async with websockets.connect(args.url) as ws:
        # Send auth frame
        auth_frame = json.dumps({"type": "auth", "access_token": token})
        await ws.send(auth_frame)
        print("Sent auth frame.")

        await asyncio.gather(reader(ws), writer(ws))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
