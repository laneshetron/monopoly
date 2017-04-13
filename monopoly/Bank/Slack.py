from Bank.Base import Base
from Bank.ORM import Channel
import re

class Bank(Base):
    def __init__(self, team):
        self.users = {}
        self.channels = {}
        self.me = {}

        if 'users' in team:
            for user in team['users']:
                self.set_user(user)
        if 'bots' in team:
            for bot in team['bots']:
                self.set_user(bot)
        if 'channels' in team:
            for channel in team['channels']:
                self.set_channel(channel)
        if 'groups' in team:
            for group in team['groups']:
                self.set_channel(group)
        if 'ims' in team:
            for im in team['ims']:
                self.set_channel(im)
        if 'self' in team:
            self.me = team['self']

        super().__init__()

    def set_channel(self, channel):
        self.channels[channel['id']] = channel
        db = Channel(channel['name'], channel['id']) # persist to db
        db.set_name(channel['name'])

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
        options = {}
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
        messages = super().receive(text, sender, clients)
        for x in messages:
            if x['type'] == 'karma':
                options['thread_ts'] = message['ts']
        if 'thread_ts' in message:
            options['thread_ts'] = message['thread_ts']

        # Some Slack-specific commands
        channel = Channel(self.channel_to_name(message['channel']), message['channel'])
        if re.search("!mute", text, re.IGNORECASE):
            channel.mute()
            messages.append({'text': '~ mute ~', 'fname': None, 'type': 'broadcast'})
            options['subtype'] = 'me_message'
        elif re.search("!softmute", text, re.IGNORECASE):
            channel.softmute()
            messages.append({'text': '~ soft mute ~ karma change messages will be suppressed',
                             'fname': None, 'type': 'broadcast'})
            options['subtype'] = 'me_message'
        elif re.search("!unmute", text, re.IGNORECASE):
            channel.unmute()
            messages.append({'text': '~ unmute ~', 'fname': None, 'type': 'broadcast'})
            options['subtype'] = 'me_message'

        # Filter in muted channels
        filtered = []
        for x in messages:
            if channel.mute_level < 1:
                filtered.append(x)
            elif channel.mute_level < 2 and x['type'] != 'karma':
                filtered.append(x)
            elif channel.mute_level == 2 and x['type'] == 'broadcast':
                filtered.append(x)

        return filtered, options
