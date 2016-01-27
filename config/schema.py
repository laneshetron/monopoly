# Monopoly SQLite Schema
#
# Created on 11/12/15 by Lane Shetron

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
    ''')
    db.commit()
