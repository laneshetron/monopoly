import time
import json
import sqlite3
import socket
from collections import deque

class ratelimit:
    def __init__(self, max, duration):
        self.max = max
        self.duration = duration # in milliseconds
        self.rateQueue = deque([0] * max, maxlen=max)

    def queue(self):
        if self.overflow:
            time.sleep((self.duration - self.elapsed / self.max) / 1000)
        self.rateQueue.append(int(time.time() * 1000))
        # TODO need to adapt this for the event loop so we can yield on delays

    def nonblocking_queue(self):
        if self.overflow:
            return False
        else:
            self.rateQueue.append(int(time.time() * 1000))
            return True

    @property
    def elapsed(self):
        return int(time.time() * 1000) - self.rateQueue[0]

    @property
    def overflow(self):
        return self.elapsed / self.max < self.duration

class global_ratelimiter:
    def __init__(self, max=20, duration=3600 * 1000):
        self.max = max
        self.duration = duration
        self.ratelimits = { 'global': ratelimit(self.max * 2, self.duration) }

    def queue(self, sender):
        if sender not in self.ratelimits:
            self.ratelimits[sender] = ratelimit(self.max, self.duration)
        return self.ratelimits[sender].nonblocking_queue()

class safesocket(socket.socket):
    def __init__(self, *args):
        self.floodQueue = ratelimit(10, 100)
        super().__init__(*args)

    def send(self, message, *args):
        try:
            if not isinstance(message, bytes):
                message = message.encode()
            # Start rate limiting after 10 messages within 100ms
            # to avoid IRC kicking us for flooding
            self.floodQueue.queue()
            super().send(message, *args)
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
