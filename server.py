import asyncio
import websockets
from config import config
import sys
from typing import List, Dict, Set, Optional, Any
import numpy as np
import time
from websockets.legacy.server import WebSocketServerProtocol as Socket


class ChatServer:
    def __init__(self, config):
        # Maps room names to sets of websockets.
        self.rooms: Dict[str, Set[Socket]] = {}
        # Maps room names to dict of user_id to audio chunks
        self.audio_buffers: Dict[str, Dict[Socket, asyncio.Queue]] = {}
        # Maps room names to an asyncio task that do audio mixing
        self.mixing_tasks: Dict[str, Any] = {}

        self.max_buffer_size = config["max_buffer_size"]
        self.amplification_factor = config["amplification_factor"]

    async def handler(self, websocket: Socket):
        print("here11",websocket)
        room_name = await websocket.recv()  # First message is the room name
        print("here1",room_name)
        if room_name not in self.rooms:
            self.rooms[room_name]: Set[Socket] = set()
            self.audio_buffers[room_name] = {}
            self.mixing_tasks[room_name] = asyncio.create_task(self.mix_and_broadcast(room_name))

        self.rooms[room_name].add(websocket)
        self.audio_buffers[room_name][websocket] = asyncio.Queue()
        print(f"New client connected to {room_name}. Total clients in room: {len(self.rooms[room_name])}")

        try:
            while True:
                print("here10")
                audio_chunk = await websocket.recv()
                # print(audio_chunk)
                if audio_chunk == "exit":
                    print("here9")
                    break
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

    async def mix_and_broadcast(self, room_name: str):
        while True:
            try:
                # wait until all the buffers in the room exceed the max buffer size
                all_buffers_full = False
                while not all_buffers_full:
                    await asyncio.sleep(0.01)  # sleep for a short duration to avoid busy waiting
                    all_buffers_full = all(
                        buffer.qsize() >= self.max_buffer_size for buffer in self.audio_buffers[room_name].values()
                    )

                # load self.max_buffer_size of audio chunks from the buffers
                audio_chunks: Dict[Socket, List[bytes]] = {}
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

    def mix_audio(self, audio_chunks: Dict[Socket, List[bytes]]) -> Optional[bytes]:
        if len(audio_chunks) == 0:
            return None

        # Mix the audio chunks by calculating the mean of each chunk over all clients
        audio_chunks: List[List[bytes]] = list(audio_chunks.values())

        # joint the bytes in the list
        audio_chunks: List[bytes] = [b''.join(chunks) for chunks in audio_chunks]

        # mix the byte data
        arrays: List[np.ndarray] = [np.frombuffer(chunk, dtype=np.int16) for chunk in audio_chunks]
        # convert to int32 to avoid overflow
        arrays = [arr.astype(np.int32) for arr in arrays]
        # mix the data by summing them
        mixed_chunk = np.sum(arrays, axis=0)
        # amplify the mixed data
        mixed_chunk = mixed_chunk * self.amplification_factor
        # clip the mixed data
        mixed_chunk = np.clip(mixed_chunk, -32768, 32767)
        # convert the mixed data back to int16
        mixed_chunk = mixed_chunk.astype(np.int16)

        return mixed_chunk.tobytes()

    async def run(self, host, port):
        async with websockets.serve(self.handler, host, port):
            print(f"Server started at ws://{host}:{port}")
            await asyncio.Future()  # run forever


if __name__ == "__main__":
    server = ChatServer(config)
    asyncio.run(server.run(config['ip'], config['port']))
