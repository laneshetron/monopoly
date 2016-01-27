# -*- coding: utf-8 -*-

from datetime import timedelta
import time
import urllib.request
import asyncio
import random
import re
from hangups import (ChatMessageSegment, hangouts_pb2)
from Bank import g

jakeisms = [
    "That guy died of ebola, I don't CARE anymore.",
    "pop pop click *exasperated sigh*",
    "You're still using the default terminal? I use iTerm.",
    "Whenever I spend the entire day looking at my external monitor and then go to use just my laptop my whole brain goes into a pretzel.",
    "I'm all about the funny",
    "It's a slippery slope: one day you're generating api tokens, the next you're torrenting Final Cut Pro.",
    "I've got a little grease lake going here. And I shall name you: Grease Lake!",
    "These German BMW makers are torturing asses." ]
blacklist = [ "HAL" ]
whitelist = [ "lshetron" ]

CONVERSATION_TYPE_ONE_TO_ONE = 1
CONVERSATION_TYPE_GROUP = 2

CONVERSATION_STATUS_ACTIVE = 2

def parentheses(msg):
    sub = msg.find("(")
    if sub == -1:
        return
    else:
        part = msg[sub:].strip('`~!@#$%^&*()+={}[]\'\":;?/\\|.>,<')
        part = ' '.join(part.split())
        return part

def name_to_nick(name):
    try:
        return (name.split()[0][0] + name.split()[1]).lower()
    except:
        return None

class Bank:
    def __init__(self, client, conv_list, swift):
        self.client = client
        self.conv_list = conv_list
        self.db = g.db
        self.cursor = g.cursor
        self.swift = swift
        self.messageBuffer = []

    def message(self, msg, fname=None):
        self.messageBuffer.append([msg, fname])

    def modify(self, amount, nick):
        self.cursor.execute("SELECT * FROM monopoly WHERE nick = ? COLLATE NOCASE LIMIT 1", (nick,))
        data = self.cursor.fetchall()
        if len(data) > 0:
            karma = data[0][2] + amount
            nick = data[0][1]
            id = data[0][0]
            self.cursor.execute("UPDATE monopoly SET karma = ? WHERE id = ?",
                            (karma, id))
            self.db.commit()
        else:
            self.cursor.execute("INSERT INTO monopoly(nick, karma) VALUES(?, ?)", (nick, amount))
            self.db.commit()
            karma = amount

        if amount == 1:
            self.message("Gave karma to {0}  Total: {1}".format(nick, karma))
        elif amount == -1:
            self.message(":( {0}  Total: {1}".format(nick, karma))
        else:
            self.message("{0} karma to {1}  Total: {2}".format(amount, nick, karma))

    def punish(self, nick):
        self.cursor.execute("SELECT * FROM monopoly WHERE nick = ? COLLATE NOCASE LIMIT 1", (nick,))
        data = self.cursor.fetchall()
        if len(data) > 0:
            karma = data[0][2] - 3
            nick = data[0][1]
            id = data[0][0]
            self.cursor.execute("UPDATE monopoly SET karma = ? WHERE id = ?",
                            (karma, id))
            self.db.commit()
        else:
            self.cursor.execute("INSERT INTO monopoly(nick, karma) VALUES(?, -3)", (nick,))
            self.db.commit()
            karma = -3

        self.message("Punished {0}!! >:(  Total: {1}".format(nick, karma))

    def karma(self, clients, nick=None, all=False):
        limit = ""
        print(clients)
        if nick is not None:
            limit = "WHERE nick = '%s' COLLATE NOCASE LIMIT 1" % nick
            self.message("Monopoly karma total for {0}:".format(nick))
        elif all:
            # do not set WHERE statement
            limit = ""
            self.message("Global Monopoly karma totals:")
        else:
            if len(clients) > 0:
                self.message("Monopoly karma totals for Hangouts:")
                limit = "WHERE "
                for uname in clients:
                    limit += "nick = '%s'" % uname
                    if uname != clients[-1]:
                        limit += " OR "
                limit += " ORDER BY karma DESC"
        print("SELECT * FROM monopoly {0}".format(limit))
        self.cursor.execute("SELECT * FROM monopoly {0}".format(limit))
        data = self.cursor.fetchall()
        for row in data:
            self.message("{0}: {1}".format(row[1], row[2]))

    def jakeism(self):
        quote = random.choice(jakeisms)
        self.message(quote)

    def subscribe(self, name, conv_id, private=False):
        try:
            self.cursor.execute("INSERT INTO subscribers(name, conv_id) VALUES(?, ?)", (name, conv_id))
            self.db.commit()
            self.swift.subscribers.append((name, conv_id))
            if not private:
                self.message("<b>{0}</b> has been subscribed to receive alerts.".format(name))
            print("{0} has subscribed to Swift.".format(name))
        except Exception as e:
            print("Exception encountered while adding subscription: ", e)

    def unsubscribe(self, name, conv_id):
        try:
            self.cursor.execute("DELETE FROM subscribers WHERE name = ?", (name,))
            self.db.commit()
            self.swift.subscribers.remove((name, conv_id))
            self.message('<i>You have been unsubscribed. ' +
                         'You will no longer receive alerts from monopoly.</i>')
            print("{0} has been unsubscribed from Swift.".format(name))
        except Exception as e:
            print("Exception encountered while removing subscription: ", e)

    @asyncio.coroutine
    def receive(self, msg, conv, user):
        clients = []
        for userObject in conv.users:
            nick = (userObject.first_name[0] + userObject.full_name.split()[1]).lower()
            clients.append(nick)

        sender = (user.first_name[0] + user.full_name.split()[1]).lower()

        increments = re.findall("(?:^|\s)([a-zA-Z_]+)\+\+( [0-9]+)?", msg) + re.findall("\(([a-zA-Z ]+)\)\+\+( [0-9]+)?", msg) # parens
        decrements = re.findall("(?:^|\s)([a-zA-Z_]+)--( [0-9]+)?(?!\S)", msg) + re.findall("\(([a-zA-Z ]+)\)--( [0-9]+)?", msg) # parens

        for group in increments:
            _nick = group[0].replace("_", " ")
            _nick = ' '.join(_nick.split()) # Reduces whitespaces and strips trailing
            if len(group[1]) > 0:
                delta = abs(int(group[1]))
            else:
                delta = None

            if delta is not None and sender in whitelist:
                self.modify(delta, _nick)
            else:
                if _nick.lower() != sender:
                    self.modify(1, _nick)
                else:
                    self.punish(sender)

        for group in decrements:
            _nick = group[0].replace("_", " ")
            _nick = ' '.join(_nick.split())
            if len(group[1]) > 0:
                delta = abs(int(group[1])) * -1
            else:
                delta = None

            if delta is not None and sender in whitelist:
                self.modify(delta, _nick)
            else:
                if sender in blacklist:
                    self.modify(-1, sender)
                    self.message("You've lost your downvoting privileges, {0}.".format(sender))
                else:
                    self.modify(-1, _nick)

        imageLinks = re.findall("((?:https?:\/\/)?(?:[\da-z\.-]+)\.(?:[a-z\.]{2,6})(?:[\/\w\.-]+)(.jpg|.png|.jpeg|.gif)\/?)", msg)
        for link in imageLinks:
            if link[0].find("https://lh3.googleusercontent") == -1:
                tmp_file = "/home/lshetron/.monopoly/tmp/" + str(random.randint(0,100)) + link[1]
                try:
                    with urllib.request.urlopen(link[0]) as response, open(tmp_file, "wb") as out:
                        data = response.read()
                        out.write(data)
                    self.message("", open(tmp_file, "rb"))
                except urllib.error.URLError as e:
                    print("Error opening file: ", e)
                except Exception as e:
                    print("Exception encountered: ", e)

        for subscriber, conv_id in self.swift.subscribers:
            re_mentions = re.compile('{0}|{1}'.format(subscriber.split()[0],
                                     name_to_nick(subscriber)), re.IGNORECASE)
            if (re.search(re_mentions, msg)
                and user.full_name != subscriber
                and len(clients) > 2
                and name_to_nick(subscriber) in clients):
                highlighted = re.sub(re_mentions, lambda x: '<b>' + x.group(0) + '</b>', msg)
                yield from self.swift.notify('<b>{0}</b> mentioned you in <i>{1}</i>:\n"{2}"'
                    .format(user.full_name, conv.name, highlighted), conv_id)
                print("Forwarded hangouts mention to {0}".format(subscriber))

        if re.search("!subscribe", msg, re.IGNORECASE):
            if user.full_name not in [name for name, id in self.swift.subscribers]:
                client_id = self.client.get_client_generated_id()
                inviteeID = hangouts_pb2.InviteeID(gaia_id=user.id_.gaia_id)
                conversation_request = hangouts_pb2.CreateConversationRequest(
                    request_header = self.client.get_request_header(),
                    type = CONVERSATION_TYPE_ONE_TO_ONE,
                    client_generated_id = client_id,
                    invitee_id = [inviteeID])
                res = yield from self.client.create_conversation(conversation_request)
                conv_id = res.conversation.conversation_id.id

                welcome_msg = ChatMessageSegment.from_str(
                    '<b>Welcome to Monopoly Swift Notifications!</b>\n' +
                    '<i>This channel will be used to receive alerts for IRC private ' +
                    'messages, channel mentions, and hangouts mentions.</i>\n\n' +
                    'To unsubscribe,\njust say <b><i>!unsubscribe</i></b>')
                new_conv = self.conv_list.get(conv_id)
                asyncio.async(new_conv.send_message(welcome_msg, image_file=None))

                if conv_id == conv.id_:
                    self.subscribe(user.full_name, conv_id, True)
                else:
                    self.subscribe(user.full_name, conv_id)
            else:
                self.message("<b>{0}</b> is already subscribed to receive alerts."
                    .format(user.full_name))

        elif re.search("!unsubscribe", msg, re.IGNORECASE):
            if user.full_name in [name for name, id in self.swift.subscribers]:
                for subscriber, id in self.swift.subscribers:
                    if user.full_name == subscriber:
                        self.unsubscribe(user.full_name, id)
            else:
                self.message("<b>{0}</b> is not currently subscribed to receive alerts."
                    .format(user.full_name))

        # TODO need shared health monitoring between hangouts and IRC
        if re.search("!uptime", msg, re.IGNORECASE):
            elapsed = int(time.time()) - g.starttime
            self.message("Monopoly has been running for: {0}".format(
                str(timedelta(seconds=elapsed))))

        if msg.find("!karma") != -1:
            _nick = ""
            sub = msg.find("!karma")
            words = msg[sub:].split()
            try:
                _nick = words[1].strip('`~!@#$%^&*()+={}[]\'\":;?/\\|.>,<')
                _nick = _nick.strip()
            except:
                pass
            if _nick.isalpha():
                self.karma(clients, _nick)
            elif _nick == "all":
                self.karma(clients, None, True)
            else:
                self.karma(clients)

        if msg.find("jakeism") != -1:
            self.jakeism()

        self.send(self.flush(), conv)

    def flush(self):
        buffer = self.messageBuffer
        self.messageBuffer = []
        return buffer

    def send(self, buffer, conv):
        for msg in buffer:
            segments = ChatMessageSegment.from_str(msg[0])
            asyncio.async(conv.send_message(segments, image_file=msg[1]))
