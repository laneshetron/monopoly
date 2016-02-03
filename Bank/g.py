import time
import json
import sqlite3
import socket
from collections import deque

class safesocket(socket.socket):
    def __init__(self, *args):
        self.floodQueue = deque([0] * 10, maxlen=10)
        super().__init__(*args)

    def send(self, message, *args):
        try:
            elapsed = int(time.time()) - self.floodQueue[0]
            if not isinstance(message, bytes):
                message = message.encode()
            if elapsed / 10 < 100:
                # Start rate limiting after 10 messages within 100ms
                # to avoid IRC kicking us for flooding
                time.sleep((100 - elapsed / 10) / 1000)
            super().send(message, *args)
            self.floodQueue.append(int(time.time()))
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
