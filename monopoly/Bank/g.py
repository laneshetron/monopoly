import os
import time
import json
import sqlite3
import socket
from collections import deque
from multiprocessing import Value

class ratelimit:
    # This seems simple, but is very important!
    # For messages within range: max * duration
    # For average message rate: duration
    def __init__(self, max, duration):
        self.max = max
        self.duration = duration # in milliseconds
        self.dropped_messages = 0
        self.rateQueue = deque([0] * max, maxlen=max)

    def queue(self):
        if self.overflow:
            time.sleep((self.duration - self.elapsed / self.max) / 1000)
        self.rateQueue.append(int(time.time() * 1000))
        # TODO need to adapt this for the event loop so we can yield on delays

    def nonblocking_queue(self):
        if self.overflow:
            self.dropped_messages += 1
            return False
        else:
            self.dropped_messages = 0
            self.rateQueue.append(int(time.time() * 1000))
            return True

    @property
    def elapsed(self):
        return int(time.time() * 1000) - self.rateQueue[0]

    @property
    def overflow(self):
        return self.elapsed / self.max < self.duration

class ratelimiter:
    def __init__(self, max=20, duration=180 * 1000):
        self.max = max
        self.duration = duration
        self.ratelimits = { 'global': ratelimit(self.max, self.duration) }

    def queue(self, key):
        if key not in self.ratelimits:
            self.ratelimits[key] = ratelimit(self.max, self.duration)
        return self.ratelimits[key].nonblocking_queue()

    def dropped(self, key):
        if key in self.ratelimits:
            return self.ratelimits[key].dropped_messages
        return 0

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

class Uptime:
    def __init__(self):
        self._startTime = Value('L', int(time.time()))
        self._lastDisconnect = Value('L', int(time.time()))

    # This is thread-safe
    def update(self):
        self._lastDisconnect.value = int(time.time())

    @property
    def startTime(self):
        return self._startTime.value

    @property
    def lastDisconnect(self):
        return self._lastDisconnect.value

    @property
    def elapsed(self):
        return int(time.time()) - self.startTime

    @property
    def elapsedDisconnect(self):
        return int(time.time()) - self.lastDisconnect

_g_root = os.path.dirname(os.path.realpath(__file__))

# TODO May want to look into using the resources module for this stuff
with open(os.path.join(_g_root, '../config/config.json')) as config_file:
    config = json.load(config_file)

with open(os.path.join(_g_root, '../data/nltk/english')) as f:
    stopwords = f.read().splitlines()

channels = config['irc']['channels']
silent_channels = config['irc']['silent_channels']
nick = config['irc']['bot']['nick']

db = sqlite3.connect(config['db']['location'])
cursor = db.cursor()

# These must be initialized by each process
ircsock = None
uptime = None
queues = {}
#
