"""Cliente manual do WebSocket `/ws`: conecta no backend local e mostra 10 mensagens.

Era `backend/test_ws_client.py`. O pytest o colhia como teste quando a suite rodava na
pasta `backend`, e ele falhava (funcao assincrona, sem plugin para isso). Saiu da
coleta no pedido 40. Uso, com o backend no ar: python tools/ws_client.py
"""

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
