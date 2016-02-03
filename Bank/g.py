import time
import json
import sqlite3
import socket

class safesocket(socket.socket):
    def __init__(self, *args):
        self.lastSend = 0
        super().__init__(*args)

    def send(self, message, *args):
        try:
            elapsed = int(time.time()) - self.lastSend
            if not isinstance(message, bytes):
                message = message.encode()
            if elapsed < 100:
                # Sleep between messages to avoid IRC kicking us for flooding
                time.sleep((100 - elapsed) / 1000)
            super().send(message, *args)
            self.lastSend = int(time.time())
        except Exception as e:
            print('Could not write to socket: ', e)

starttime = int(time.time())
lastDisconnect = 0

with open('config/config.json') as config_file:
    config = json.load(config_file)

channels = config['irc']['channels']
silent_channels = config['irc']['silent_channels']

db = sqlite3.connect(config['db']['location'])
cursor = db.cursor()
ircsock = None
