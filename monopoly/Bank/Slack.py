from Bank.Base import Base
import re

class Bank(Base):
    def __init__(self, team):
        self.users = {}
        self.channels = {}

        if 'users' in team:
            for user in team['users']:
                self.users[user['id']] = user
        if 'channels' in team:
            for channel in team['channels']:
                self.channels[channel['id']] = channel
        if 'groups' in team:
            for group in team['groups']:
                self.channels[group['id']] = group
        super().__init__()

    def set_channel(self, channel):
        self.channels[channel['id']] = channel

    def id_to_name(self, id):
        if id in self.users:
            return self.users[id]['name']
        return id

    def members(self, id):
        if id in self.channels and 'members' in self.channels[id]:
            return [self.id_to_name(uid) for uid in self.channels[id]['members']]
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
            text = re.sub(re_mentions, name, text)

        # Replace — (emdash) with --
        text = re.sub("—", "--", text)

        sender = self.id_to_name(message['user'])
        clients = self.members(message['channel'])
        return super().receive(text, sender, clients)
