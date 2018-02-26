from Bank.Slack import Bank
from Bank import g
import websocket
import requests
import time
import json

token = g.config['slack']['api-token']

def rtmStart(token):
    params = {'token': token, 'simple_latest': True, 'no_unreads': True}
    return requests.get('https://slack.com/api/rtm.start', params=params).json()

def conversationsMembers(token, channel, limit=300):
    params = {'token': token, 'channel': channel, 'limit': limit}
    return requests.get('https://slack.com/api/conversations.members', params=params).json()

def postMessage(token, channel, text=None, opts=None):
    base = {'token': token, 'channel': channel, 'as_user': True}
    params = {**base, **opts} if opts else base
    params['text'] = text if text else ''
    res = requests.get('https://slack.com/api/chat.postMessage', params=params).json()
    return res['ok']

class SlackClient:
    def __init__(self):
        self.up = False
        self.ws = None
        self.bank = None

    def _update_members(self):
        if self.bank is None:
            return
        for k, v in self.bank.channels.items():
            if v.get('is_member', False):
                res = conversationsMembers(token, k)
                self.bank.channels[k]['members'] = list(
                    set(v.get('members', [])) | set(res.get('members', [])))

    def send(self, text, channel, opts=None):
        if opts and 'attachments' in opts:
            # Attachments can only be created through the Web API
            return postMessage(token, channel, text, opts)

        if self.ws:
            base = {'id': 1, 'type': 'message', 'channel': channel, 'text': text}
            message = {**base, **opts} if opts else base
            message = json.dumps(message)
            self.ws.send(message)
        else:
            raise Exception('No websocket available.')

    def on_message(self, ws, message):
        message = json.loads(message)
        # TODO this should be restored with DEBUG log level
        #print(message)
        if 'type' in message:
            if message['type'] == 'hello':
                self.up = True
            elif message['type'] == 'error':
                print('Error encountered: {1}'.format(message['error']))
            elif message['type'] in ['channel_joined', 'group_joined', 'im_created']:
                self.bank.set_channel(message['channel'])
            elif message['type'] in ['team_join', 'user_change']:
                self.bank.set_user(message['user'])
            elif message['type'] in ['bot_added', 'bot_changed']:
                self.bank.set_user(message['bot'])
            elif (message['type'] == 'message'
                and 'reply_to' not in message
                and ('subtype' not in message
                    or message['subtype'] not in ['message_changed', 'message_deleted'])):
                # Consume message
                print("{0}: {1}\n{2}".format(self.bank.channel_to_name(message['channel']),
                                             message['text'], self.bank.id_to_name(message['user'])))
                buffer, options = self.bank.receive(message)
                for msg in buffer:
                    self.send(msg['text'], message['channel'], options)

    def on_error(self, ws, error):
        print(error)
        ws.close()

    def on_close(self, ws):
        print('Connection to Slack closed. Reopening...')
        self.up = False
        self.connect()

    def on_open(self, ws):
        print('Connection to Slack established.')

    def connect(self):
        while not self.up:
            try:
                res = rtmStart(token)
                if 'url' in res:
                    self.bank = Bank(res)
                    self._update_members()
                    self.ws = websocket.WebSocketApp(res['url'], on_message=self.on_message,
                                                                 on_error=self.on_error,
                                                                 on_open=self.on_open,
                                                                 on_close=self.on_close)
                    self.ws.run_forever()
                else:
                    # connection error
                    print('Connection error.', res)
            except Exception as e:
                print('Exception caught:', e)
                print('Retrying in 1 second...')
                time.sleep(1)

def main(uptime, queues, **kwargs):
    g.uptime = uptime

    slack = SlackClient()
    slack.connect()
