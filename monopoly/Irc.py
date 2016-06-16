import socket
import errno
import time
import random
from copy import copy
from Bank import Channel, g
from Bank.Trumpisms import Trumpisms

server = g.config['irc']['server']
port = g.config['irc']['port']
nick = g.config['irc']['bot']['nick']
backup_nicks = g.config['irc']['bot']['backup_nicks']
version = g.config['irc']['bot']['version']
pswd = g.config['irc']['bot']['password']
channelList = g.channels + g.silent_channels
channels = {}
readbuffer = ""
recheckTimer = 0

def set_nick(nick):
    print("NICK {0}\r\n".format(nick))
    ircsock.send("NICK {0}\r\n".format(nick))

def ping(response):
    ircsock.send("PONG :{0}\r\n".format(response))

def version(nick):
    print("NOTICE %s : VERSION monopoly %s\r\n" % (nick, version))
    ircsock.send("NOTICE {0} : VERSION monopoly {1}\r\n".format(nick, version))

def reset():
    if not Channel.reset():
        return
    try:
        reload(Channel)
        for key, chnl in channels.items():
            newObj = Channel.Empty()
            newObj.__class__ = Channel.Channel
            newObj.__dict__ = copy(chnl.__dict__)
            channels[key] = newObj
    except Exception as e:
        print(e)

def connect():
    up = False

    while not up:
        try:
            global ircsock
            g.uptime.update()
            ircsock = g.safesocket(socket.AF_INET, socket.SOCK_STREAM)
            ircsock.settimeout(5)
            ircsock.connect((server, port))
            ircsock.settimeout(None)
            print("PASS %s\r\n" % pswd)
            ircsock.send(("PASS %s\r\n" % pswd))
            set_nick(nick)
            readbuffer = ""
            ircsock.send("USER {0} {0} {1} :{2}\r\n".format(
                nick, server, g.config['irc']['bot']['fullname']))
            g.ircsock = ircsock
            up = True
        except socket.timeout:
            print("Connection timed out. Retrying in 1 second...")
            time.sleep(1)
        except socket.error as e:
            if e.errno == errno.ECONNREFUSED:
                print("Connection error: " + str(e))
                print("Retrying in 1 second...")
                time.sleep(1)
            else:
                raise e

def main(uptime, queues, **kwargs):
    g.uptime = uptime
    swift = queues['hangouts']
    donald = Trumpisms()

    connect()
    while True:
        try:
            data = ircsock.recv(2048).decode(errors='replace')
            data = data.strip('\r\n')
        except socket.error as e:
            print("Exception encountered: ", e)
            connect()
            continue

        if len(data) == 0:
            print("Socket disconnected.\nRetrying connection...")
            connect()
            continue

        for msg in data.splitlines():
            print(msg)

            if msg.find(":Welcome to the Arbor IRC") != -1:
                sub = msg.find(":Welcome to the Arbor IRC")
                global channels
                for chnlName in channelList:
                    channels[chnlName] = Channel.Channel(chnlName, donald, swift)
                channels[nick] = Channel.Channel(nick, donald, None, True)

            if msg.find("PING :") != -1:
                sub = msg.find('PING :')
                ping(msg[sub + 6:])

            if msg.find("VERSION") != -1:
                sub = msg.find("!nospoof")
                version(msg[1:sub])

            # Check for primary nick availability periodically
            if g.nick != nick and int(time.time()) - recheckTimer > 30:
                set_nick(nick)
                recheckTimer = int(time.time())

            # Direct message to the corresponding channel object
            # TODO this definitely needs to be cleaned up
            parts = msg.rsplit()
            if len(parts) > 2:
                if parts[1] == '433' and parts[2] == '*':
                    # Nick is taken
                    backup = random.choice(backup_nicks)
                    set_nick(backup)
                    g.nick = backup
                    recheckTimer = int(time.time())

                chnlName = parts[2].strip(':')
                if len(parts) > 4 and parts[4] in channels:
                    channels[parts[4]].listen(msg)
                elif chnlName in channels:
                    channels[chnlName].listen(msg)
                elif chnlName == g.nick:
                    channels[nick].listen(msg)

                sender = parts[0]
                sender = sender[1:sender.find("!")]
                if parts[1] == 'NICK' and sender == g.nick:
                    g.nick = nick

                if parts[1] == "PRIVMSG":
                    privmsg = ' '.join(parts[2:])
                    if privmsg.find("!reload") != -1:
                        if sender == "lshetron":
                            reset()
                        else:
                            ircsock.send("PRIVMSG {0} :{1}\r\n".format(chnlName,
                                         "This command is whitelisted."))
