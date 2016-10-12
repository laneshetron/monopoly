from Bank.Base import Base
from Bank.Trumpisms import Trumpisms
from hangups import (ChatMessageSegment, hangouts_pb2)
import asyncio

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

class Bank(Base):
    def __init__(self, client, conv_list, swift):
        self.client = client
        self.conv_list = conv_list
        self.swift = swift
        self.donald = Trumpisms()
        super().__init__()

    @asyncio.coroutine
    def receive(self, msg, conv, user):
        clients = []
        for userObject in conv.users:
            nick = name_to_nick(userObject.full_name)
            clients.append(nick)
        sender = name_to_nick(user.full_name)

        imageLinks = re.findall("((?:https?:\/\/)?(?:[\da-z\.-]+)\.(?:[a-z\.]{2,6})(?:[\/\w\.-]+)(\.jpg|\.png|\.jpeg|\.gif)\/?)", msg)
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
            re_mentions = re.compile('{0}|{1}|{2}'.format(name_to_nick(subscriber),
                                     *subscriber.split()), re.IGNORECASE)
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

        # Avoid outputting twice
        if re.search("trumpism", msg, re.IGNORECASE):
            if self.g_ratelimiter.queue(sender):
                self.message("<i>{0}</i>".format(self.donald.trumpism()))
        else:
            # TODO should ratelimit
            provoked = self.donald.provoke(msg)
            if provoked:
                self.message("<i>{0}</i>".format(provoked))

        buffer = super().receive(msg, sender, clients)
        self.send(buffer, conv)

    def send(self, buffer, conv):
        for msg in buffer:
            segments = ChatMessageSegment.from_str(msg[0])
            asyncio.async(conv.send_message(segments, image_file=msg[1]))

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
