# vim: fileencoding=utf-8

import bisect
import cPickle as pickle
import codecs
import collections
import errno
import itertools
import logging
import nltk
import textblob
import textwrap

from textblob.utils import PUNCTUATION_REGEX

from nanogendermo.pos import PosTag
from nanogendermo.nounmapping import rough_mapping


log = logging.getLogger(__name__)


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


def remove_all(l, to_remove):
    return [ x for x in l if x not in to_remove ]


class Names(object):
    def __init__(self, exclude=[], xx_xys=None):
        if xx_xys is not None:
            (self.xxs, self.xys) = xx_xys
        else:
            female = nltk.corpus.names.words('female.txt')
            male = nltk.corpus.names.words('male.txt')

            female.sort()
            male.sort()

            self.xxs = remove_all(female, male + exclude)
            self.xys = remove_all(male, female + exclude)

    pos = frozenset((PosTag.NNP,))

    def flip(self):
        return Names(xx_xys=(self.xys, self.xxs))

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
            filter(None, [r.fmap(lambda x: x.title()) for r in rules]) +
            filter(None, [r.fmap(lambda x: x.upper()) for r in rules])
        )

    def map(self, original_word, successor):
        if original_word.pos_tag == PosTag.NNS:
            word = original_word.singularize()
            word.pos_tag = PosTag.NN
        else:
            word = original_word

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

                if original_word.pos_tag == PosTag.NNS:
                    return { replacement.pluralize() }
                else:
                    return { replacement }

        return set()


class BiMapping(object):
    def __init__(self, rules):
        self.xx_xy = Mapping(rules)
        self.xy_xx = Mapping([r.flip() for r in rules])

    def map(self, word, successor):
        candidates = (
            self.xx_xy.map(word, successor) |
            self.xy_xx.map(word, successor))
        return candidates


static_rules = [
    # Actually not the case
    Exact('madam', 'sir'),
    Exact('Mrs', 'Mr'),
    Exact('Miss', 'Mister'),

    Exact('she', 'he'),

    Exact('her', 'his', if_followed_by=frozenset((
        PosTag.NN, PosTag.NNS, PosTag.NNP,
        PosTag.JJ, PosTag.JJR, PosTag.JJS))),
    Exact('her', 'him'),
    Exact('hers', 'his'),

    Exact('herself', 'himself'),

    Exact('woman', 'man'),
    Exact('female', 'male'),
    # Suffix('woman', 'man'),
    # Exact('women', 'men'),

    # bzzt, person -> perdaughter
    # Suffix('daughter', 'son'),
    Exact('daughter', 'son'),
    Exact('girl', 'boy'),

    Prefix('queen', 'king'),

    # A little disappointing that the WordNet-derived rules don't generate this.
    Exact('Countess', 'Count'),
    Exact('Princess', 'Prince'),
    Exact('gentlewoman', 'gentleman'),
    Exact('sister', 'brother'),

    Names(exclude=['Sherlock', 'King', 'Von', 'Prince']),
]


def generate_rules():
    cache_filename = 'wordnet-rules.pickle'
    try:
        with open(cache_filename, 'rb') as f:
            log.info("Loading cached rules from %s", cache_filename)
            return pickle.load(f)
    except IOError as e:
        if e.errno != errno.ENOENT: raise

        log.info("Generating rules from WordNet")
        rules = [
            Exact(femme_lemma, other_lemma)
            for femme_lemma, other_lemmas in rough_mapping()
            for other_lemma in other_lemmas
        ]

        with open(cache_filename, 'wb') as f:
            log.info("Caching rules to %s", cache_filename)
            pickle.dump(rules, f, pickle.HIGHEST_PROTOCOL)

        return rules


def shift_zip(xs):
    return itertools.izip_longest(xs, xs[1:], fillvalue=(None, None))


class Substitution(collections.namedtuple('Substitution', 'old new')):
    pass


def swap_paragraph(mapping, paragraph):
    b = textblob.TextBlob(paragraph.replace('--', u' – '))
    new_sentences = []

    for sentence in b.sentences:
        new_words = []
        lengths = []

        # Inlined to exclude 'if not PUNCTUATION_REGEX.match(unicode(t))]'
        sentence_pos_tags = [
            (textblob.Word(word, pos_tag=t), unicode(t))
            for word, t in sentence.pos_tagger.tag(sentence.raw)
        ]
        for (word, pos_tag), (next_word, next_pos_tag) in shift_zip(sentence_pos_tags):
            replacements = mapping.map(word, next_word)
            if replacements:
                new_word = Substitution(word, '|'.join(replacements))
            else:
                new_word = word

            new_words.append(new_word)
            lengths.append(max(len(x) for x in (word, pos_tag, new_word)))

            # TODO: remove whitespace around punctuation.

        #print ' '.join('%*s' % (l, x) for l, (x, t) in zip(lengths, sentence.pos_tags))
        #print ' '.join('%*s' % (l, t) for l, (x, t) in zip(lengths, sentence.pos_tags))
        #print ' '.join('%*s' % (l, y) for l, y      in zip(lengths, new_words))
        #print
        new_sentences.append(new_words)

    return reassemble(new_sentences)


def reassemble(sentences):
    at_start = True


    in_dquote = False
    buf = []

    for sentence in sentences:
        for fragment in sentence:
            if fragment == '"':
                if in_dquote:
                    in_dquote = False
                else:
                    if not at_start:
                        buf.append(' ')

                    at_start = True
                    in_dquote = True
            elif not PUNCTUATION_REGEX.match(unicode(fragment)) and not at_start:
                buf.append(' ')
            else:
                at_start = False

            if isinstance(fragment, Substitution):
                buf.append('<del>{}</del><ins>{}</ins>'.format(*fragment))
            else:
                buf.append(fragment)

    return ''.join(buf)


def lines_between(lines, a, b):
    return itertools.dropwhile(lambda line: not line.startswith(a),
                               itertools.takewhile(lambda line: not line.startswith(b),
                                                   (line.rstrip() for line in lines)))


header = u'''
<!DOCTYPE html>
<html class="hide-deletions">
    <head>
        <meta charset="utf-8">
        <style>
            .hide-deletions del {
                display: none;
            }
        </style>
    </head>
    <body>
'''

footer = u'''
    </body>
</html>
'''


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(name)s %(message)s',
                       )

    wordnet_rules = generate_rules()

    log.info("Building mapping")
    mapping = BiMapping(static_rules + wordnet_rules)

    log.info("Slurping up some text")
    with codecs.open('input/pg1661.txt', 'r', 'utf-8') as f:
        with codecs.open('output/pg1661.html', 'w', 'utf-8') as g:
            lines = lines_between(f, 'ADVENTURE I.', 'ADVENTURE II.')
            first_chapter = '\n'.join(lines)
            log.info('%s characters', len(first_chapter))

            paragraphs = first_chapter.split('\n\n')
            swapped_paragraphs = [ swap_paragraph(mapping, p) for p in paragraphs ]
            g.write(header)
            for paragraph in swapped_paragraphs:
                g.write(u'<p>{}</p>\n\n'.format(paragraph))
            g.write(footer)
