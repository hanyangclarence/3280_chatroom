import sys
import asyncio
import websockets
import pyaudio
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QWidget, QInputDialog
from PyQt5.QtCore import pyqtSlot
from config import config
import time
import numpy as np
import qasync

class AudioChatClientGUI(QMainWindow):
    def __init__(self, uri, config):
        super().__init__()
        self.uri = uri
        self.audio_format = pyaudio.paInt16
        self.channels = config["channel"]
        self.rate = config["rate"]
        self.chunk_size = config["chunk_size"]
        self.pyaudio_instance = pyaudio.PyAudio()
        self.count = 0
        self.websocket = None  # Initialize websocket attribute
        self.is_in_room = False
        self.is_running = True

        # Setup GUI
        self.setWindowTitle("Audio Chat Client")
        self.setup_gui()

        self.loop = qasync.QEventLoop(app)  # Use qasync's QEventLoop
        asyncio.set_event_loop(self.loop)


    def setup_gui(self):
        self.status_label = QLabel("Disconnected", self)
        self.status_label.setStyleSheet("color: red")

        self.connect_button = QPushButton("Connect to Chat Room", self)
        self.connect_button.clicked.connect(self.connect_to_room)

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(self.connect_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def closeEvent(self, event):
        self.is_running = False
        asyncio.ensure_future(self.stop_chat())
        self.pyaudio_instance.terminate()
        self.connect_task.cancel()
        self.run_task.cancel()
        loop = asyncio.get_event_loop()
        loop.stop()
        event.accept()

    @qasync.asyncSlot()
    async def connect_to_room(self):
        chat_room, ok = QInputDialog.getText(self, "Input", "Enter the chat room name:")
        if ok and chat_room:
            self.status_label.setText(f"Connected to {chat_room}")
            self.status_label.setStyleSheet("color: green")
            self.connect_button.setText("Exit Chat Room")
            self.connect_button.clicked.disconnect()
            self.connect_button.clicked.connect(self.exit_chat_room)
            self.is_in_room = True
            self.run_task = asyncio.ensure_future(self.run(chat_room))

    @qasync.asyncSlot()
    async def exit_chat_room(self):
        print("here2")
        await self.stop_chat()
    async def stop_chat(self):
        print("here3")
        self.is_in_room = False
        if self.send_task:
            self.send_task.cancel()
        if self.receive_task:
            self.receive_task.cancel()
        self.connect_button.setText("Connect to Chat Room")
        self.connect_button.clicked.disconnect()
        self.connect_button.clicked.connect(self.connect_to_room)
        self.status_label.setText("Disconnected")
        self.status_label.setStyleSheet("color: red")
    def open_stream(self):
        self.record_stream = self.pyaudio_instance.open(
            format=self.audio_format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )
        self.play_stream = self.pyaudio_instance.open(
            format=self.audio_format,
            channels=self.channels,
            rate=self.rate,
            output=True,
            frames_per_buffer=self.chunk_size
        )
        return self.record_stream, self.play_stream

    async def record_and_send(self, websocket, stream):
        try:
            counter = 1
            while self.is_in_room:
                counter += 1
                before_read_time = time.time()
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                after_read_time = time.time()
                await websocket.send(data)
                after_send_time = time.time()
                print(f'data: {data[:6]}, read time: {after_read_time - before_read_time}, send time: {after_send_time - after_read_time}')
                await asyncio.sleep(0)
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed during record and send process: {e}")
        print("here7")

    async def receive_and_play(self, websocket, stream):
        try:
            while self.is_in_room:
                self.count += 1
                before_receive_time = time.time()
                message = await websocket.recv()
                after_receive_time = time.time()

                # run the stream.write in a separate thread to avoid blocking
                await asyncio.get_event_loop().run_in_executor(None, stream.write, message)

                after_play_time = time.time()
                print(f'Receive: receive time: {after_receive_time - before_receive_time}, play time: {after_play_time - after_receive_time}')
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed during receive and play process: {e}")
        print("here8")

    async def run(self, chat_room):
        print("here4")
        record_stream, play_stream = None, None
        try:
            async with websockets.connect(self.uri) as websocket:
                print("here5",websocket)
                await websocket.send(chat_room)  # Use the locally-input chat room name
                record_stream, play_stream = self.open_stream()
                self.send_task = asyncio.create_task(self.record_and_send(websocket, record_stream))
                self.receive_task = asyncio.create_task(self.receive_and_play(websocket, play_stream))
                try:
                    await asyncio.gather(self.send_task, self.receive_task)
                except asyncio.CancelledError:
                    print("Tasks cancelled")
                    await websocket.send("exit")
                    self.receive_task = None
                    self.send_task = None
                print("here6")
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed: {e}")
        finally:
            if record_stream:
                record_stream.stop_stream()
                record_stream.close()
            if play_stream:
                play_stream.stop_stream()
                play_stream.close()


    def start(self):
        self.show()
        self. connect_task = asyncio.ensure_future(self.connect_to_room())  # Schedule connect_to_room coroutine
        self.loop.run_forever()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    client = AudioChatClientGUI(uri=f"ws://{config['ip']}:{config['port']}", config=config)
    client.start()
    sys.exit(app.exec_())