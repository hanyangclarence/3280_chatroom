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

    def open_stream(self):
        record_stream = self.pyaudio_instance.open(
            format=self.audio_format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )
        play_stream = self.pyaudio_instance.open(
            format=self.audio_format,
            channels=self.channels,
            rate=self.rate,
            output=True,
            frames_per_buffer=self.chunk_size
        )
        return record_stream, play_stream

    async def record_and_send(self, websocket, stream):
        try:
            counter = 1
            while True:
                print(f'Send: {counter}')
                counter += 1
                data = stream.read(self.chunk_size)
                # Process and possibly compress your audio data here
                # await websocket.send(data)
                await websocket.send(data)
                await asyncio.sleep(0)
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed during record and send process: {e}")

    async def receive_and_play(self, websocket, stream):
        try:
            while True:
                print(f'Receive: {self.count}')
                self.count += 1
                # Decompress your audio data here if necessary
                message = await websocket.recv()
                stream.write(message)
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed during receive and play process: {e}")

    async def run(self):
        record_stream, play_stream = None, None
        try:
            async with websockets.connect(self.uri) as websocket:
                record_stream, play_stream = self.open_stream()
                send_task = asyncio.create_task(self.record_and_send(websocket, record_stream))
                receive_task = asyncio.create_task(self.receive_and_play(websocket, play_stream))
                await asyncio.gather(send_task, receive_task)
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed: {e}")
        finally:
            if record_stream:
                record_stream.stop_stream()
                record_stream.close()
            if play_stream:
                play_stream.stop_stream()
                play_stream.close()
            self.pyaudio_instance.terminate()


if __name__ == "__main__":
    # uri = "ws://10.13.25.124:5678"
    uri = "ws://10.13.245.139:5678"
    client = AudioChatClient(uri)
    asyncio.run(client.run())
