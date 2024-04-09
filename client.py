import asyncio
import websockets
import pyaudio
import tkinter as tk
from tkinter import simpledialog, messagebox
from threading import Thread
from config import config
import time
import numpy as np


class AudioChatClientGUI:
    def __init__(self, uri, config):
        self.uri = uri
        self.audio_format = pyaudio.paInt16
        self.channels = config["channel"]
        self.rate = config["rate"]
        self.chunk_size = config["chunk_size"]
        self.pyaudio_instance = pyaudio.PyAudio()
        self.chat_room = ""  # Keep track of the current room
        self.root = tk.Tk()
        self.root.title("Audio Chat Client")

        self.record_stream = None
        self.play_stream = None
        self.is_muted = False

        self._setup_gui()

    def _setup_gui(self):
        self.status_label = tk.Label(self.root, text="Disconnected", fg="red")
        self.status_label.pack(pady=10)

        self.create_room_button = tk.Button(self.root, text="Create Chat Room", command=self.create_room)
        self.create_room_button.pack(pady=10)

        self.list_rooms_button = tk.Button(self.root, text="List Chat Rooms", command=self.list_rooms)
        self.list_rooms_button.pack(pady=10)

        self.rooms_listbox = tk.Listbox(self.root)
        self.rooms_listbox.pack(pady=10)

        self.connect_button = tk.Button(self.root, text="Connect to Selected Room", command=self.connect_to_selected_room)
        self.connect_button.pack(pady=5)

        self.disconnect_button = tk.Button(self.root, text="Disconnect from Selected Room", command=self.disconnect_from_room)
        self.disconnect_button.pack(pady=5)

        self.delete_room_button = tk.Button(self.root, text="Delete Selected Room", command=self.delete_selected_room)
        self.delete_room_button.pack(pady=5)

        self.mute_button = tk.Button(self.root, text="Mute", command=self.toggle_mute)
        self.mute_button.pack(pady=5)

    def create_room(self):
        room_name = simpledialog.askstring("Input", "Enter the chat room name:", parent=self.root)
        if room_name:
            async def create_room_async():
                async with websockets.connect(self.uri) as websocket:
                    await websocket.send(f"CREATE {room_name}")
                    response = await websocket.recv()
                    messagebox.showinfo("Info", response)
            Thread(target=lambda: asyncio.run(create_room_async()), daemon=True).start()

    def list_rooms(self):
        async def list_rooms_async():
            async with websockets.connect(self.uri) as websocket:
                await websocket.send("LIST")
                rooms = await websocket.recv()
                self.rooms_listbox.delete(0, tk.END)
                for room in rooms.split(","):
                    if room:  # Ensure the room name is not empty
                        self.rooms_listbox.insert(tk.END, room)

        Thread(target=lambda: asyncio.run(list_rooms_async()), daemon=True).start()

    def toggle_mute(self):
        if self.is_muted:
            self.is_muted = False
            self.mute_button.config(text="Mute")
        else:
            self.is_muted = True
            self.mute_button.config(text="Unmute")

    def connect_to_selected_room(self):
        selection = self.rooms_listbox.curselection()
        if selection:
            self.chat_room = self.rooms_listbox.get(selection[0])
            self.status_label.config(text="Connected to " + self.chat_room, fg="green")
            Thread(target=self.run_client, daemon=True).start()
        else:
            messagebox.showerror("Error", "Please select a room first")
    
    def disconnect_from_room(self):
        async def disconnect_async():
            try:
                async with websockets.connect(self.uri) as websocket:
                    await websocket.send(f"LEAVE {self.chat_room}")
            except Exception as e:
                print(f"Error disconnecting from room: {e}")
            finally:
                self.root.after(0, self.cleanup_resources)

        Thread(target=lambda: asyncio.run(disconnect_async()), daemon=True).start()

    def cleanup_resources(self):
        if hasattr(self, 'record_stream') and self.record_stream is not None:
            self.record_stream.stop_stream()
            self.record_stream.close()
            self.record_stream = None
        
        if hasattr(self, 'play_stream') and self.play_stream is not None:
            self.play_stream.stop_stream()
            self.play_stream.close()
            self.play_stream = None
        self.pyaudio_instance.terminate()
        
        self.update_ui_after_disconnect()

    def update_ui_after_disconnect(self):
        print("Updating UI after disconnecting...")
        self.status_label.config(text="Disconnected", fg="red")
        self.chat_room = ""

    def delete_selected_room(self):
        selection = self.rooms_listbox.curselection()
        if selection:
            room_to_delete = self.rooms_listbox.get(selection[0])

            async def delete_room_async():
                async with websockets.connect(self.uri) as websocket:
                    await websocket.send(f"DELETE {room_to_delete}")
                    response = await websocket.recv()
                    messagebox.showinfo("Info", response)
                    self.list_rooms()  # Refresh the room list

            Thread(target=lambda: asyncio.run(delete_room_async()), daemon=True).start()
        else:
            messagebox.showerror("Error", "Please select a room first")

    def run_client(self):
        asyncio.run(self.run())

    def open_stream(self):
        self.pyaudio_instance = pyaudio.PyAudio()

        try:
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
        except OSError as e:
            messagebox.showerror("Error", f"Failed to open audio stream: {e}")
            return None, None

        return record_stream, play_stream

    async def record_and_send(self, websocket):
        try:
            while True:
                if not self.is_muted:
                    data = self.record_stream.read(self.chunk_size, exception_on_overflow=False)
                    await websocket.send(data)
                    await asyncio.sleep(0)
                else:
                    # sleep for the same duration as the recording interval to avoid busy waiting
                    time.sleep(self.chunk_size / self.rate)
                    mute_message = 'MUTE'
                    await websocket.send(mute_message)
                    await asyncio.sleep(0)
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed during record and send process: {e}")

    async def receive_and_play(self, websocket):
        try:
            while True:
                message = await websocket.recv()
                # run the stream.write in a separate thread to avoid blocking
                await asyncio.get_event_loop().run_in_executor(None, self.play_stream.write, message)
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed during receive and play process: {e}")

    async def run(self):
        try:
            async with websockets.connect(self.uri) as websocket:
                await websocket.send(self.chat_room)  # Use the GUI-input chat room name
                self.record_stream, self.play_stream = self.open_stream()
                send_task = asyncio.create_task(self.record_and_send(websocket))
                receive_task = asyncio.create_task(self.receive_and_play(websocket))
                await asyncio.gather(send_task, receive_task)
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed: {e}")
        finally:
            if self.record_stream:
                self.record_stream.stop_stream()
                self.record_stream.close()
            if self.play_stream:
                self.play_stream.stop_stream()
                self.play_stream.close()
            self.pyaudio_instance.terminate()

    def start_gui(self):
        self.root.mainloop()


if __name__ == "__main__":
    try:
        uri = f"ws://{config['ip']}:{config['port']}"
        client = AudioChatClientGUI(uri, config=config)
        client.start_gui()
    except Exception as e:
        print(f"Unhandled exception: {e}")