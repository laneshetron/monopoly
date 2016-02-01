import time
import json
import sqlite3
import socket

class safesocket(socket.socket):
    def send(self, *args):
        try:
            super().send(*args)
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
