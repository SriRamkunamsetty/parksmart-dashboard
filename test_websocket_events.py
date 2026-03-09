import asyncio
import websockets
import json
import time

async def listen():
    uri = "ws://localhost:8000/ws"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected! Waiting for events...")
            while True:
                message = await websocket.recv()
                data = json.loads(message)
                
                print(f"[{time.strftime('%X')}] Received event:")
                print(json.dumps(data, indent=2))
                
                if data.get("event") == "slot_update":
                    print(f"--> Slot {data.get('slot_id')} is now {data.get('status')} <--\n")
                    
    except KeyboardInterrupt:
        print("Test stopped.")
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    asyncio.run(listen())
