
import asyncio
import websockets
import json

async def test_ws():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        print("Connected to WS")
        for _ in range(10):
            message = await websocket.recv()
            data = json.loads(message)
            print(f"Received type: {data['type']}")
            if data['type'] == 'telemetry':
                print(f"  Speed: {data['data']['speed']}")
        print("WS Test passed")

if __name__ == "__main__":
    asyncio.run(test_ws())
