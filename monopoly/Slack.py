from Bank import g
import websocket
import requests
import json

domain = 'https://slack.com'
endpoint = 'api/rtm.start'

token = ''

url = '{0}/{1}?token={2}&simple_latest=true&no_unreads=true'.format(domain, endpoint, token)

class SlackClient:
    def __init__(self):
        self.up = False

    def on_message(self, ws, message):
        message = json.loads(message)
        if message['type'] == 'hello':
            self.up = True
        elif message['type'] == 'error':
            print('Error encountered: {0}'.format(message['error']))

    def on_error(self, ws, error):
        print(error)

    def on_close(self, ws):
        print('Connection to Slack closed. Reopening...')
        self.up = False
        self.connect()

    def on_open(self, ws):
        print('Connection to Slack established.')

    def connect(self):
        res = requests.get(url).json()
        if 'url' in res:
            ws = websocket.WebSocketApp(res['url'], on_message=self.on_message,
                                                    on_error=self.on_error,
                                                    on_open=self.on_open,
                                                    on_close=self.on_close)
            ws.run_forever()
        else:
            # connection error
            print('connection error')

def main(uptime, queues, **kwargs):
    g.uptime = uptime

    slack = SlackClient()
    slack.connect()
