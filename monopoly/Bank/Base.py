from datetime import timedelta
import time
import urllib.request
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
    "I'm not gonna f\*\*\*\*n Bernie Sanders my lunch at work." ]
blacklist = g.config['irc']['blacklist']
whitelist = g.config['irc']['whitelist']
fixed = g.config['irc']['fixed']

class Base:
    def __init__(self):
        self.db = g.db
        self.cursor = g.cursor
        self.messageBuffer = []
        self.rand_jakeisms = []
        self.modifications = {}
        self.g_ratelimiter = g.ratelimiter()
        self.r_ratelimiter = g.ratelimiter(max=12)
        self.sr_ratelimiter = g.ratelimiter(max=6)
        self.k_ratelimiter = g.ratelimiter(1, 300000)

    def message(self, msg, fname=None):
        self.messageBuffer.append([msg, fname])

    def modify(self, amount, nick, sender):
        if nick in self.modifications:
            self.modifications[nick][0] += amount
        else:
            self.modifications[nick] = [amount, sender]

    def modify_messages(self):
        results = {}
        for nick, (amount, sender) in self.modifications.items():
            transaction = Transaction(sender, nick)
            transaction.transact(amount)

            results[nick] = (amount, transaction.receiver.karma)
        self.modifications = {}

        if len(results) < 2:
            for nick, (change, total) in results.items():
                if change > 0:
                    change = " {0} ".format(change) if change > 1 else " "
                    self.message("Gave{0}karma to {1} ({2})".format(change, nick, total))
                elif change < 0:
                    change = " {0} ".format(abs(change)) if change < -1 else " "
                    self.message("Took{0}karma from {1} ({2})".format(change, nick, total))
                else:
                    self.message("I award you no points, and may God have mercy on your soul. {0} ({1})".format(nick, total))
        else:
            keys = sorted(results, key=results.get)
            decrements = [x for x in sorted(results, key=results.get, reverse=True)
                          if results[x][0] < 0]
            increments = [x for x in sorted(results, key=results.get) if results[x][0] > -1]
            if len(increments) > 0:
                if len(set([results[x][0] for x in increments])) < 2:
                    change = results[increments[0]][0]
                    change = " {0} ".format(change) if change != 1 else " "
                    nicks = ["{0} ({1})".format(x, results[x][1]) for x in increments]
                    self.message("Gave{0}karma to {1}".format(change, nl().nl_join(nicks)))
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
                    self.message("Gave {0}".format(nl().nl_join(nicks)))

            if len(decrements) > 0:
                if len(set([results[x][0] for x in decrements])) < 2:
                    change = results[decrements[0]][0]
                    change = " {0} ".format(abs(change)) if change != 1 else " "
                    nicks = ["{0} ({1})".format(x, results[x][1]) for x in decrements]
                    self.message("Took{0}karma from {1}".format(change, nl().nl_join(nicks)))
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
                    self.message("Took {0}".format(nl().nl_join(nicks)))

    def punish(self, nick):
        transaction = Transaction('monopoly', nick)
        transaction.transact(-3)

        self.message("Punished {0}!! >:(  Total: {1}".format(nick, transaction.receiver.karma))

    def karma(self, clients, nick=None, all=False):
        clients = list(set(clients))
        msg = limit = ""
        print(clients)
        if nick is not None:
            limit = "WHERE nick = '%s' COLLATE NOCASE LIMIT 1" % nick
            self.message("Monopoly karma total for {0}:".format(nick))
        elif all:
            # do not set WHERE statement
            limit = " ORDER BY karma DESC LIMIT 10"
            self.message("Global Monopoly karma totals:")
        else:
            if len(clients) > 0:
                self.message("Monopoly karma totals for this channel:")
                limit = "WHERE "
                for uname in clients:
                    limit += "nick = '%s'" % uname
                    if uname != clients[-1]:
                        limit += " OR "
                limit += " COLLATE NOCASE"
            limit += " ORDER BY karma DESC LIMIT 10"
        print("SELECT * FROM monopoly {0}".format(limit))
        self.cursor.execute("SELECT * FROM monopoly {0}".format(limit))
        data = self.cursor.fetchall()
        for row in data:
            msg += "{0} {1}".format(row[1], row[2])
            if row != data[-1]:
                msg += "\n"
        self.message(msg)

    def jakeism(self):
        if not self.rand_jakeisms:
            self.rand_jakeisms = random.sample(jakeisms, len(jakeisms))
        quote = self.rand_jakeisms.pop()
        self.message(quote)

    def receive(self, msg, sender, clients):
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
                self.modify(delta, _nick, 'monopoly')
            else:
                if _nick.lower() != sender:
                    if sender not in blacklist and _nick not in fixed:
                        if len(clients) > 2 or sender in whitelist:
                            if (self.g_ratelimiter.queue(sender)
                                and self.r_ratelimiter.queue(_nick)
                                and self.sr_ratelimiter.queue(sender + _nick)):
                                self.modify(1, _nick, sender)
                        else:
                            self.message("You are not on the whitelist for private messages.")
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
                self.modify(delta, _nick, 'monopoly')
            else:
                if len(clients) > 2 or sender in whitelist:
                    if (self.g_ratelimiter.queue(sender)
                        and self.r_ratelimiter.queue(_nick)
                        and self.sr_ratelimiter.queue(sender + _nick)):
                        if sender in blacklist:
                            self.modify(-1, sender, 'monopoly')
                            self.message("You've lost your downvoting privileges, {0}."
                                .format(sender))
                        elif _nick in fixed:
                            pass
                        else:
                            self.modify(-1, _nick, sender)
                else:
                    self.message("You are not on the whitelist for private messages.")

        # TODO need shared health monitoring between hangouts and IRC
        if re.search("!uptime", msg, re.IGNORECASE):
            if self.g_ratelimiter.queue(sender):
                self.message("Monopoly has been running for: {0}".format(
                    str(timedelta(seconds=g.uptime.elapsed))))

        karma_parens = re.search("!karma \(([a-zA-Z ]+)\)", msg, re.IGNORECASE)
        karma_underscores = re.search("!karma( [a-zA-Z_]+)?(?!\S)", msg, re.IGNORECASE)

        if karma_parens:
            if self.g_ratelimiter.queue(sender):
                _nick = ' '.join(karma_parens.group(1).split())
                if sender not in blacklist:
                    self.karma(clients, _nick)
                else:
                    self.message("Nice try, {0}.".format(sender))

        elif karma_underscores and karma_underscores.group(1):
            if self.g_ratelimiter.queue(sender):
                _nick = karma_underscores.group(1).replace("_", " ")
                _nick = ' '.join(_nick.split())
                if re.match("all", _nick, re.IGNORECASE):
                    if self.k_ratelimiter.queue('global'):
                        if sender not in blacklist:
                            self.karma(clients, all=True)
                        else:
                            self.message("Nice try, {0}.".format(sender))
                else:
                    if sender not in blacklist:
                        self.karma(clients, _nick)
                    else:
                        self.message("Nice try, {0}.".format(sender))
        elif karma_underscores:
            if self.k_ratelimiter.queue('global') and self.g_ratelimiter.queue(sender):
                if sender not in blacklist:
                    self.karma(clients)
                else:
                    self.message("Nice try, {0}.".format(sender))

        if msg.find("jakeism") != -1:
            if self.g_ratelimiter.queue(sender):
                self.jakeism()

        # Useful for counting arbitrary things of sudden importance
        # e.g. cups of coffee, number of times someone uses the word "synergy"
        # in a meeting, how many times your coworker paces through the hallways...
        if re.search("!ding reset", msg, re.IGNORECASE):
            if self.g_ratelimiter.queue(sender) and g.ding > 0:
                g.ding = 0
                self.message("Reset to 0")

        elif re.search("!ding", msg, re.IGNORECASE):
            if self.g_ratelimiter.queue(sender):
                self.message("Total: <b>{0}</b>".format(g.ding))

        elif re.search("ding", msg, re.IGNORECASE):
            if self.g_ratelimiter.queue(sender):
                g.ding += 1

        # Karma analytics
        if re.search("!givers", msg, re.IGNORECASE):
            if self.g_ratelimiter.queue(sender):
                analytics = Analytics(clients, limit=10)
                message = "Monopoly's Most Generous\n"
                for nick, ratio in analytics.top_givers:
                    message += "{0}: {1}% positive\n".format(nick, ratio)
                self.message(message)

        elif re.search("!takers", msg, re.IGNORECASE):
            if self.g_ratelimiter.queue(sender):
                analytics = Analytics(clients, limit=10)
                message = "Monopoly's Most Pessimistic\n"
                for nick, ratio in analytics.top_takers:
                    message += "{0}: {1}% negative\n".format(nick, ratio)
                self.message(message)

        elif re.search("!loved", msg, re.IGNORECASE):
            if self.g_ratelimiter.queue(sender):
                analytics = Analytics(clients, limit=10)
                message = "Monopoly's Most Loved ❤\n"
                for nick, ratio in analytics.top_loved:
                    message += "{0}: {1}% positive\n".format(nick, ratio)
                self.message(message)

        elif re.search("!hated", msg, re.IGNORECASE):
            if self.g_ratelimiter.queue(sender):
                analytics = Analytics(clients, limit=10)
                message = "Monopoly's Les Deplorables\n"
                for nick, ratio in analytics.top_hated:
                    message += "{0}: {1}% negative\n".format(nick, ratio)
                self.message(message)

        return self.flush()

    def flush(self):
        self.modify_messages()
        buffer = self.messageBuffer
        self.messageBuffer = []
        return buffer
