# -*- coding: utf-8 -*-

from datetime import timedelta
import time
import random
import re
from Bank import g

jakeisms = [
    "That guy died of ebola, I don't CARE anymore.",
    "pop pop click *exasperated sigh*",
    "You're still using the default terminal? I use iTerm.",
    "Whenever I spend the entire day looking at my external monitor and then go to use just my laptop my whole brain goes into a pretzel.",
    "I'm all about the funny",
    "It's a slippery slope: one day you're generating api tokens, the next you're torrenting Final Cut Pro.",
    "I've got a little grease lake going here. And I shall name you: Grease Lake!",
    "These German BMW makers are torturing asses.",
    "*standing at a urinal* Man, these things are heavy... The helmet, I mean." ]
blacklist = g.config['irc']['blacklist']
whitelist = g.config['irc']['whitelist']
channelList = g.channels + g.silent_channels
silent_channels = g.silent_channels


def message(msg, chnl):
    if chnl not in silentChannels:
        ircsock.send("PRIVMSG {0} :{1}\r\n".format(chnl, msg))

def action(msg, chnl):
    if chnl not in silentChannels:
        ircsock.send("PRIVMSG {0} :\x01ACTION {1}\x01\r\n".format(chnl, msg))

def modify(amount, nick, chnl):
    cursor.execute("SELECT * FROM monopoly WHERE nick = ? COLLATE NOCASE LIMIT 1", (nick,))
    data = cursor.fetchall()
    if len(data) > 0:
        karma = data[0][2] + amount
        nick = data[0][1]
        id = data[0][0]
        cursor.execute("UPDATE monopoly SET karma = ? WHERE id = ?",
                        (karma, id))
        db.commit()
    else:
        cursor.execute("INSERT INTO monopoly(nick, karma) VALUES(?, ?)", (nick, amount))
        db.commit()
        karma = amount

    if amount == 1:
        message("Gave karma to {0}  Total: {1}".format(nick, karma), chnl)
    elif amount == -1:
        message(":( {0}  Total: {1}".format(nick, karma), chnl)
    else:
        message("{0} karma to {1}  Total: {2}".format(amount, nick, karma), chnl)

def punish(nick):
    cursor.execute("SELECT * FROM monopoly WHERE nick = ? COLLATE NOCASE LIMIT 1", (nick,))
    data = cursor.fetchall()
    if len(data) > 0:
        karma = data[0][2] - 3
        nick = data[0][1]
        id = data[0][0]
        cursor.execute("UPDATE monopoly SET karma = ? WHERE id = ?",
                        (karma, id))
        db.commit()
    else:
        cursor.execute("INSERT INTO monopoly(nick, karma) VALUES(?, -3)", (nick,))
        db.commit()
        karma = -3

    message("Punished {0}!! >:(  Total: {1}".format(nick, karma), channel)

def karma(clients, nick=None, all=False):
    clients = list(set(clients))
    limit = ""
    print(clients)
    if nick is not None:
        limit = "WHERE nick = '%s' COLLATE NOCASE LIMIT 1" % nick
        message("Monopoly karma total for {0}:".format(nick), channel)
    elif all:
        # do not set WHERE statement
        limit = " ORDER BY karma DESC LIMIT 10"
        message("Global Monopoly karma totals:", channel)
    else:
        if len(clients) > 0:
            message("Monopoly karma totals for {0}:".format(channel), channel)
            limit = "WHERE "
            for uname in clients:
                limit += "nick = '%s'" % uname
                if uname != clients[-1]:
                    limit += " OR "
            limit += " COLLATE NOCASE ORDER BY karma DESC LIMIT 10"
    print("SELECT * FROM monopoly {0}".format(limit))
    cursor.execute("SELECT * FROM monopoly {0}".format(limit))
    data = cursor.fetchall()
    for row in data:
        message("{0}: {1}".format(row[1], row[2]), channel)

def parentheses(msg):
    sub = msg.find("(")
    if sub == -1:
        return
    else:
        part = msg[sub:].strip('`~!@#$%^&*()+={}[]\'\":;?/\\|.>,<')
        part = ' '.join(part.split())
        return part

def jakeism(chnl):
    global jakeisms
    quote = random.choice(jakeisms)
    message(quote, chnl)

def operands(msg, privmsg, chnl, clients, s_user):
    global channel, ircsock, cursor, db
    channel = chnl
    ircsock = g.ircsock
    cursor = g.cursor
    db = g.db

    increments = re.findall("(?:^|:|\s)([a-zA-Z_]+)\+\+( [0-9]+)?", privmsg) + re.findall("\(([a-zA-Z ]+)\)\+\+( [0-9]+)?", privmsg) # parens
    decrements = re.findall("(?:^|:|\s)([a-zA-Z_]+)--( [0-9]+)?(?!\S)", privmsg) + re.findall("\(([a-zA-Z ]+)\)--( [0-9]+)?", privmsg) # parens

    for group in increments:
        _nick = group[0].replace("_", " ")
        _nick = ' '.join(_nick.split()) # Reduces whitespaces and strips trailing
        if len(group[1]) > 0:
            delta = abs(int(group[1]))
        else:
            delta = None

        if delta is not None and s_user in whitelist:
            modify(delta, _nick, channel)
        else:
            if _nick.lower() != s_user:
                if channel in channelList:
                    modify(1, _nick, channel)
                elif channel not in channelList and s_user in whitelist:
                    modify(1, _nick, channel)
                else:
                    message("This command is whitelisted for private messages.", channel)
            else:
                punish(s_user)

    for group in decrements:
        _nick = group[0].replace("_", " ")
        _nick = ' '.join(_nick.split()) # Reduces whitespaces and strips trailing
        if len(group[1]) > 0:
            delta = abs(int(group[1])) * -1
        else:
            delta = None

        if delta is not None and s_user in whitelist:
            modify(delta, _nick, channel)
        else:
            if s_user in blacklist:
                modify(-1, s_user, channel)
                message("You've lost your downvoting privileges, {0}.".format(s_user), channel)
            else:
                if channel in channelList:
                    modify(-1, _nick, channel)
                elif channel not in channelList and s_user in whitelist:
                    modify(-1, _nick, channel)
                else:
                    message("This command is whitelisted for private messages.", channel)

    if re.search("!uptime", privmsg, re.IGNORECASE):
        running_elapsed = int(time.time()) - g.starttime
        disconnect_elapsed = int(time.time()) - g.lastDisconnect
        message("Monopoly has been running for: {0}".format(
            str(timedelta(seconds=running_elapsed))), channel)
        if running_elapsed != disconnect_elapsed:
            message("Time since last disconnect: {0}".format(
                str(timedelta(seconds=disconnect_elapsed))), channel)

    karma_parens = re.search("!karma \(([a-zA-Z ]+)\)", privmsg, re.IGNORECASE)
    karma_underscores = re.search("!karma( [a-zA-Z_]+)?(?!\S)", privmsg, re.IGNORECASE)

    if karma_parens:
        _nick = ' '.join(karma_parens.group(1).split())
        karma(clients, _nick)
    elif karma_underscores and karma_underscores.group(1):
        _nick = karma_underscores.group(1).replace("_", " ").strip()
        if re.search("all", _nick, re.IGNORECASE):
            karma(clients, all=True)
        else:
            karma(clients, _nick)
    elif karma_underscores:
        karma(clients)

    if privmsg.find("jakeism") != -1:
        jakeism(channel)

    if privmsg.find("points") != -1:
        message("Welcome to {0}, the channel where everything's made up and the points don't matter.".format(channel), channel)

    if privmsg.find("!chaos") != -1:
       if s_user in whitelist:
           action("Activating CHAOS MODE", channel)
           bodyCount = random.randint(1,len(clients))
           for a in range(0, bodyCount):
               command = random.choice(['++', '--'])
               victim = random.choice(clients)
               damage = random.randint(0,100)
               message(victim + command + " " + str(damage), channel)
           action("Out of ammo...", channel)
       else:
           message("This command is whitelisted.", channel)
