import asyncio
import websockets
import sys
from config import config
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
        self.room_list: Set[str] = set()  # Maintain a list of all rooms
        # Dict of muted clients in each room
        self.muted_clients: Dict[str, List[Socket]] = {}

        # set self.audio_chunk_size to the size of each audio chunk in bytes
        self.audio_chunk_size = config['chunk_size'] * config['channel'] * 2  # 2 bytes per sample
        self.max_buffer_size = config["max_buffer_size"]
        self.amplification_factor = config["amplification_factor"]
   
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
                self.audio_buffers[room_name] = {}
                self.muted_clients[room_name] = []
                self.mixing_tasks[room_name] = asyncio.create_task(self.mix_and_broadcast(room_name))
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

    async def handle_join(self, websocket: Socket, room_name: str):
        if room_name not in self.rooms:
            raise Exception('This condition should not be reached')
            self.rooms[room_name]: Set[Socket] = set()
            self.audio_buffers[room_name] = {}
            self.muted_clients[room_name] = []
            self.mixing_tasks[room_name] = asyncio.create_task(self.mix_and_broadcast(room_name))
            self.room_list.add(room_name)  # Add the room name to the room list

        self.rooms[room_name].add(websocket)
        self.audio_buffers[room_name][websocket] = asyncio.Queue()
        self.print_status()

        try:
            while True:
                audio_chunk = await websocket.recv()
                if isinstance(audio_chunk, bytes):
                    if websocket in self.muted_clients[room_name]:
                        # previously the client is muted, then unmute the client
                        self.remove_client_from_mutelist(room_name, websocket)
                        self.print_status()
                    await self.audio_buffers[room_name][websocket].put(audio_chunk)
                else:
                    assert audio_chunk == 'MUTE', f"Invalid message received: {audio_chunk}, {type(audio_chunk)}"
                    # if MUTE is received, add the client to the muted list
                    if websocket not in self.muted_clients[room_name]:
                        self.muted_clients[room_name].append(websocket)
                        # clean up the corresponding audio buffer
                        while not self.audio_buffers[room_name][websocket].empty():
                            self.audio_buffers[room_name][websocket].get_nowait()
                        self.print_status()
        finally:
            if websocket in self.rooms[room_name]:
                self.rooms[room_name].remove(websocket)
            if websocket in self.audio_buffers[room_name]:
                del self.audio_buffers[room_name][websocket]
            if websocket in self.muted_clients[room_name]:
                self.muted_clients[room_name].remove(websocket)

            if len(self.rooms[room_name]) == 0:
                print(f"No clients left in room: {room_name}, but the room remains until explicitly deleted.")
            else:
                print(f"Client disconnected from {room_name}. Total clients in room: {len(self.rooms[room_name])}")
            self.print_status()

    def delete_room(self, room_name: str):
        self.mixing_tasks[room_name].cancel()
        del self.rooms[room_name]
        del self.audio_buffers[room_name]
        del self.mixing_tasks[room_name]
        del self.muted_clients[room_name]
        self.room_list.remove(room_name)

    async def mix_and_broadcast(self, room_name: str):
        while True:
            try:
                # wait until all the buffers in the room exceed the max buffer size, except the muted clients
                while True:
                    if len(self.rooms[room_name]) > 0:
                        if all(
                            buffer.qsize() >= self.max_buffer_size
                            for usr, buffer in self.audio_buffers[room_name].items()
                            if usr not in self.muted_clients[room_name]
                        ):
                            if len(self.rooms[room_name]) != len(self.muted_clients[room_name]):
                                # ensure that there is at least one non-muted client in the room
                                break
                    await asyncio.sleep(0.01)

                # load self.max_buffer_size of audio chunks from the buffers, except the muted clients
                audio_chunks: Dict[Socket, List[bytes]] = {}
                for client, buffer in self.audio_buffers[room_name].items():
                    if client not in self.muted_clients[room_name]:
                        audio_chunks[client] = [await buffer.get() for _ in range(self.max_buffer_size)]

                # broadcast the audio chunks to all clients in the room, including the muted clients
                mixed_chunk_with_self = self.mix_audio({k: v for k, v in audio_chunks.items()})
                for client in self.rooms[room_name]:
                    print(f'Client: {client.remote_address} received from', end=' ')
                    # mix the audio chunks except the client's own audio
                    mixed_chunk = self.mix_audio({k: v for k, v in audio_chunks.items() if k != client})

                    #if everyone else is muted, still receive empty chunk
                    if mixed_chunk is None:
                        mixed_chunk = b'\x00' * self.audio_chunk_size

                    await client.send(mixed_chunk+mixed_chunk_with_self)
            except Exception as e:
                print(f'error found: {e}', file=sys.stderr)

    def remove_client_from_mutelist(self, room_name: str, client: Socket):
        self.muted_clients[room_name].remove(client)
        # we need to ensure that the audio buffer is synchronized with others
        # the muted client's audio buffer is empty, but others are not
        # we need to fill the muted client's buffer with the same amount of audio chunks to keep them synchronized
        # we can simply zero pad the muted client's buffer
        if not all([buffer.qsize() == 0 for buffer in self.audio_buffers[room_name].values()]):
            # get the average number of audio chunks in the non-empty buffers
            avg_buffer_size = np.mean([buffer.qsize() for buffer in self.audio_buffers[room_name].values() if buffer.qsize() > 0])
            avg_buffer_size = int(round(avg_buffer_size))
            # fill the muted client's buffer with zeros
            for _ in range(avg_buffer_size):
                self.audio_buffers[room_name][client].put_nowait(b'\x00' * self.audio_chunk_size)

    def mix_audio(self, audio_chunks: Dict[Socket, List[bytes]]) -> Optional[bytes]:
        if len(audio_chunks) == 0:
            print(f'None')
            return None

        for client in audio_chunks.keys():
            print(f'{client.remote_address}', end=' ')
        print()

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

    def print_status(self):
        # print the rooms, the clients in each room, and their status
        for room_name, clients in self.rooms.items():
            print(f"Room: {room_name}")
            if len(clients) == 0:
                print("\tEmpty")
            else:
                for client in clients:
                    print(f'\tClient: {client.remote_address}', end='; ')
                    print(f'Audio buffer size: {self.audio_buffers[room_name][client].qsize()}', end='; ')
                    if client in self.muted_clients[room_name]:
                        print(' (muted)')
                    else:
                        print()

    async def run(self, host, port):
        async with websockets.serve(self.handler, host, port):
            print(f"Server started at ws://{host}:{port}")
            await asyncio.Future()  # run forever


if __name__ == "__main__":
    server = ChatServer(config)
    asyncio.run(server.run(config['ip'], config['port']))
