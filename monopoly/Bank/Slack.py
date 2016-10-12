from Bank.Base import Base

class Bank(Base):
    def __init__(self, users, channels):
        self.users = {}
        self.channels = {}

        for user in users:
            self.users[user['id']] = user
        for channel in channels:
            self.channels[channel['name']] = channel
        super().__init__()

    def id_to_name(self, id):
        if id in self.users:
            return self.users[id]['name']

    def members(self, name):
        if name in self.channels:
            return [self.id_to_name(id) for id in self.channels[name]['members']]

    def receive(self, message):
        text = message['text']
        sender = self.id_to_name(message['user'])
        clients = self.members(message['channel'])
        return super().receive(text, sender, clients)
