from Bank import g
import websocket
import requests
import time
import json

domain = 'https://slack.com'
endpoint = 'api/rtm.start'

token = ''

url = '{0}/{1}?token={2}&simple_latest=true&no_unreads=true'.format(domain, endpoint, token)

class SlackClient:
    def __init__(self):
        self.up = False
        self.ws = None

    def send(self, text, channel):
        if self.ws:
            message = json.dumps({'id': 1, 'type': 'message', 'channel': channel, 'text': text})
            self.ws.send(message)
        else:
            raise Exception('No websocket available.')

    def on_message(self, ws, message):
        message = json.loads(message)
        print(message)
        if 'type' in message:
            if message['type'] == 'hello':
                self.up = True
            elif message['type'] == 'error':
                print('Error encountered: {1}'.format(message['error']))
            elif message['type'] == 'message' and 'reply_to' not in message:
                # Consume message
                print(message['text'])

    def on_error(self, ws, error):
        print(error)
        self.connect()

    def on_close(self, ws):
        print('Connection to Slack closed. Reopening...')
        self.up = False
        self.connect()

    def on_open(self, ws):
        print('Connection to Slack established.')

    def connect(self):
        while not self.up:
            try:
                res = requests.get(url).json()
                if 'url' in res:
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