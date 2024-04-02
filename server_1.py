import asyncio
import websockets

class ChatServer:
    def __init__(self):
        self.rooms = {}  # Maps room names to sets of websockets.

    async def handler(self, websocket):
        room_name = await websocket.recv()  # First message is the room name
        if room_name not in self.rooms:
            self.rooms[room_name] = set()
        self.rooms[room_name].add(websocket)
        print(f"New client connected to {room_name}. Total clients in room: {len(self.rooms[room_name])}")
        try:
            while True:
                message = await websocket.recv()
                await self.broadcast(message, websocket, room_name)
        finally:
            self.rooms[room_name].remove(websocket)
            if not self.rooms[room_name]:  # If the room is empty, remove it
                del self.rooms[room_name]
                print(f"Room {room_name} deleted as the last client disconnected.")
            else:
                print(f"Client disconnected from {room_name}. Total clients in room: {len(self.rooms[room_name])}")


    async def broadcast(self, message, sender, room_name):
        for client in self.rooms[room_name]:
            if client != sender:
                await client.send(message)

    async def run(self, host, port):
        async with websockets.serve(self.handler, host, port):
            print(f"Server started at ws://{host}:{port}")
            await asyncio.Future()  # run forever

if __name__ == "__main__":
    server = ChatServer()
    asyncio.run(server.run("10.13.181.168", 5678))
