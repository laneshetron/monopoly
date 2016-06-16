import re
import random
from Bank import g
from Levenshtein import distance
from fuzzywuzzy import process

class Trumpisms:
    def __init__(self):
        self.INDEX_MAX = 50.0
        self.TRUMP_MAX = 5.0
        self.THRESHOLD = 0.2
        self.nl = NaturalLanguage()

        g.cursor.execute('SELECT * FROM trumpisms;')
        self.trumpisms = [x[1] for x in g.cursor.fetchall() ]
        self.lc_trumpisms = [x.lower() for x in self.trumpisms ]
        self.trump_tokens = [self.create_tokens(x) for x in self.lc_trumpisms ]
        self.trump_quotes = dict(enumerate(map(self._rebuild_quote,
            self.trump_tokens)))
        self.rand_trumpisms = []

    def _include(self, word):
        # XXX This is probably not terribly efficient
        g.cursor.execute("SELECT count FROM words_index WHERE word = ?;", (word,))
        index = g.cursor.fetchone()
        g.cursor.execute("SELECT count FROM trumpisms_index WHERE word = ?;",
                         (word,))
        trump_index = g.cursor.fetchone()

        count = index[0] if index else 0
        trump_count = trump_index[0] if trump_index else 0
        return ((count / self.INDEX_MAX) - (trump_count / self.TRUMP_MAX)
            < self.THRESHOLD)

    def _rebuild_quote(self, tokens):
        tokens = [x for x in tokens if self._include(x) ]
        return ' '.join(tokens)

    def create_tokens(self, message):
        tokens = self.nl.tokenize(message)
        tokens = [x for x in tokens if re.search("[a-z0-9]+", x)
            and not x in g.stopwords ]
        return [x for x in tokens if self._include(x) ]

    def score_ngrams(self, a, b):
        unigrams, bigrams = self.nl.common_ngrams(a, b)
        similar = [x for x in self.nl.similar(a, b) if x not in unigrams ]
        score = len(bigrams) * 3 + len(unigrams) * 2 + len(similar)
        return score

    def get_best(self, message):
        message = message.lower()
        tokens = self.create_tokens(message)
        matches = process.extractBests(' '.join(tokens), self.trump_quotes,
                                       score_cutoff=50, limit=3)
        if not matches:
            return None

        if re.search('trump|the donald', message):
            matches = [(x[0], x[1] + 10, x[2]) for x in matches ]

        adjusted = []
        for x in matches:
            b_tokens = self.create_tokens(x[0])
            score = self.score_ngrams(tokens, b_tokens)
            adjusted.append((x[0], x[1] + score, x[2]))
        top = [x for x in adjusted if x[1] == adjusted[0][1] ]
        return top

    def provoke(self, message):
        # output random choice from best matches that exceed threshold
        # otherwise return False
        top = self.get_best(message)
        if top and top[0][1] > 90:
            c = random.choice(top)
            return self.trumpisms[int(c[2])]
        return False

    def trumpism(self):
        if not self.rand_trumpisms:
            self.rand_trumpisms = random.sample(self.trumpisms,
                len(self.trumpisms))
        quote = self.rand_trumpisms.pop()
        return quote

class NaturalLanguage:
    def bigrams(self, s):
        n = len(s)
        ngrams = []
        while n > 1:
            l = s.pop()
            ngrams.append((s[-1], l))
            n -= 1
        return ngrams

    def common_ngrams(self, a, b):
        # Searches set(b) for common ngrams - duplicates in a will be preserved !!!
        # Outputs 2-dimensional tuple as: ((unigrams), (bigrams))
        unigrams = tuple([x for x in a if x in set(b) ])
        bigrams = tuple([x for x in self.bigrams(a) if x in set(self.bigrams(b)) ])
        return unigrams, bigrams

    def similar(self, a, b):
        # Searches set(b) for similar unigrams - duplicates in a will be preserved !!!
        similar = []
        for x in a:
            similar += [y for y in set(b) if distance(x, y) < 3 ]
        return tuple(similar)

    def tokenize(self, s):
        # Adapted from NLTK
        regx = r"""
        (?:[^\W\d_](?:[^\W\d_]|['\-_])+[^\W\d_]) # Words with apostrophes or dashes.
        |
        (?:[+\-]?\d+[,/.:-]\d+[+\-]?)  # Numbers, including fractions, decimals.
        |
        (?:[\w_]+)                     # Words without apostrophes or dashes.
        |
        (?:\.(?:\s*\.){1,})            # Ellipsis dots.
        |
        (?:\S)                         # Everything else that isn't whitespace.
        """
        WORD_RE = re.compile(r"""(%s)""" % regx, re.VERBOSE | re.I
                             | re.UNICODE)
        # WORD_RE performs poorly on these patterns:
        HANG_RE = re.compile(r'([^a-zA-Z0-9])\1{3,}')

        safe_text = HANG_RE.sub(r'\1\1\1', s)
        words = WORD_RE.findall(safe_text)
        return words
