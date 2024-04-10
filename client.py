import asyncio
import websockets
import pyaudio
import tkinter as tk
from tkinter import simpledialog, messagebox
from threading import Thread
from config import config
import time
import numpy as np
import cv2
from PIL import Image, ImageTk
import json


class AudioChatClientGUI:
    def __init__(self, uri, config):
        self.uri = uri
        self.audio_format = pyaudio.paInt16
        self.channels = config["channel"]
        self.rate = config["rate"]
        self.chunk_size = config["chunk_size"]
        self.pyaudio_instance = pyaudio.PyAudio()
        self.chat_room = ""  # Keep track of the current room
        self.count = 0
        self.root = tk.Tk()
        self.root.title("Audio Chat Client")
        self.username = config["my_name"]

        self.setup_gui()

    def setup_gui(self):
        self.status_label = tk.Label(self.root, text="Disconnected", fg="red")
        self.status_label.pack(pady=10)

        self.create_room_button = tk.Button(self.root, text="Create Chat Room", command=self.create_room)
        self.create_room_button.pack(pady=10)

        self.list_rooms_button = tk.Button(self.root, text="List Chat Rooms", command=self.list_rooms)
        self.list_rooms_button.pack(pady=10)

        self.rooms_listbox = tk.Listbox(self.root)
        self.rooms_listbox.pack(pady=10)

        self.connect_button = tk.Button(self.root, text="Connect to Selected Room",
                                        command=self.connect_to_selected_room)
        self.connect_button.pack(pady=5)

        self.disconnect_button = tk.Button(self.root, text="Disconnect from Selected Room",
                                           command=self.disconnect_from_room)
        self.disconnect_button.pack(pady=5)

        self.delete_room_button = tk.Button(self.root, text="Delete Selected Room", command=self.delete_selected_room)
        self.delete_room_button.pack(pady=5)

        # Video frame
        self.video_frame = tk.Frame(self.root, width=200, height=150)
        self.video_frame.pack(pady=10)

        self.client_video_labels = {}

        self.mylbl = tk.Label(self.video_frame)
        self.mylbl.pack()

        # Start video capture
        self.capture = cv2.VideoCapture(0)

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
                self.send_task.cancel()
                self.receive_task.cancel()
                self.send_video_task.cancel()
                self.receive_video_task.cancel()
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
        for label in self.client_video_labels.values():
            label.pack_forget()
        self.client_video_labels = {}
        self.mylbl.pack_forget()
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
        print("here1")
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

    async def record_and_send(self, websocket, stream):
        try:
            counter = 1
            while True:
                counter += 1
                before_read_time = time.time()
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                after_read_time = time.time()
                await websocket.send(b"AUDIO" + data)
                after_send_time = time.time()
                print(f'data: {data[:6]}, read time: {after_read_time - before_read_time}, send time: {after_send_time - after_read_time}')
                await asyncio.sleep(0)
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed during record and send process: {e}")

    async def receive_and_play(self, websocket, stream):
        try:
            while True:
                self.count += 1
                before_receive_time = time.time()
                message = await websocket.recv()
                after_receive_time = time.time()
                await asyncio.get_event_loop().run_in_executor(None, stream.write, message)

                after_play_time = time.time()
                print(f'Receive: receive time: {after_receive_time - before_receive_time}, play time: {after_play_time - after_receive_time}')
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed during receive and play process: {e}")

    async def receive_and_play_video(self, websocket):
        try:
            while True:
                before_receive_time = time.time()
                message = await websocket.recv()
                after_receive_time = time.time()
                client_id = message[1:5]  # 前4个字节是客户端ID
                frame = cv2.imdecode(np.frombuffer(message[5:], np.uint8), cv2.IMREAD_COLOR)

                cv_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(cv_image)
                image_tk = ImageTk.PhotoImage(image=pil_image)
                # cv2.imshow('Receiver', frame)
                # 如果这是新的客户端，创建一个新的标签
                print("here",client_id)
                if client_id not in self.client_video_labels:
                    self.add_video_label(client_id)

                # 更新对应客户端的视频标签
                label = self.client_video_labels[client_id]
                label.imgtk = image_tk
                label.configure(image=image_tk)
                after_play_time = time.time()

                # self.root.after(0,self.update_client_video,client_id,frame)
                # print(f'video:Receive: receive time: {after_receive_time - before_receive_time}, play time: {after_play_time - after_receive_time}')
                # await asyncio.sleep(0.01)
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed during receive and play video process: {e}")
    def update_client_video(self,client_id,frame):
        cv_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(cv_image)
        image_tk = ImageTk.PhotoImage(image=pil_image)
        # cv2.imshow('Receiver', frame)
        # 如果这是新的客户端，创建一个新的标签
        if client_id not in self.client_video_labels:
            self.add_video_label(client_id)

        # 更新对应客户端的视频标签
        label = self.client_video_labels[client_id]
        label.imgtk = image_tk
        label.configure(image=image_tk)
    async def record_and_send_video(self, websocket):
        while self.capture.isOpened():
            print("here111")
            before_read_time = time.time()
            ret, frame = self.capture.read()
            if not ret:
                break
            frame = cv2.resize(frame, (200, 150))
            # Here you would need to encode the frame using a codec like H.264
            _, buffer = cv2.imencode('.jpg', frame)
            after_read_time = time.time()
            await websocket.send(b"VIDEO" + buffer.tobytes())
            after_send_time = time.time()
            frame_show = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            img = Image.fromarray(frame_show)

            imgtk = ImageTk.PhotoImage(image=img)

            self.mylbl.imgtk = imgtk
            self.mylbl.configure(image=imgtk)
            print(f'video: read time: {after_read_time - before_read_time}, send time: {after_send_time - after_read_time}')
            # Mimic the delay of video encoding
            await asyncio.sleep(0.033)  # Roughly 30 frames per second

    def add_video_label(self, client_id):
        if client_id not in self.client_video_labels:
            # 创建一个Label来显示视频
            label = tk.Label(self.video_frame)
            label.pack(side="left", padx=10)
            self.client_video_labels[client_id] = label


    async def run(self):
        print("here2")
        try:
            async with websockets.connect(self.uri) as websocket:
                await websocket.send(json.dumps({"room": self.chat_room, "user": self.username,
                                                 "type": "audio"}))  # Use the GUI-input chat room name
                record_stream, play_stream = self.open_stream()
                if not self.capture.isOpened():
                    print("无法打开摄像头")
                    exit()
                self.send_task = asyncio.create_task(self.record_and_send(websocket, record_stream))
                self.receive_task = asyncio.create_task(self.receive_and_play(websocket, play_stream))
                websocket2 = await websockets.connect(f"ws://{config['ip']}:5679")
                await websocket2.send(json.dumps({"room": self.chat_room, "user": self.username, "type": "video"}))
                self.send_video_task = asyncio.create_task(self.record_and_send_video(websocket2))
                self.receive_video_task = asyncio.create_task(self.receive_and_play_video(websocket2))
                try:
                    await asyncio.gather(self.send_task, self.receive_task, self.send_video_task,
                                         self.receive_video_task)
                except asyncio.CancelledError:
                    print("Tasks cancelled")
                    await websocket.send(f"LEAVE {self.chat_room}")
                    await websocket2.send(f"LEAVE {self.chat_room}")
                    # await websocket.send("exit")
                    self.receive_task = None
                    self.send_task = None
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed: {e}")

    def start_gui(self):
        self.root.mainloop()


if __name__ == "__main__":
    try:
        uri = f"ws://{config['ip']}:{config['port']}"
        client = AudioChatClientGUI(uri, config=config)
        client.start_gui()
    except Exception as e:
        print(f"Unhandled exception: {e}")
