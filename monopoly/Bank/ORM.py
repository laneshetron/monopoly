from Bank import g

class Nick:
    def __init__(self, nick):
        self._nick = nick
        self.db = g.db
        self.cursor = g.cursor
        self._id = None
        self._karma = None
        self._get()

    def _get(self):
        self.cursor.execute(
            "SELECT * FROM monopoly WHERE nick = ? COLLATE NOCASE LIMIT 1", (self.nick,))
        data = self.cursor.fetchone()
        if data is not None:
            self._id, self._nick, self._karma = data
        else:
            self.cursor.execute("INSERT INTO monopoly(nick, karma) VALUES(?, ?)",
                (self.nick, 0))
            self.db.commit()

            self._id = self.cursor.lastrowid
            self._karma = 0

    def set_karma(self, amount):
        self.cursor.execute("UPDATE monopoly SET karma = ? WHERE id = ?",
            (amount, self.id))
        self.db.commit()
        self._karma = amount

    # Ensure properties cannot be set manually
    @property
    def id(self):
        return self._id

    @property
    def nick(self):
        return self._nick

    @property
    def karma(self):
        return self._karma

class Channel:
    def __init__(self, name=None, channel_id=None):
        self.db = g.db
        self.cursor = g.cursor
        self._name = name if name else ''
        self._channel_id = channel_id
        self._id = None
        self._mute_level = 1
        self._lottery_updates = 0
        self._get()

    def _get(self):
        if self.channel_id:
            self.cursor.execute(
                "SELECT * FROM channels WHERE channel_id = ? COLLATE NOCASE LIMIT 1",
                (self.channel_id,))
        else:
            self.cursor.execute("SELECT * FROM channels WHERE name = ? COLLATE NOCASE LIMIT 1",
                (self.name,))
        data = self.cursor.fetchone()

        if data is not None:
            self._id, self._channel_id, self._name, self._mute_level, self._lottery_updates = data
        else:
            if self.channel_id:
                self.cursor.execute("INSERT INTO channels(name, channel_id) VALUES (?, ?)",
                    (self.name, self.channel_id))
            else:
                self.cursor.execute("INSERT INTO channels(name) VALUES (?)", (self.name,))
            self.db.commit()
            self._id = self.cursor.lastrowid

    def set_name(self, name):
        self.cursor.execute("UPDATE channels SET name = ? WHERE id = ?", (name, self.id))
        self.db.commit()
        self._name = name

    def set_mute(self, level):
        self.cursor.execute("UPDATE channels SET mute_level = ? WHERE id = ?", (level, self.id))
        self.db.commit()
        self._mute_level = level

    def mute(self):
        self.set_mute(2)

    def softmute(self):
        self.set_mute(1)

    def unmute(self):
        self.set_mute(0)

    @property
    def id(self):
        return self._id

    @property
    def channel_id(self):
        return self._channel_id

    @property
    def name(self):
        return self._name

    @property
    def mute_level(self):
        return self._mute_level

    @property
    def lottery_updates(self):
        return self._lottery_updates

class Transaction:
    def __init__(self, sender, receiver):
        self.db = g.db
        self.cursor = g.cursor
        self.sender = Nick(sender)
        self.receiver = Nick(receiver)
        self._positive = 0
        self._negative = 0
        self._get()

    def _get(self):
        self.cursor.execute(
            "SELECT * FROM analytics WHERE sid = ? AND rid = ? COLLATE NOCASE LIMIT 1",
            (self.sender.id, self.receiver.id))
        data = self.cursor.fetchone()
        if data is not None:
            self._positive = data[2]
            self._negative = data[3]
        else:
            self.cursor.execute("INSERT INTO analytics(sid, rid, positive, negative) VALUES(?, ?, ?, ?)",
                (self.sender.id, self.receiver.id, 0, 0))
            self.db.commit()

    def set_positive(self, amount):
        self.cursor.execute("UPDATE analytics SET positive = ? WHERE sid = ? AND rid = ?",
            (amount, self.sender.id, self.receiver.id))
        self.db.commit()
        self._positive = amount

    def set_negative(self, amount):
        self.cursor.execute("UPDATE analytics SET negative = ? WHERE sid = ? AND rid = ?",
            (amount, self.sender.id, self.receiver.id))
        self.db.commit()
        self._negative = amount

    def transact(self, change):
        karma = self.receiver.karma + change
        self.receiver.set_karma(karma)
        if change > 0:
            positive = self.positive + change
            self.set_positive(positive)
        elif change < 0:
            negative = self.negative + abs(change)
            self.set_negative(negative)

    @property
    def positive(self):
        return self._positive

    @property
    def negative(self):
        return self._negative

class Analytics:
    def __init__(self, clients, limit=None):
        self.clients = clients
        self.limit = limit
        self.db = g.db
        self.cursor = g.cursor

    def _ratio(self, sr, positive=True):
        positivity = "positive" if positive else "negative"
        limit = "LIMIT {0}".format(self.limit) if self.limit else ""
        self.cursor.execute(
            "SELECT id, nick, SUM(positive), SUM(negative), (SUM(CAST({0} AS float)) /" \
            "(SUM(CAST(positive AS float)) + SUM(CAST(negative AS float))) * 100) AS ratio " \
            "FROM monopoly JOIN analytics ON id={1} WHERE nick IN ({2}) " \
            "COLLATE NOCASE GROUP BY id ORDER BY ratio DESC {3}".format(
            positivity, sr, ','.join('?'*len(self.clients)), limit), self.clients)
        data = self.cursor.fetchall()
        results = []
        for row in data:
            if round(row[4]) > 0:
                results.append([row[1], round(row[4])])
        return results

    @property
    def top_givers(self):
        return self._ratio('sid')

    @property
    def top_takers(self):
        return self._ratio('sid', False)

    @property
    def top_loved(self):
        return self._ratio('rid')

    @property
    def top_hated(self):
        return self._ratio('rid', False)
