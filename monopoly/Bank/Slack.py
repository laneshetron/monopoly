from Bank.Base import Base
import re

class Bank(Base):
    def __init__(self, team):
        self.users = {}
        self.channels = {}
        self.me = {}

        if 'users' in team:
            for user in team['users']:
                self.users[user['id']] = user
        if 'bots' in team:
            for bot in team['bots']:
                self.users[bot['id']] = bot
        if 'channels' in team:
            for channel in team['channels']:
                self.channels[channel['id']] = channel
        if 'groups' in team:
            for group in team['groups']:
                self.channels[group['id']] = group
        if 'ims' in team:
            for im in team['ims']:
                self.channels[im['id']] = im
        if 'self' in team:
            self.me = team['self']

        super().__init__()

    def set_channel(self, channel):
        self.channels[channel['id']] = channel

    def set_user(self, user):
        self.users[user['id']] = user

    def channel_to_name(self, id):
        if id in self.channels:
            try:
                return self.channels[id]['name']
            except:
                return self.id_to_name(id)
        return id

    def id_to_name(self, id):
        if id in self.users:
            return self.users[id]['name']
        return id

    def members(self, id):
        if id in self.channels and 'members' in self.channels[id]:
            return [self.id_to_name(uid) for uid in self.channels[id]['members']]
        elif id in self.channels and 'user' in self.channels[id]:
            if self.me:
                return [self.id_to_name(uid) for uid in [self.channels[id]['user'], self.me['id']]]
            else:
                # pedantic fallback
                return [self.id_to_name(self.channels[id]['user'])]
        return []

    def receive(self, message):
        # Handle members joining & leaving
        if 'subtype' in message:
            if (message['subtype'] in ['channel_join', 'group_join'] and
                message['user'] not in self.channels[message['channel']]['members']):
                self.channels[message['channel']]['members'].append(message['user'])
            if (message['subtype'] in ['channel_leave', 'group_leave'] and
                message['user'] in self.channels[message['channel']]['members']):
                self.channels[message['channel']]['members'].remove(message['user'])

        # Replace Slack @ mentions with uname before proceeding
        text = message['text']
        re_mentions = re.compile("<@([0-9a-zA-Z]+)\|?(?:[0-9a-zA-Z]+)?>")
        for mention in re.findall(re_mentions, text):
            name = self.id_to_name(mention)
            text = re.sub("<@{0}\|?(?:[0-9a-zA-Z]+)?>".format(mention), name, text)

        # Replace — (emdash) with --
        text = re.sub("—", "--", text)

        # Replace &amp; with &
        text = re.sub("&amp;", "&", text)

        sender = self.id_to_name(message['user'])
        clients = self.members(message['channel'])
        return super().receive(text, sender, clients)
