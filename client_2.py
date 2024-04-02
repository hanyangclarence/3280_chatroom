import asyncio
import websockets
import pyaudio
import tkinter as tk
from tkinter import simpledialog
from threading import Thread

class AudioChatClientGUI:
    def __init__(self, uri):
        self.uri = uri
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.chunk_size = 1024
        self.pyaudio_instance = pyaudio.PyAudio()
        self.count = 0
        self.root = tk.Tk()
        self.root.title("Audio Chat Client")

        # Setup GUI
        self.setup_gui()

    def setup_gui(self):
        self.status_label = tk.Label(self.root, text="Disconnected", fg="red")
        self.status_label.pack(pady=10)

        self.connect_button = tk.Button(self.root, text="Connect to Chat Room", command=self.connect_to_room)
        self.connect_button.pack(pady=10)

    def connect_to_room(self):
        self.chat_room = simpledialog.askstring("Input", "Enter the chat room name:", parent=self.root)
        if self.chat_room:
            self.status_label.config(text="Connected to " + self.chat_room, fg="green")
            # Start the client in a non-blocking manner
            Thread(target=self.run_client, daemon=True).start()

    def run_client(self):
        asyncio.run(self.run())

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
                try:
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    await websocket.send(data)
                except IOError as e:
                    if e.errno == pyaudio.paInputOverflowed:
                        print("Input overflow, dropping frame.")
                        continue
                await asyncio.sleep(0)
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed during record and send process: {e}")

    async def receive_and_play(self, websocket, stream):
        try:
            while True:
                print(f'Receive: {self.count}')
                self.count += 1
                message = await websocket.recv()
                stream.write(message)
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed during receive and play process: {e}")

    async def run(self):
        record_stream, play_stream = None, None
        try:
            async with websockets.connect(self.uri) as websocket:
                await websocket.send(self.chat_room)  # Use the GUI-input chat room name
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

    def start_gui(self):
        self.root.mainloop()

if __name__ == "__main__":
    uri = "ws://10.13.181.168:5678"
    client = AudioChatClientGUI(uri)
    client.start_gui()