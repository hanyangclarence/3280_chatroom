import asyncio
import websockets
import sys
from config import config
from typing import List, Dict, Set, Optional, Any
import numpy as np
import time
from websockets.legacy.server import WebSocketServerProtocol as Socket
import json


class ChatServer:
    def __init__(self, config):
        # Maps room names to sets of websockets.
        self.rooms: Dict[str, Set[Socket]] = {}
        self.rooms2: Dict[str, Set[Socket]] = {}
        # Maps room names to dict of user_id to audio chunks
        self.audio_buffers: Dict[str, Dict[Socket, asyncio.Queue]] = {}
        self.video_buffers: Dict[str, Dict[Socket, bytes]] = {}
        # Maps room names to an asyncio task that do audio mixing
        self.mixing_tasks: Dict[str, Any] = {}
        self.video_broadcast_tasks: Dict[str, Any] = {}
        self.room_list: Set[str] = set()  # Maintain a list of all rooms

        self.max_buffer_size = config["max_buffer_size"]
        self.amplification_factor = config["amplification_factor"]
        self.socket_name_mapping: Dict[str, (Socket, Socket)] = {}
   
    async def handler(self, websocket: Socket, path):
        message = await websocket.recv()
        try:
            if isinstance(message, bytes):
                action = message.decode('utf-8')
            else:
                action = message
        except UnicodeDecodeError:
            print("Received data could not be decoded as UTF-8. It might be binary data.")
            return  
        
        if action == "LIST":
            await websocket.send(",".join(self.room_list))
            return  
        elif action.startswith("CREATE"):
            room_name = action.split()[1]
            if room_name not in self.rooms:
                self.rooms[room_name]: Set[Socket] = set()
                self.rooms2[room_name]: Set[Socket] = set()
                self.audio_buffers[room_name] = {}
                self.mixing_tasks[room_name] = asyncio.create_task(self.mix_and_broadcast(room_name))
                self.video_buffers[room_name] = {}
                self.video_broadcast_tasks[room_name] = asyncio.create_task(self.broadcast_video(room_name))
                self.room_list.add(room_name)
                await websocket.send(f"Room {room_name} created.")
            else:
                await websocket.send(f"Room {room_name} already exists.")
            return  
        elif action.startswith("DELETE"):
            room_name = action.split()[1]
            if room_name in self.rooms:
                self.delete_room(room_name)
                await websocket.send(f"Room {room_name} deleted.")
            else:
                await websocket.send("Room not found.")
            return  
        elif action.startswith("LEAVE"):
            room_name = action.split()[1]
            if room_name in self.rooms and websocket in self.rooms[room_name]:
                self.rooms[room_name].remove(websocket)
                print(f"Client disconnected from room: {room_name}.")
        else:
            await self.handle_join(websocket, action)

    async def handler2(self, websocket: Socket, path):
        message = await websocket.recv()

        await self.handle_join2(websocket, message)
    async def handle_join(self, websocket: Socket, message: str):
        data = json.loads(message)
        room_name = data['room']
        if room_name not in self.rooms:
            self.rooms[room_name]: Set[Socket] = set()
            self.rooms2[room_name]: Set[Socket] = set()
            self.audio_buffers[room_name] = {}
            self.mixing_tasks[room_name] = asyncio.create_task(self.mix_and_broadcast(room_name))
            self.video_buffers[room_name] = {}
            self.video_broadcast_tasks[room_name] = asyncio.create_task(self.broadcast_video(room_name))
            self.room_list.add(room_name)  # Add the room name to the room list
            print(f"Room {room_name} created and added to the room list.")

        self.rooms[room_name].add(websocket)
        self.audio_buffers[room_name][websocket] = asyncio.Queue()
        print(f"New client connected to {room_name}. Total clients in room: {len(self.rooms[room_name])}")

        try:
            while websocket in self.rooms[room_name]:
                message = await websocket.recv()
                await self.audio_buffers[room_name][websocket].put(message[5:])

        finally:
            if websocket in self.rooms[room_name]:
                self.rooms[room_name].remove(websocket)
            if websocket in self.audio_buffers[room_name]:
                del self.audio_buffers[room_name][websocket]
            if len(self.rooms[room_name]) == 0:
                print(f"No clients left in room: {room_name}, but the room remains until explicitly deleted.")
            else:
                print(f"Client disconnected from {room_name}. Total clients in room: {len(self.rooms[room_name])}")

    async def handle_join2(self, websocket: Socket, message: str):
        data = json.loads(message)
        room_name = data['room']
        self.rooms2[room_name].add(websocket)
        self.video_buffers[room_name][websocket] = b''
        print(f"New client connected to {room_name}. Total clients in room: {len(self.rooms[room_name])}")

        try:
            while websocket in self.rooms2[room_name]:
                message = await websocket.recv()
                self.video_buffers[room_name][websocket] = message[5:]

        finally:
            if websocket in self.rooms[room_name]:
                self.rooms2[room_name].remove(websocket)
            if websocket in self.audio_buffers[room_name]:
                del self.audio_buffers[room_name][websocket]
            if len(self.rooms2[room_name]) == 0:
                print(f"No clients left in room: {room_name}, but the room remains until explicitly deleted.")
            else:
                print(f"Client disconnected from {room_name}. Total clients in room: {len(self.rooms[room_name])}")

    def delete_room(self, room_name: str):
        self.mixing_tasks[room_name].cancel()
        del self.rooms[room_name]
        del self.audio_buffers[room_name]
        del self.mixing_tasks[room_name]
        self.room_list.remove(room_name)

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
                # print(f'After broadcast: {time.time()}', file=sys.stderr)
            except Exception as e:
                print(f'error found in audio: {e}', file=sys.stderr)
    async def broadcast_video(self, room_name: str):
        while True:
            # try:
                # wait until all the buffers in the room exceed the max buffer size
                all_buffers_full = False
                while not all_buffers_full:
                    await asyncio.sleep(0.01)  # sleep for a short duration to avoid busy waiting
                    all_buffers_full = all(
                        (buffer != b'') for buffer in self.video_buffers[room_name].values()
                    )

                # load self.max_buffer_size of video chunks from the buffers
                video_frame: Dict[Socket, bytes] = {}
                for client, buffer in self.video_buffers[room_name].items():
                    video_frame[client] = buffer

                # broadcast the audio chunks to all clients in the room
                for client in self.rooms2[room_name]:
                    counter = 0
                    for socket, data in video_frame.items():
                        if socket != client:
                            print("here2")
                            await client.send(b'V'+counter.to_bytes(4, byteorder='big')+data)
                            counter += 1
                # print(f'After broadcast: {time.time()}', file=sys.stderr)
            # except Exception as e:
                # print(f'error found in video: {e}', file=sys.stderr)

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
        server = await websockets.serve(self.handler, host, port)
        print(f"Server started at ws://{host}:{port}")
        await server.wait_closed()

    async def run2(self, host, port):
        server = await websockets.serve(self.handler2, host, port)
        print(f"Server2 started at ws://{host}:{port}")
        await server.wait_closed()

async def main():
    server = ChatServer(config)
    # 使用 asyncio.gather 同时启动两个 WebSocket 服务器
    await asyncio.gather(
        server.run(config['ip'], config['port']),
        server.run2(config['ip'], 5679)
    )

if __name__ == "__main__":
    # 运行主函数以启动服务器
    asyncio.run(main())
