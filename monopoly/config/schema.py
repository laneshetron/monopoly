# Monopoly SQLite Schema
#
# Created on 11/12/15 by Lane Shetron

import os

class MigrationNotFoundError(FileNotFoundError):
    '''Raise when a required migration file could not be found.'''
    def __init__(self, *args):
        super().__init__(2, 'No such migration', *args)

def load_schema(db, cursor):
    cursor.executescript('''
    CREATE TABLE IF NOT EXISTS
        monopoly(id INTEGER PRIMARY KEY AUTOINCREMENT,
                 nick TEXT,
                 karma INTEGER);

    CREATE TABLE IF NOT EXISTS
        subscribers(id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    conv_id TEXT);

    CREATE TABLE IF NOT EXISTS
        trumpisms(id INTEGER PRIMARY KEY AUTOINCREMENT,
                  quote TEXT);

    CREATE TABLE IF NOT EXISTS
        words_index(word TEXT PRIMARY KEY,
                    count INTEGER);

    CREATE INDEX IF NOT EXISTS
        index_on_words ON words_index (word, count);

    CREATE TABLE IF NOT EXISTS
        trumpisms_index(word TEXT PRIMARY KEY,
                        count INTEGER);

    CREATE INDEX IF NOT EXISTS
        index_on_trumpisms ON trumpisms_index (word, count);

    CREATE TABLE IF NOT EXISTS
        schema_migrations(version INTEGER PRIMARY KEY);
    ''')
    db.commit()

def migrate(db, cursor):
    # Migrations must be explicitly listed here (in order!) to be run
    migrations = {
        1: 'migrations/1-WordsIndex.sql',
        2: 'migrations/2-TrumpismsIndex.sql',
        3: 'migrations/3-TrumpQuotes.sql' }

    cursor.execute('SELECT * FROM schema_migrations;')
    versions = cursor.fetchall()
    root = os.path.dirname(os.path.realpath(__file__))

    for x in range(1, len(migrations) + 1):
        if x not in [x for y in versions for x in y]:
            fname = os.path.join(root, migrations[x])
            if os.path.isfile(fname):
                with open(fname, 'r') as f:
                    try:
                        for line in f:
                            cursor.execute(line)
                        cursor.execute('INSERT INTO schema_migrations'
                                       '(version) VALUES (?);', (x,))
                        db.commit()
                    except Exception as e:
                        db.rollback()
                        raise e
            else:
                raise MigrationNotFoundError(fname)
