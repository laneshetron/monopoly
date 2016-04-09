from Bank import Bank, g
import re

def reset():
    try:
        reload(Bank)
        return True
    except Exception as e:
        print(e)
        return False

class Empty:
    pass

class Channel:

    def __init__(self, chan, swift=None, private=False):
        self.channel = chan
        self.nick = g.config['irc']['bot']['nick']
        self.socket = g.ircsock
        self.cursor = g.cursor
        self.db = g.db
        self.swift = swift
        self.private = private
        self.loggedIn = self.private
        self.clients = []

        if not self.private:
            self.socket.send("JOIN {0}\r\n".format(self.channel))

    def listen(self, msg):
        if msg.find("353") != -1:
            self.loggedIn = True
            groups = re.search("353 {0} . {1} :(.*)".format(self.nick, self.channel), msg)
            try:
                for uname in groups.group(1).split():
                    uname = uname.strip(':+@')
                    if uname.isalpha():
                        self.clients.append(uname)
            except:
                pass
            print(self.clients)

        if self.loggedIn:
            parts = msg.rsplit()
            privmsg = ""
            sender = parts[0]
            sender = sender[1:sender.find("!")]

            if parts[1] == "PRIVMSG":
                privmsg = ' '.join(parts[2:])

                if self.swift:
                    try:
                        self.swift.write("{0} {1}\r\n".format(sender, privmsg))
                    except Exception as e:
                        # swift is broken, hangups probably crashed
                        print("Could not write to Swift. Hangouts has likely crashed.", e)
                        self.swift = None

                Bank.operands(msg, privmsg, sender if self.private else self.channel,
                              self.clients, sender)

            if parts[1] == "JOIN":
                new = parts[0]
                n_user = new[1:new.find("!")].lower()
                if n_user.isalpha() and n_user != self.nick:
                    self.clients.append(n_user)
                    print("Added client %s (JOIN)" % n_user)

            if parts[1] == ("PART" or "QUIT"):
                old = parts[0]
                o_user = old[1:old.find("!")].lower()
                if o_user.isalpha() and o_user in self.clients and o_user != self.nick:
                    self.clients.remove(o_user)
                    print("Removed client %s from channel list." % o_user)

            if parts[1] == "KICK":
                kicked_user = parts[3].lower()
                if kicked_user.isalpha() and kicked_user in self.clients and kicked_user != self.nick:
                    self.clients.remove(kicked_user)
                    print("Removed client %s from channel list. (KICKED)" % kicked_user)
