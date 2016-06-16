from multiprocessing import Process, Queue
from Bank import g
from config import schema
import time
import Hangups
import Irc

class Monopoly:
    def __init__(self):
        self.irc = None
        self.hangouts = None

        # Ensure database is in sync
        schema.load_schema(g.db, g.cursor)
        schema.migrate(g.db, g.cursor)

        # Start uptime timer
        self.uptime = g.Uptime()

        self.queues = {}
        for process in ['irc', 'hangouts']:
            if g.config[process]['enabled']:
                self.queues[process] = Queue()

    def start(self):
        # Start services
        if not g.config['irc']['enabled'] and not g.config['hangouts']['enabled']:
            print("Hangouts and IRC are both disabled.\n" \
                  "You can configure these options in config/config.json")

        if g.config['irc']['enabled']:
            print("Starting IRC.")
            self.start_irc()

        if g.config['hangouts']['enabled']:
            print("Starting Hangouts integration.")
            self.start_hangouts()

    def start_irc(self):
        self.irc = Process(target=Irc.main, args=(self.uptime, self.queues))
        self.irc.start()

    def start_hangouts(self):
        kwargs = {'log': 'hangups.log',
                  'token_path': 'hangouts_token.txt'}
        self.hangouts = Process(target=Hangups.main,
                                args=(self.uptime, self.queues),
                                kwargs=kwargs)
        self.hangouts.start()

if __name__ == '__main__':
    monopoly = Monopoly()
    monopoly.start()

    while monopoly.irc or monopoly.hangouts:
        if monopoly.irc:
            if not monopoly.irc.is_alive():
                print("IRC has crashed. Restarting...")
                monopoly.start_irc()
        if monopoly.hangouts:
            if not monopoly.hangouts.is_alive():
                print("Hangouts has crashed. Restarting...")
                monopoly.start_hangouts()

        time.sleep(5)
