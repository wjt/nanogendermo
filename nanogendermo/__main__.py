# vim: fileencoding=utf-8

import bisect
import codecs
import collections
import itertools
import textblob
import textwrap
import nltk

from nanogendermo.pos import PosTag


def _Create(n):
    klass = collections.namedtuple(n, 'xx xy if_followed_by')

    class _Rule(klass):
        def __new__(cls, xx, xy, if_followed_by=None):
            return klass.__new__(cls, xx, xy, if_followed_by)

        def flip(self):
            return self._replace(xx=self.xy, xy=self.xx)

        def fmap(self, f):
            return self._replace(xx=f(self.xx), xy=f(self.xy))

        pos = frozenset((PosTag.PRP, PosTag.PRP_, PosTag.NN, PosTag.NNS))

    return _Rule


class Exact(_Create('Exact')):
    def matches(r, w): return r.xx == w
    def apply  (r, w): return r.xy

class Prefix(_Create('Prefix')):
    def matches(r, w): return w.startswith(r.xx)
    def apply  (r, w): return r.xy + w[len(r.xx):]

class Suffix(_Create('Suffix')):
    def matches(r, w): return w.endswith(r.xx)
    def apply  (r, w): return w[:-len(r.xx)] + r.xy

class Names(object):
    def __init__(self, xx_xys=None):
        if xx_xys is not None:
            (self.xxs, self.xys) = xx_xys
        else:
            female = nltk.corpus.names.words('female.txt')
            male = nltk.corpus.names.words('male.txt')

            female.sort()
            male.sort()

            self.xxs = [ xx for xx in female if xx not in male ]
            self.xys = [ xy for xy in male if xy not in female ]

    pos = frozenset((PosTag.NNP,))

    def flip(self):
        return Names((self.xys, self.xxs))

    def fmap(self, f):
        return None

    def matches(self, w):
        i = bisect.bisect_left(self.xxs, w)
        return i != len(self.xxs) and self.xxs[i] == w

    def apply(self, w):
        i = bisect.bisect_left(self.xys, w)
        return self.xys[i]


class Mapping(object):
    def __init__(self, rules):
        self.rules = (
            rules +
            filter(None, [r.fmap(str.title) for r in rules]) +
            filter(None, [r.fmap(str.upper) for r in rules])
        )

    def map(self, word, successor):
        for rule in self.rules:
            if word.pos_tag in rule.pos and rule.matches(word):
                replacement = textblob.Word(rule.apply(word), pos_tag=word.pos_tag)
                if replacement == 'hress':
                    continue
                #if replacement.definitions == []:
                #    continue

                #if rule.if_followed_by is None or (
                #    successor is not None and
                #    successor.pos_tag in rule.if_followed_by)

                return {replacement}

        return set()


class BiMapping(object):
    def __init__(self, rules):
        self.xx_xy = Mapping(rules)
        self.xy_xx = Mapping([r.flip() for r in rules])

    def map(self, word, successor):
        candidates = (
            self.xx_xy.map(word, successor) |
            self.xy_xx.map(word, successor))
        return candidates or {word}


mapping = BiMapping([
    # Actually not the case
    Exact('madam', 'sir'),

    Exact('she', 'he'),

    Exact('her', 'his', if_followed_by=frozenset((
        PosTag.NN, PosTag.NNS, PosTag.NNP,
        PosTag.JJ, PosTag.JJR, PosTag.JJS))),
    Exact('her', 'him'),
    Exact('hers', 'his'),

    Exact('herself', 'himself'),

    # TODO: How to disambiguate?
    # Or just build exact matches out of the dictionary
    Suffix('ress', 'er'),
    Suffix('ress', 'or'),

    Prefix('woman', 'man'),
    Exact('women', 'men'),

    Prefix('queen', 'king'),

    Names(),
])

first_paragraph = u'''
To Sherlock Holmes she is always THE woman. I have seldom heard
him mention her under any other name. In his eyes she eclipses
and predominates the whole of her sex. It was not that he felt
any emotion akin to love for Irene Adler. All emotions, and that
one particularly, were abhorrent to his cold, precise but
admirably balanced mind. He was, I take it, the most perfect
reasoning and observing machine that the world has seen, but as a
lover he would have placed himself in a false position. He never
spoke of the softer passions, save with a gibe and a sneer. They
were admirable things for the observer--excellent for drawing the
veil from men's motives and actions. But for the trained reasoner
to admit such intrusions into his own delicate and finely
adjusted temperament was to introduce a distracting factor which
might throw a doubt upon all his mental results. Grit in a
sensitive instrument, or a crack in one of his own high-power
lenses, would not be more disturbing than a strong emotion in a
nature such as his. And yet there was but one woman to him, and
that woman was the late Irene Adler, of dubious and questionable
memory.
'''

def shift_zip(xs):
    return itertools.izip_longest(xs, xs[1:], fillvalue=(None, None))


def swap_paragraph(paragraph):
    b = textblob.TextBlob(paragraph.replace('--', u' – '))
    new_sentences = []
    for sentence in b.sentences:
        new_words = []
        lengths = []
        for (word, pos_tag), (next_word, next_pos_tag) in shift_zip(sentence.pos_tags):
            flipped = '|'.join(mapping.map(word, next_word))

            new_words.append(flipped)
            lengths.append(max(len(x) for x in (word, pos_tag, flipped)))

        #print ' '.join('%*s' % (l, x) for l, (x, t) in zip(lengths, sentence.pos_tags))
        #print ' '.join('%*s' % (l, t) for l, (x, t) in zip(lengths, sentence.pos_tags))
        #print ' '.join('%*s' % (l, y) for l, y      in zip(lengths, new_words))
        #print
        new_sentences.append(' '.join(new_words))

    new_paragraph = '\n'.join(textwrap.wrap('. '.join(new_sentences)))
    return new_paragraph

if __name__ == '__main__':
    with codecs.open('input/pg1661.txt', 'r', 'utf-8') as f:
        first_chapter = '\n'.join(
            itertools.dropwhile(lambda line: not line == 'I.',
                                itertools.takewhile(lambda line: not line == 'II.',
                                                    (line.strip() for line in f))))

        paragraphs = map(swap_paragraph, first_chapter.split('\n\n'))
        print '\n\n'.join(paragraphs)

