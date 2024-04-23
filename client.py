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
import ReadWrite
import os
import math
import aiofiles
import librosa


class AudioChatClientGUI:
    def __init__(self, uri, config):
        self.config = config
        self.uri = uri
        self.audio_format = pyaudio.paInt16
        self.channels = config["channel"]
        self.rate = config["rate"]
        self.chunk_size = config["chunk_size"]
        self.pyaudio_instance = pyaudio.PyAudio()
        self.chat_room = ""  # Keep track of the current room
        self.root = tk.Tk()
        self.root.title("Audio Chat Client")
        self.username = config["my_name"]

        self.websocket = None
        self.send_task = None
        self.receive_task = None
        self.send_video_task = None
        self.receive_video_task = None
        self.filename_count = 0

        self.record_stream = None
        self.play_stream = None
        self.is_muted = False
        self.is_recording = False

        self.audio = ReadWrite.Audio()
        self.audio.loadConfig(config["rate"], config["channel"], bytesPerSample=2)

        # set self.audio_chunk_size to the size of each audio chunk in bytes
        self.audio_chunk_size = config['chunk_size'] * config['channel'] * config['max_buffer_size'] * 2  # 2 bytes per sample

        self._setup_gui()

        # Initially hide the mute and save recording buttons
        self.mute_button.pack_forget()
        self.save_recording_button.pack_forget()

    def _setup_gui(self):
        self.root.geometry("640x720")

        controls_frame = tk.Frame(self.root)
        controls_frame.pack(side='left', fill='both', expand=True)

        video_frame = tk.Frame(self.root, width=200, height=150)
        video_frame.pack(side='right', fill='both', expand=True)

        self.status_label = tk.Label(controls_frame, text="Disconnected", fg="red")
        self.status_label.pack(pady=5)
        #self.status_label.place(x=100,y=10)

        self.create_room_button = tk.Button(controls_frame, text="Create Chat Room", command=self.create_room)
        self.create_room_button.pack(pady=5)
        #self.create_room_button.place(x=100,y=60)

        self.list_rooms_button = tk.Button(controls_frame, text="List Chat Rooms", command=self.list_rooms)
        self.list_rooms_button.pack(pady=5)
        #self.list_rooms_button.place(x=100,y=110)

        self.rooms_listbox = tk.Listbox(controls_frame)
        self.rooms_listbox.pack(pady=5)
        #self.rooms_listbox.pack(side='left',padx=100)
        #self.list_rooms_button.place(x=200,y=110)

        self.connect_button = tk.Button(controls_frame, text="Connect to Selected Room",
                                        command=self.connect_to_selected_room)
        self.connect_button.pack(pady=5)
        #self.connect_button.place(x=100,y=400)

        self.disconnect_button = tk.Button(controls_frame, text="Disconnect from Selected Room",
                                           command=self.disconnect_from_room)
        self.disconnect_button.pack(pady=5)
        #self.disconnect_button.place(x=100,y=450)

        self.delete_room_button = tk.Button(controls_frame, text="Delete Selected Room", command=self.delete_selected_room)
        self.delete_room_button.pack(pady=5)
        #self.delete_room_button.place(x=100,y=500)

        self.mute_button = tk.Button(controls_frame, text="Mute", command=self.toggle_mute)
        #self.mute_button.pack(pady=5)
        #self.mute_button.place(x=600,y=60)

        self.save_recording_button = tk.Button(controls_frame, text="Start Recording", command=self.save_recording)
        #self.save_recording_button.pack(pady=5)
        #self.save_recording_button.place(x=600,y=110)

        title_label_1 = tk.Label(controls_frame, text="Voice Change", font=("Arial", 12, "bold"))
        title_label_1.pack()

        self.n_steps = tk.Scale(controls_frame, from_=-10, to=10, orient=tk.HORIZONTAL, length=200, resolution=1.0)
        self.n_steps.pack()
        self.n_steps.set(0.0)

        self.video_frame = tk.Frame(video_frame, width=200, height=150)
        self.video_frame.pack(pady=10)

        self.client_video_labels = {}

        self.mylbl = tk.Label(self.video_frame)

        # Start video capture
        self.capture = cv2.VideoCapture(0)

    def show_control_buttons(self):
        # self.mute_button.place(x=500,y=60)
        # self.save_recording_button.place(x=500,y=110)
        self.mute_button.pack(pady=5)
        self.save_recording_button.pack(pady=5)

    def hide_control_buttons(self):
        self.mute_button.pack_forget()
        self.save_recording_button.pack_forget()

    def create_room(self):
        room_name = simpledialog.askstring("Input", "Enter the chat room name:", parent=self.root)
        if room_name:
            async def create_room_async():
                async with websockets.connect(self.uri) as websocket:
                    await websocket.send(f"CREATE {room_name}")
                    response = await websocket.recv()
                    messagebox.showinfo("Info", response)
                    self.list_rooms()

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
            self.show_control_buttons()
            Thread(target=self.run_client, daemon=True).start()
        else:
            messagebox.showerror("Error", "Please select a room first")

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

    def change_speed(self, speed, frames):
        arr = np.frombuffer(frames, dtype=np.int16)
        new_length = int(len(arr) / speed)
        new_arr = np.zeros(new_length, dtype=np.float64)
        win_size = 1024
        hs = win_size // 2
        ha = int(speed * hs)
        # calculate the Hann window
        hanning_window = [0] * win_size
        for i in range(win_size):
            hanning_window[i] = 0.5 - 0.5 * math.cos(2 * math.pi * i /(win_size - 1))
        old_pos = 0
        new_pos = 0
        delta = 0
        while old_pos + delta < len(arr) - win_size and new_pos < new_length - win_size:
            for i in range(win_size):
                new_arr[new_pos+i] += arr[old_pos+i] * hanning_window[i]
            # update new_pos and old_pos
            new_pos += hs
            old_pos += ha
        # new_arr = new_arr.astype(np.int16)
        return new_arr
        # tobytes = new_arr.tobytes()
        # return tobytes

    def pitch_interp(self,y, sr, n_steps):
        n = len(y)
        factor = 2 ** (1.0 * n_steps / 12.0)  # Frequency scaling factor
        y_shifted = np.interp(np.arange(0, n, factor), np.arange(n), y)
        return y_shifted
    def change_pitch(self, frames, n_steps):
        print("here1")
        y = self.change_speed(1/(2 ** (1.0 * n_steps / 12.0)), frames)
        sr = self.rate
        original_length = len(y.tobytes())
        print("length after changing speed",original_length)
        y_shifted = self.pitch_interp(y, sr, n_steps)

        # Convert back to int16
        y_shifted_int = y_shifted.astype(np.int16)

        # Splitting the shifted audio into frames
        bytes_arr = y_shifted_int.tobytes()
        print("length after pitch change",len(bytes_arr))
        return bytes_arr

    async def record_and_send(self, websocket):
        try:
            while True:
                if not self.is_muted:
                    # Get the running event loop
                    loop = asyncio.get_event_loop()
                    data = await loop.run_in_executor(None, self.record_stream.read, self.chunk_size, False)
                    # print("before:",len(data))
                    n_steps = self.n_steps.get()
                    if n_steps != 0:
                        # data = self.change_pitch(data,n_steps)
                        data_float32 = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                        data_float32 /= np.iinfo(np.int16).max
                        shifted_data = librosa.effects.pitch_shift(data_float32, sr=self.rate, n_steps=n_steps)
                        shifted_data_int16 = (shifted_data * np.iinfo(np.int16).max).astype(np.int16)
                        data = shifted_data_int16.tobytes()
                        # print("after:",len(data))
                    await websocket.send(data)
                else:
                    # sleep for the same duration as the recording interval to avoid busy waiting
                    await asyncio.sleep(self.chunk_size / self.rate)
                    mute_message = 'MUTE'
                    await websocket.send(mute_message)
                # Give the control back
                await asyncio.sleep(0)
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed during record and send process: {e}")


    async def receive_and_play(self, websocket):
        try:
            while True:
                # message is chunks_without_self + chunks_with_self
                message = await websocket.recv()
                if message[:4] == b'FILE':
                    file_path = os.path.join(os.getcwd(), "other's_recording_",str(self.filename_count),".wav")
                    async with aiofiles.open(file_path, "rb") as f:
                    # async with open(os.path.join(os.getcwd(), "other's_recording_",str(self.filename_count),".wav"), "wb") as f:
                        await f.write(message[5:])
                        self.filename_count += 1
                    continue
                chunks_with_self = message[:self.audio_chunk_size]
                chunks_without_self = message[self.audio_chunk_size:]
                #print(f'chunks_with_self: {len(chunks_with_self)}, chunks_without_self: {len(chunks_without_self)}')
                if self.is_recording==True:
                    self.audio.appendData(chunks_with_self, self.config["rate"], self.config["channel"], 2)
                if len(chunks_without_self) > 0:
                    # run the stream.write in a separate thread to avoid blocking
                    await asyncio.get_event_loop().run_in_executor(None, self.play_stream.write, chunks_without_self)
                else:
                    await asyncio.sleep(0)
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed during receive and play process: {e}")

    async def send_file(self):
        async with aiofiles.open(os.path.join(os.getcwd(), self.config["record_path"]), "rb") as f:
            content = await f.read()
            await self.websocket.send(b"FILE"+content)
    def save_recording(self):
        if self.is_recording == True:
            self.audio.write(os.path.join(os.getcwd(), self.config["record_path"]))
            asyncio.run(self.send_file())
            self.audio = ReadWrite.Audio()
            self.audio.loadConfig(config["rate"], config["channel"], bytesPerSample=2)
            print("saved")
            self.is_recording = False
            self.save_recording_button.config(text="Start Recording")
        else:
            self.is_recording = True
            self.save_recording_button.config(text="End Recording")

    async def receive_and_play_video(self, websocket):
        try:
            while True:
                #before_receive_time = time.time()
                message = await websocket.recv()
                #print("video received:", message[:10])
                #after_receive_time = time.time()
                client_id = message[1:5]
                if message[0] == b'X':
                    self.client_video_labels[client_id].pack_forget()
                    self.client_video_labels.pop(client_id)
                    continue
                frame = cv2.imdecode(np.frombuffer(message[5:], np.uint8), cv2.IMREAD_COLOR)

                # cv_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # pil_image = Image.fromarray(cv_image)
                # image_tk = ImageTk.PhotoImage(image=pil_image)
                # # cv2.imshow('Receiver', frame)
                # # 如果这是新的客户端，创建一个新的标签
                # if client_id not in self.client_video_labels:
                #     self.add_video_label(client_id)
                #
                # # 更新对应客户端的视频标签
                # label = self.client_video_labels[client_id]
                # label.imgtk = image_tk
                # label.configure(image=image_tk)
                # after_play_time = time.time()
                try:
                    self.root.after(0, self.update_client_video, client_id, frame)
                except Exception as e:
                    print("here2",e)
                # print(f'video:Receive: receive time: {after_receive_time - before_receive_time}, play time: {after_play_time - after_receive_time}')
                await asyncio.sleep(0)
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed during receive and play video process: {e}")

    def update_my_lbl(self, frame):
        cv_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(cv_image)
        image_tk = ImageTk.PhotoImage(image=pil_image)
        self.mylbl.imgtk = image_tk
        self.mylbl.configure(image=image_tk)
    def update_client_video(self, client_id, frame):
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

    def add_video_label(self, client_id):
        if client_id not in self.client_video_labels:
            # 创建一个Label来显示视频
            label = tk.Label(self.video_frame)
            label.pack(side="left", padx=10)
            self.client_video_labels[client_id] = label

    async def record_and_send_video(self, websocket):
        while self.capture.isOpened():
            #print("here111")
            before_read_time = time.time()
            loop = asyncio.get_running_loop()
            ret, frame = await loop.run_in_executor(None, self.capture.read)
            # ret, frame = self.capture.read()
            if not ret:
                break
            frame = cv2.resize(frame, (200, 150))
            # Here you would need to encode the frame using a codec like H.264
            _, buffer = cv2.imencode('.jpg', frame)
            after_read_time = time.time()
            bytes_buffer = buffer.tobytes()
            image_size = len(bytes_buffer)
            #print(image_size)
            await websocket.send(b"VIDEO" + bytes_buffer)
            # after_send_time = time.time()
            # frame_show = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            #
            # img = Image.fromarray(frame_show)
            #
            # imgtk = ImageTk.PhotoImage(image=img)
            #
            # self.mylbl.imgtk = imgtk
            # self.mylbl.configure(image=imgtk)
            try:
                self.root.after(0, self.update_my_lbl, frame)
            except Exception as e:
                print("here1",e)
            #print(
            #    f'video: read time: {after_read_time - before_read_time}, send time: {after_send_time - after_read_time}')
            # Mimic the delay of video encoding
            await asyncio.sleep(0.033)  # Roughly 30 frames per second

    async def run(self):
        try:
            async with websockets.connect(self.uri) as websocket:
                self.websocket = websocket
                await websocket.send(self.chat_room)  # Use the GUI-input chat room name
                if not self.capture.isOpened():
                    print("无法打开摄像头")
                    exit()
                self.record_stream, self.play_stream = self.open_stream()
                self.send_task = asyncio.create_task(self.record_and_send(websocket))
                self.receive_task = asyncio.create_task(self.receive_and_play(websocket))
                self.websocket2 = await websockets.connect(f"ws://{config['ip']}:5679")
                await self.websocket2.send(json.dumps({"room": self.chat_room, "user": self.username, "type": "video"}))
                self.send_video_task = asyncio.create_task(self.record_and_send_video(self.websocket2))
                self.mylbl.pack()
                self.receive_video_task = asyncio.create_task(self.receive_and_play_video(self.websocket2))
                try:
                    await asyncio.gather(self.send_task, self.receive_task, self.send_video_task,
                                     self.receive_video_task)
                except asyncio.CancelledError:
                    await self.websocket2.close()
                    self.websocket2 = None
                    print("Tasks are cancelled")
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed: {e}")
        # finally:
        #     await self.disconnect()

    async def disconnect(self):
        self.hide_control_buttons()
        if self.send_task is not None:
            self.send_task.cancel()
            self.send_task = None
        if self.receive_task is not None:
            self.receive_task.cancel()
            self.receive_task = None
        if self.send_video_task is not None:
            self.send_video_task.cancel()
            self.send_video_task = None
        if self.receive_video_task is not None:
            self.receive_video_task.cancel()
            self.receive_video_task = None
        if self.websocket is not None:
            # await self.websocket.close()
            self.websocket = None
        self.cleanup_resources()

    def cleanup_resources(self):
        if self.record_stream is not None:
            self.record_stream.stop_stream()
            self.record_stream.close()
            self.record_stream = None
        if self.play_stream is not None:
            self.play_stream.stop_stream()
            self.play_stream.close()
            self.play_stream = None
        if self.pyaudio_instance is not None:
            self.pyaudio_instance.terminate()
            self.pyaudio_instance = None
        self.update_ui_after_disconnect()

    def update_ui_after_disconnect(self):
        self.status_label.config(text="Disconnected", fg="red")
        self.chat_room = ""
        for label in self.client_video_labels.values():
            label.pack_forget()
        self.client_video_labels = {}
        self.mylbl.pack_forget()

    def disconnect_from_room(self):
        asyncio.run(self.disconnect())

    def start_gui(self):
        self.root.mainloop()


if __name__ == "__main__":
    try:
        uri = f"ws://{config['ip']}:{config['port']}"
        client = AudioChatClientGUI(uri, config=config)
        client.start_gui()
    except Exception as e:
        print(f"Unhandled exception: {e}")