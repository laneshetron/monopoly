from datetime import timedelta
import time
import random
import re
from Bank import g
from Bank.ORM import *
from Bank.Trumpisms import NaturalLanguage as nl

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

def modify(amount, sender, nick):
    if nick in modifications:
        modifications[nick][0] += amount
    else:
        modifications[nick] = [amount, sender]

def modify_messages(chnl):
    global modifications
    results = {}
    for nick, (amount, sender) in modifications.items():
        transaction = Transaction(sender, nick)
        transaction.transact(amount)

        results[nick] = (amount, transaction.receiver.karma)
    modifications = {}

    if len(results) < 2:
        for nick, (change, total) in results.items():
            if change > 0:
                change = " {0} ".format(change) if change > 1 else " "
                message("Gave{0}karma to {1} ({2})".format(change, nick, total), chnl)
            elif change < 0:
                change = " {0} ".format(abs(change)) if change < -1 else " "
                message("Took{0}karma from {1} ({2})".format(change, nick, total), chnl)
            else:
                message("I award you no points, and may God have mercy on your soul. {0} ({1})".format(nick, total), chnl)
    else:
        decrements = [x for x in sorted(results, key=results.get, reverse=True) if results[x][0] < 0]
        increments = [x for x in sorted(results, key=results.get) if results[x][0] > -1]
        if len(increments) > 0:
            if len(set([results[x][0] for x in increments])) < 2:
                change = results[increments[0]][0]
                change = " {0} ".format(change) if change != 1 else " "
                nicks = ["{0} ({1})".format(x, results[x][1]) for x in increments]
                message("Gave{0}karma to {1}".format(change, nl().nl_join(nicks)), chnl)
            else:
                nicks = []
                for x in increments:
                    substr = []
                    if not (results[x][0] == 1 and x == increments[0]):
                        substr.append(str(results[x][0]))
                    if x == increments[0]:
                        substr.append('karma')
                    substr.append('to')
                    substr.append(x)
                    substr.append('({0})'.format(results[x][1]))
                    nicks.append(' '.join(substr))
                message("Gave {0}".format(nl().nl_join(nicks)), chnl)

        if len(decrements) > 0:
            if len(set([results[x][0] for x in decrements])) < 2:
                change = results[decrements[0]][0]
                change = " {0} ".format(abs(change)) if change != -1 else " "
                nicks = ["{0} ({1})".format(x, results[x][1]) for x in decrements]
                message("Took{0}karma from {1}".format(change, nl().nl_join(nicks)), chnl)
            else:
                nicks = []
                for x in decrements:
                    substr = []
                    if not (results[x][0] == -1 and x == decrements[0]):
                        substr.append(str(abs(results[x][0])))
                    if x == decrements[0]:
                        substr.append('karma')
                    substr.append('from')
                    substr.append(x)
                    substr.append('({0})'.format(results[x][1]))
                    nicks.append(' '.join(substr))
                message("Took {0}".format(nl().nl_join(nicks)), chnl)

def uptime(chnl):
    message("Monopoly has been running for: {0}".format(
        str(timedelta(seconds=g.uptime.elapsed))), chnl)
    if g.uptime.elapsed != g.uptime.elapsedDisconnect:
        message("Time since last disconnect: {0}".format(
            str(timedelta(seconds=g.uptime.elapsedDisconnect))), chnl)

def punish(nick):
    transaction = Transaction('monopoly', nick)
    transaction.transact(-3)

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

def ding(count):
    g.ding += count

def ding_reset():
    if g.ding > 0:
        g.ding = 0
        message("Reset to 0", channel)

def trumpism():
    message(donald.trumpism(), channel)

def analytics(option, clients):
    clients = list(set(clients))
    a = Analytics(clients, limit=10)
    if option in ['givers', 'loved']:
        qualifier = 'positive'
    else:
        qualifier = 'negative'

    if option == 'givers':
        message("Monopoly's Most Generous", channel)
        for nick, ratio in a.top_givers:
            message("{0}: {1}% {2}".format(nick, ratio, qualifier), channel)
    elif option == 'takers':
        message("Monopoly's Most Pessimistic", channel)
        for nick, ratio in a.top_takers:
            message("{0}: {1}% {2}".format(nick, ratio, qualifier), channel)
    elif option == 'loved':
        message("Monopoly's Most Loved ❤", channel)
        for nick, ratio in a.top_loved:
            message("{0}: {1}% {2}".format(nick, ratio, qualifier), channel)
    elif option == 'hated':
        message("Monopoly's Les Deplorables", channel)
        for nick, ratio in a.top_hated:
            message("{0}: {1}% {2}".format(nick, ratio, qualifier), channel)

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

    basic = "(?:^|\s)@?(#?~*[\w$]+[?~]*%?){0}( [0-9]+)?(?!\S)"
    parens = "\(([\w#&%?~\-/ ]+)\){0}( [0-9]+)?(?!\S)"

    increments = {'basic':  re.findall(basic.format("\+\+"), privmsg),
                  'parens': re.findall(parens.format("\+\+"), privmsg)}
    decrements = {'basic':  re.findall(basic.format("--"), privmsg),
                  'parens': re.findall(parens.format("--"), privmsg)}

    for key, value in increments.items():
        for group in value:
            if key == 'basic':
                _nick = group[0].replace("_", " ")
            _nick = ' '.join(_nick.split()) # Reduces whitespaces and strips trailing
            if len(group[1]) > 0:
                delta = abs(int(group[1]))
            else:
                delta = None

            if delta is not None and s_user in whitelist:
                modify(delta, 'monopoly', _nick)
            else:
                if _nick.lower() != s_user:
                    if not private and _nick not in fixed:
                        if (g_ratelimiter.queue(s_user)
                            and r_ratelimiter.queue(_nick)
                            and sr_ratelimiter.queue(s_user + _nick)):
                            modify(1, s_user, _nick)
                        elif (g_ratelimiter.dropped(s_user) == 1
                            or r_ratelimiter.dropped(_nick) == 1
                            or sr_ratelimiter.dropped(s_user + _nick) == 1):
                            message("http://i.imgur.com/v79Hl19.jpg", channel)
                    elif private and s_user in whitelist:
                        modify(1, s_user, _nick)
                    elif private:
                        message("You are not on the whitelist for private messages.", channel)
                else:
                    if (g_ratelimiter.queue(s_user)
                        and r_ratelimiter.queue(s_user)
                        and sr_ratelimiter.queue(s_user + s_user)):
                        punish(s_user)
                    elif (g_ratelimiter.dropped(s_user) == 1
                        or r_ratelimiter.dropped(s_user) == 1
                        or sr_ratelimiter.dropped(s_user + s_user) == 1):
                        message("http://i.imgur.com/v79Hl19.jpg", channel)

    for key, value in decrements.items():
        for group in value:
            if key == 'basic':
                _nick = group[0].replace("_", " ")
            _nick = ' '.join(_nick.split()) # Reduces whitespaces and strips trailing
            if len(group[1]) > 0:
                delta = abs(int(group[1])) * -1
            else:
                delta = None

            if delta is not None and s_user in whitelist:
                modify(delta, 'monopoly', _nick)
            else:
                if s_user in blacklist:
                    if (g_ratelimiter.queue(s_user)
                        and sr_ratelimiter.queue(s_user + s_user)):
                        modify(-1, 'monopoly', s_user)
                        message("You've lost your downvoting privileges, {0}.".format(s_user), channel)
                    elif (g_ratelimiter.dropped(s_user) == 1
                        or sr_ratelimiter.dropped(s_user + s_user) == 1):
                        message("http://i.imgur.com/v79Hl19.jpg", channel)
                else:
                    if not private and _nick not in fixed:
                        if (g_ratelimiter.queue(s_user)
                            and r_ratelimiter.queue(_nick)
                            and sr_ratelimiter.queue(s_user + _nick)):
                            modify(-1, s_user, _nick)
                        elif (g_ratelimiter.dropped(s_user) == 1
                            or r_ratelimiter.dropped(_nick) == 1
                            or sr_ratelimiter.dropped(s_user + _nick) == 1):
                            message("http://i.imgur.com/v79Hl19.jpg", channel)
                    elif private and s_user in whitelist:
                        modify(-1, s_user, _nick)
                    elif private:
                        message("You are not on the whitelist for private messages.", channel)
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
            if re.match("all", _nick, re.IGNORECASE):
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

    if re.search("!ding reset", msg, re.IGNORECASE):
        ratelimit_command(ding_reset)

    elif re.search("!ding", msg, re.IGNORECASE):
        ratelimit_command(message, "Total: {0}".format(g.ding), channel)

    elif re.search("ding", msg, re.IGNORECASE):
        ratelimit_command(ding, 1)

    # Avoid outputting twice
    if re.search("trumpism", privmsg, re.IGNORECASE):
        ratelimit_command(trumpism)
    # Trumpisms currently disabled
    #else:
    #    # This won't be necessary once it's fixed in Channel.py
    #    # TODO should probably ratelimit this
    #    _privmsg = ' '.join(privmsg.rsplit()[1:])[1:].lower()
    #    provoked = donald.provoke(_privmsg)
    #    if provoked:
    #        message(provoked, channel)

    # Karma analytics
    if re.search("!givers", msg, re.IGNORECASE):
        ratelimit_command(analytics, 'givers', clients)
    elif re.search("!takers", msg, re.IGNORECASE):
        ratelimit_command(analytics, 'takers', clients)
    elif re.search("!loved", msg, re.IGNORECASE):
        ratelimit_command(analytics, 'loved', clients)
    elif re.search("!hated", msg, re.IGNORECASE):
        ratelimit_command(analytics, 'hated', clients)
