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
    "*standing at a urinal* Man, these things are heavy... The helmet, I mean.",
    "I'm not gonna f****n Bernie Sanders my lunch at work." ]
rand_jakeisms = []

blacklist = g.config['irc']['blacklist']
whitelist = g.config['irc']['whitelist']
fixed = g.config['irc']['fixed']
channelList = g.channels + g.silent_channels
modifications = {}
g_ratelimiter = g.ratelimiter()
r_ratelimiter = g.ratelimiter(max=12)
sr_ratelimiter = g.ratelimiter(max=6)
k_ratelimiter = g.ratelimiter(1, 300000)


def message(msg, chnl):
    if chnl not in g.silent_channels:
        ircsock.send("PRIVMSG {0} :{1}\r\n".format(chnl, msg))

def action(msg, chnl):
    if chnl not in g.silent_channels:
        ircsock.send("PRIVMSG {0} :\x01ACTION {1}\x01\r\n".format(chnl, msg))

def modify(amount, nick):
    if nick in modifications:
        modifications[nick] += amount
    else:
        modifications[nick] = amount

def modify_messages(chnl):
    global modifications
    for nick, amount in modifications.items():
        cursor.execute("SELECT * FROM monopoly WHERE nick = ? COLLATE NOCASE LIMIT 1",
            (nick,))
        data = cursor.fetchall()
        if len(data) > 0:
            karma = data[0][2] + amount
            nick = data[0][1]
            id = data[0][0]
            cursor.execute("UPDATE monopoly SET karma = ? WHERE id = ?",
                            (karma, id))
            db.commit()
        else:
            cursor.execute("INSERT INTO monopoly(nick, karma) VALUES(?, ?)",
                (nick, amount))
            db.commit()
            karma = amount

        if amount == 1:
            message("Gave karma to {0}  Total: {1}".format(nick, karma), chnl)
        elif amount == -1:
            message(":( {0}  Total: {1}".format(nick, karma), chnl)
        else:
            message("{0} karma to {1}  Total: {2}".format(amount, nick, karma), chnl)
    modifications = {}

def uptime(chnl):
    message("Monopoly has been running for: {0}".format(
        str(timedelta(seconds=g.uptime.elapsed))), chnl)
    if g.uptime.elapsed != g.uptime.elapsedDisconnect:
        message("Time since last disconnect: {0}".format(
            str(timedelta(seconds=g.uptime.elapsedDisconnect))), chnl)

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
    msg = limit = ""
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
            limit += " COLLATE NOCASE"
        limit += " ORDER BY karma DESC LIMIT 10"
    print("SELECT * FROM monopoly {0}".format(limit))
    cursor.execute("SELECT * FROM monopoly {0}".format(limit))
    data = cursor.fetchall()
    for row in data:
        msg += "{0} {1}".format(row[1], row[2])
        if row != data[-1]:
            msg += " : "
    message(msg, channel)

def parentheses(msg):
    sub = msg.find("(")
    if sub == -1:
        return
    else:
        part = msg[sub:].strip('`~!@#$%^&*()+={}[]\'\":;?/\\|.>,<')
        part = ' '.join(part.split())
        return part

def jakeism(chnl):
    global jakeisms, rand_jakeisms
    if not rand_jakeisms:
        rand_jakeisms = random.sample(jakeisms, len(jakeisms))
    quote = rand_jakeisms.pop()
    message(quote, chnl)

def trumpism():
    message(donald.trumpism(), channel)

def ratelimit_command(command, *args):
    if ((private and g_ratelimiter.queue('global') and g_ratelimiter.queue(s_user))
        or (not private and g_ratelimiter.queue(s_user))):
        command(*args)
    elif ((private and g_ratelimiter.dropped('global') == 1)
        or g_ratelimiter.dropped(s_user) == 1):
        message("http://i.imgur.com/v79Hl19.jpg", channel)

def operands(msg, privmsg, chnl, clients, sender, trumpisms):
    global channel, private, s_user, ircsock, cursor, db, donald
    channel = chnl
    private = channel not in channelList
    s_user = sender
    donald = trumpisms
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
            modify(delta, _nick)
        else:
            if _nick.lower() != s_user:
                if not private and _nick not in fixed:
                    if (g_ratelimiter.queue(s_user)
                        and r_ratelimiter.queue(_nick)
                        and sr_ratelimiter.queue(s_user + _nick)):
                        modify(1, _nick)
                    elif (g_ratelimiter.dropped(s_user) == 1
                        or r_ratelimiter.dropped(_nick) == 1
                        or sr_ratelimiter.dropped(s_user + _nick) == 1):
                        message("http://i.imgur.com/v79Hl19.jpg", channel)
                elif private and s_user in whitelist:
                    modify(1, _nick)
                elif private:
                    message("This command is whitelisted for private messages.", channel)
            else:
                if (g_ratelimiter.queue(s_user)
                    and r_ratelimiter.queue(s_user)
                    and sr_ratelimiter.queue(s_user + s_user)):
                    punish(s_user)
                elif (g_ratelimiter.dropped(s_user) == 1
                    or r_ratelimiter.dropped(s_user) == 1
                    or sr_ratelimiter.dropped(s_user + s_user) == 1):
                    message("http://i.imgur.com/v79Hl19.jpg", channel)

    for group in decrements:
        _nick = group[0].replace("_", " ")
        _nick = ' '.join(_nick.split()) # Reduces whitespaces and strips trailing
        if len(group[1]) > 0:
            delta = abs(int(group[1])) * -1
        else:
            delta = None

        if delta is not None and s_user in whitelist:
            modify(delta, _nick)
        else:
            if s_user in blacklist:
                if (g_ratelimiter.queue(s_user)
                    and sr_ratelimiter.queue(s_user + s_user)):
                    modify(-1, s_user)
                    message("You've lost your downvoting privileges, {0}.".format(s_user), channel)
                elif (g_ratelimiter.dropped(s_user) == 1
                    or sr_ratelimiter.dropped(s_user + s_user) == 1):
                    message("http://i.imgur.com/v79Hl19.jpg", channel)
            else:
                if not private and _nick not in fixed:
                    if (g_ratelimiter.queue(s_user)
                        and r_ratelimiter.queue(_nick)
                        and sr_ratelimiter.queue(s_user + _nick)):
                        modify(-1, _nick)
                    elif (g_ratelimiter.dropped(s_user) == 1
                        or r_ratelimiter.dropped(_nick) == 1
                        or sr_ratelimiter.dropped(s_user + _nick) == 1):
                        message("http://i.imgur.com/v79Hl19.jpg", channel)
                elif private and s_user in whitelist:
                    modify(-1, _nick)
                elif private:
                    message("This command is whitelisted for private messages.", channel)
    modify_messages(channel)

    if re.search("!uptime", privmsg, re.IGNORECASE):
        ratelimit_command(uptime, channel)

    karma_parens = re.search("!karma \(([a-zA-Z ]+)\)", privmsg, re.IGNORECASE)
    karma_underscores = re.search("!karma( [a-zA-Z_]+)?(?!\S)", privmsg, re.IGNORECASE)
    # TODO write exceptions for these ratelimits if in whitelist
    if karma_parens:
        def print_karma():
            _nick = ' '.join(karma_parens.group(1).split())
            if s_user not in blacklist:
                karma(clients, _nick)
            else:
                message("Nice try, {0}.".format(s_user), channel)
        ratelimit_command(print_karma)

    elif karma_underscores and karma_underscores.group(1):
        def print_karma():
            _nick = karma_underscores.group(1).replace("_", " ").strip()
            _nick = ' '.join(_nick.split())
            if re.search("all", _nick, re.IGNORECASE):
                if k_ratelimiter.queue('global'):
                    if s_user not in blacklist:
                        karma(clients, all=True)
                    else:
                        message("Nice try, {0}.".format(s_user), channel)
            else:
                if s_user not in blacklist:
                    karma(clients, _nick)
                else:
                    message("Nice try, {0}.".format(s_user), channel)
        ratelimit_command(print_karma)

    elif karma_underscores:
        def print_karma():
            if s_user not in blacklist:
                karma(clients)
            else:
                message("Nice try, {0}.".format(s_user), channel)
        if k_ratelimiter.queue('global'):
            ratelimit_command(print_karma)
        # No ratelimit image here as it may be triggered often

    if privmsg.find("jakeism") != -1:
        ratelimit_command(jakeism, channel)

    if privmsg.find("points") != -1:
        points_message = "Welcome to {0}, the channel where everything's made up " \
                         "and the points don't matter.".format(channel)
        ratelimit_command(message, points_message, channel)

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
           ratelimit_command(message, "This command is whitelisted.", channel)

    # Avoid outputting twice
    if re.search("trumpism", privmsg, re.IGNORECASE):
        ratelimit_command(trumpism)
    else:
        # This won't be necessary once it's fixed in Channel.py
        # TODO should probably ratelimit this
        _privmsg = ' '.join(privmsg.rsplit()[1:])[1:].lower()
        provoked = donald.provoke(_privmsg)
        if provoked:
            message(provoked, channel)
