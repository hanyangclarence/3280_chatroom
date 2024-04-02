import asyncio
import websockets


class ChatServer:
    def __init__(self):
        self.connected_clients = set()

    async def handler(self, websocket):
        self.connected_clients.add(websocket)
        print(f"New client connected. Total clients: {len(self.connected_clients)}")
        try:
            while True:
                message = await websocket.recv()
                await self.broadcast(message, websocket)
                print(f'{websocket.remote_address}', end=' ')
                for client in self.connected_clients:
                    print(f'{client.remote_address}', end=' ')
                print()
        finally:
            self.connected_clients.remove(websocket)
            print(f"Client disconnected. Total clients: {len(self.connected_clients)}")

    async def broadcast(self, message, sender):
        for client in self.connected_clients:
            if client != sender:
                await client.send(message)
                await asyncio.sleep(0)

    async def run(self, host, port):
        async with websockets.serve(self.handler, host, port):
            print(f"Server started at ws://{host}:{port}")
            await asyncio.Future()  # run forever


if __name__ == "__main__":
    server = ChatServer()
    # asyncio.run(server.run("10.13.25.124", 5678))
    asyncio.run(server.run("localhost", 5678))
