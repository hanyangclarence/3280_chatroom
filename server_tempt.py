import asyncio
import websockets
from config import config
import sys
from typing import List, Dict
import numpy as np
import time


class ChatServer:
    def __init__(self, config):
        self.rooms = {}  # Maps room names to sets of websockets.
        self.audio_buffers = {}  # Maps room names to dict of user_id to audio chunks, Dict[room name, Dict[socket, bytes]
        self.mixing_tasks = {}  # Maps room names to asyncio tasks

        self.max_buffer_size = config["max_buffer_size"]
        self.buffer_duration = config["chunk_size"] / config["rate"] * self.max_buffer_size

    async def handler(self, websocket):
        room_name = await websocket.recv()  # First message is the room name

        if room_name not in self.rooms:
            self.rooms[room_name] = set()
            self.audio_buffers[room_name] = {}
            self.mixing_tasks[room_name] = asyncio.create_task(self.mix_and_broadcast(room_name))

        self.rooms[room_name].add(websocket)
        self.audio_buffers[room_name][websocket] = asyncio.Queue()
        print(f"New client connected to {room_name}. Total clients in room: {len(self.rooms[room_name])}")

        try:
            while True:
                audio_chunk = await websocket.recv()
                await self.audio_buffers[room_name][websocket].put(audio_chunk)
        finally:
            self.rooms[room_name].remove(websocket)
            del self.audio_buffers[room_name][websocket]
            if not self.rooms[room_name]:  # If the room is empty, remove it
                self.mixing_tasks[room_name].cancel()
                del self.rooms[room_name]
                del self.audio_buffers[room_name]
                del self.mixing_tasks[room_name]
                print(f"Room {room_name} deleted as the last client disconnected.")
            else:
                print(f"Client disconnected from {room_name}. Total clients in room: {len(self.rooms[room_name])}")

    async def mix_and_broadcast(self, room_name):
        while True:
            try:
                # wait until all the buffers in the room exceed the max buffer size
                all_buffers_full = False
                while not all_buffers_full:
                    await asyncio.sleep(0.01)  # sleep for a short duration to avoid busy waiting
                    all_buffers_full = all(buffer.qsize() >= self.max_buffer_size for buffer in self.audio_buffers[room_name].values())

                # load self.max_buffer_size of audio chunks from the buffers
                audio_chunks = {}
                for client, buffer in self.audio_buffers[room_name].items():
                    audio_chunks[client] = [await buffer.get() for _ in range(self.max_buffer_size)]

                # broadcast the audio chunks to all clients in the room
                for client in self.rooms[room_name]:
                    # mix the audio chunks except the client's own audio
                    mixed_chunk = self.mix_audio({k: v for k, v in audio_chunks.items() if k != client})

                    if mixed_chunk is None:
                        print(f"No audio chunks to mix: {room_name}", file=sys.stderr)
                        continue

                    # DEBUG: print the shape of the mixed chunk
                    print(f"Mixed chunk shape: {len(mixed_chunk)}", file=sys.stderr)

                    await client.send(mixed_chunk)
                print(f'After broadcast: {time.time()}', file=sys.stderr)
            except Exception as e:
                print(f'error found: {e}', file=sys.stderr)

    def mix_audio(self, audio_chunks) -> bytes:
        if len(audio_chunks) == 0:
            return None

        # Mix the audio chunks by calculating the mean of each chunk over all clients
        audio_chunks: List[List[bytes]] = list(audio_chunks.values()) # List of List of bytes

        # joint the bytes in the list
        audio_chunks: List[bytes] = [b''.join(chunks) for chunks in audio_chunks]

        # average the byte data
        arrays: List[np.ndarray] = [np.frombuffer(chunk, dtype=np.int16) for chunk in audio_chunks]
        mixed_chunk = np.mean(arrays, axis=0).astype(np.int16)

        print(np.max(mixed_chunk), np.min(mixed_chunk), np.mean(mixed_chunk), np.std(mixed_chunk), file=sys.stderr)

        return mixed_chunk.tobytes()

    async def run(self, host, port):
        async with websockets.serve(self.handler, host, port):
            print(f"Server started at ws://{host}:{port}")
            await asyncio.Future()  # run forever


if __name__ == "__main__":
    server = ChatServer(config)
    asyncio.run(server.run("localhost", 5678))
