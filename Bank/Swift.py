# Swift Message & Alert System
#
# Opens and accepts messages over a socket
# and from stdin for irc channel alerts

import asyncio
import sqlite3
import socket
import sys
import re
from hangups import ChatMessageSegment
from Bank.Hangouts import name_to_nick
from Bank import g

def is_an_alert(message):
    result = re.match("^\[(\S+)\] \((\S+)!(\S+)@([0-9a-zA-Z.:-]+)\) (.*)", message)
    if result:
        return result.groups()

def timeout(future, sock, address):
    if future.cancel():
        sock.close()
        print('Swift: client connection {0} timed out.'.format(address))

class Subscribers(list):

    def __init__(self, *args):
        list.__init__(self, *args)

    @property
    def first_name(self):
        return [(name.split()[0], id) for name, id in self]

    @property
    def nick(self):
        return [((name.split()[0][0] + name.split()[1]).lower(), id)
                for name, id in self]

class Swift:

    def __init__(self, client, conv_list):
        self.loop = asyncio.get_event_loop()
        self.host = socket.gethostname()
        self.port = g.config['notifications']['port']
        self.h_client = client
        self.h_conv_list = conv_list
        self.db = g.db
        self.cursor = g.cursor

        # Load subscriber list on initialization
        self.cursor.execute("SELECT name, conv_id FROM subscribers")
        self.subscribers = Subscribers(self.cursor.fetchall())

        asyncio.async(self.open_swift())
        self.loop.add_reader(sys.stdin, self.read_stdin)

    @asyncio.coroutine
    def open_swift(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setblocking(0)
            sock.bind((self.host, self.port))
            sock.listen(5)
            print('Swift bound on port {0}'.format(self.port))
            yield from self.accept_swift(sock)
        except Exception as e:
            print('Swift: ', e)
            raise e
        finally:
            sock.close()

    @asyncio.coroutine
    def accept_swift(self, sock):
        try:
            futures = {}
            timers = {}
            while True:
                (client, address) = yield from self.loop.sock_accept(sock)
                address = ":".join(str(part) for part in address)
                #futures[address] = asyncio.async(self.read_client(client, address))
                #timers[address] = asyncio.async(asyncio.sleep(10))
                #timers[address].add_done_callback(lambda x: timeout(futures[address], client, address))
                future = asyncio.async(self.read_client(client, address))
                print('Swift client connected from: ', address)
            return future
        except Exception as e:
            print('Swift: ', e)
            raise e

    @asyncio.coroutine
    def read_client(self, client, address):
        try:
            while True:
                data = yield from self.loop.sock_recv(client, 2048)
                if data:
                    data = data.decode().strip()
                    for message in data.splitlines():
                        print("Swift received from {0}: {1}".format(address, message))
                        alert = is_an_alert(message)
                        if alert:
                            (recipient, nick, uname, domain, msg) = alert
                            for subscriber, conv_id in self.subscribers.nick:
                                if recipient == subscriber:
                                    yield from self.notify('Private message from <b>{0}</b>:\n"{1}"'
                                        .format(nick, msg), conv_id)
                                    print('Swift forwarded message to {0}.'.format(recipient))
                else:
                    client.close()
                    print('Swift: remote client {0} closed connection.'.format(address))
                    break
        except Exception as e:
            print('Swift: ', e)
            raise e

    @asyncio.coroutine
    def notify(self, message, conv_id):
        segment = ChatMessageSegment.from_str(message)
        conv = self.h_conv_list.get(conv_id)
        asyncio.async(conv.send_message(segment, image_file=None))

    # Listen on stdin for irc alerts
    def read_stdin(self):
        message = sys.stdin.readline()
        if len(message) == 0:
            print('IRC is kill. Closing read from stdin.')
            self.loop.remove_reader(sys.stdin)
            return
        message = message.strip()
        print("Swift received from stdin: ", message)
        sender, channel, *parts = message.split()
        message = " ".join(parts).strip(":")

        for subscriber, conv_id in self.subscribers:
            re_mentions = re.compile('{0}|{1}'.format(subscriber.split()[0],
                                     name_to_nick(subscriber)), re.IGNORECASE)
            if re.search(re_mentions, message) and sender != name_to_nick(subscriber):
                highlighted = re.sub(re_mentions, lambda x: '<b>' + x.group(0) + '</b>', message)
                asyncio.async(self.notify('<b>{0}</b> mentioned you on IRC in <i>{1}</i>:\n"{2}"'
                    .format(sender, channel, highlighted), conv_id))
                print("Forwarded IRC mention to {0}".format(subscriber))
