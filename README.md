# Operation running procedure

Step 1: Set the ip address and port in the config.py file to match the ip address and port of the server (tips: If you are running server.py and client.py on the same computer at the same time, you only need to change the ip address and port once in config.py, and server.py and client.py will read themselves)

Step 2: 
```bash
python server.py
```
Run the above command in terminal and you will see the corresponding server ip printed in terminal, which indicates that the server is open and waiting for the client to connect

Step 3:
```bash
python client.py
```
Run the above code on another computer or in the terminal of the same computer running the server, and you can see the visual client interface

# Client gui running procedure
In the client gui screen that displays, you can see the red "Disconnected" text at the top, which indicates your current connection status. Click the "List Chat Rooms" button and you can see the Rooms created by all users under this server. At this time, because it is the first time to open the server, no rooms are displayed after clicking the "List Chat Rooms" button.

Step 1: Click the Botton "Create Chat Room"
A window will pop up asking you to enter the number of the room you want to create. Click the "OK" button to create the room, and click the "Cancel" button to cancel the creation of the room. If the Room already exists, the corresponding window "Room + the room number you created + already exists" will pop up. If the Room you want to create does not exist, a pop-up window "Room + Room number you Created + Created" will pop up, and you can see the room you created in the list panel below.

Step 2: Click the Botton "List Chat Rooms"
Botton "List Chat Rooms" displays all chat rooms created on the same network as you. This list will help users identify and choose to join their favorite chat rooms.

Step 3: Choose Room Name 
In the "chat room list" select a Room Name that you want to join and click Select.

Step 4: Click the Botton "Connect to Selected Room"
You can see the audio and video data in server.py terminal and client.py terminal.  You can also see videos of yourself and other clients in the client gui. Now you can video chat happily with the people in your room!  At the same time, the status bar at the top will also display a green statement telling you the room number of the connection.

Step 5: Click the Botton "Mute"
You can chat in the room, click the "Mute" key to mute yourself, at this time other clients in the same room can not hear your voice, but can receive your video image.

Step 6: Click the Botton "Unmute"
After clicking the "Unmute" button, your voice message is sent to the server side, and other clients in the same room can hear your voice again.

Step 7: Start and save recording
Click "Start Recording" to start recording audio. Click "End recording" and the record will be saved to local file named last_recording.wav

Step 8: Click the Botton "Disconnect from Selected Room"
If you want to Disconnect from the current Room, you can simply click the "Disconnect from Selected Room" button. At this point, the Disconnected state at the top will also reappear in red, informing you that you have successfully exited the current room.

Step 9: Click the Botton "Delecte Selected Room"
Select the Room you want to delete and then click the "Delecte Selected Room" button. The current room will be deleted from all clients connected to the same server id. You will not be able to see the room in the "chat room list" and you can also recreate the room.
