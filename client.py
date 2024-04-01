import asyncio
import websockets
import pyaudio
import numpy as np


class AudioChatClient:
    def __init__(self, uri):
        self.uri = uri
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.chunk_size = 1024
        self.pyaudio_instance = pyaudio.PyAudio()
        self.count = 0

    def open_stream(self, record=True, play=True):
        stream = self.pyaudio_instance.open(
            format=self.audio_format,
            channels=self.channels,
            rate=self.rate,
            input=record,
            output=play,
            frames_per_buffer=self.chunk_size
        )
        return stream

    async def record_and_send(self, websocket, stream):
        counter = 1
        while True:
            print(f'Send: {counter}')
            counter += 1
            data = stream.read(self.chunk_size)
            # Process and possibly compress your audio data here
            # await websocket.send(data)
            await websocket.send(data)
            await asyncio.sleep(0)

    async def receive_and_play(self, websocket, stream):
        while True:
            print(f'Receive: {self.count}')
            self.count += 1
            # Decompress your audio data here if necessary
            message = await websocket.recv()
            stream.write(message)

    async def run(self):
        async with websockets.connect(self.uri) as websocket:
            stream = self.open_stream()
            send_task = asyncio.create_task(self.record_and_send(websocket, stream))
            receive_task = asyncio.create_task(self.receive_and_play(websocket, stream))
            await asyncio.gather(send_task, receive_task)


if __name__ == "__main__":
    # uri = "ws://10.13.25.124:5678"
    uri = "ws://localhost:5678"
    client = AudioChatClient(uri)
    asyncio.run(client.run())
