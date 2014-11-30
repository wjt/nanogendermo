# vim: fileencoding=utf-8

import textblob
import itertools
import codecs
import pprint
from operator import itemgetter

from nltk.corpus import wordnet
from nltk.metrics.distance import edit_distance


def patriarchy(word_ending_ess):
    w = textblob.Word(word_ending_ess)
    return {
        (lemma_name, ess_synset.lexname(), any(x in ess_synset.definition() for x in ('woman', 'girl', 'female')))
        for ess_synset in w.synsets
        if ess_synset.lexname() == u'noun.person'
        for ess_hyp_nym in ess_synset.hypernyms() + ess_synset.hyponyms()
        for lemma_name in ess_hyp_nym.lemma_names()
        if lemma_name != word_ending_ess
        if len(lemma_name) < len(word_ending_ess)
        if len(list(itertools.takewhile(lambda t: t[0] == t[1],
                                        zip(word_ending_ess, lemma_name)))) >= 3
    }

# er -> ess needs to be pre-computed

# Failing
# countess - 'count.n.03' not in any of its nyms?
# trampess - doesn't have tramp.n.01
# barmaid?
# handmaid?
# widow/widower
# hostess…

# In [367]: gentleman = textblob.Word('gentleman').synsets[0]
# 
# In [368]: gentlewoman = textblob.Word('gentlewoman').synsets[0]
# 
# In [369]: gentleman.lowest_common_hypernyms(gentlewoman)
# Out[369]: [Synset('adult.n.01')]
#
# Just do this by hand?

def scrape():
    with codecs.open('/usr/share/dict/words', 'r', 'utf-8') as f:
        for word in itertools.imap(unicode.strip, f):
            if word.endswith(u'ess'):
                er = patriarchy(word)
                if er:
                    print u'{} -> {}'.format(word, er)


def rough_mapping():
    noun_person_feminine = (
        synset
        for synset in wordnet.all_synsets(wordnet.NOUN)
        if synset.lexname() == u'noun.person'
        if any(x in synset.definition() for x in ('woman', 'girl', 'female'))
    )
    # for n in noun_person_feminine:
    #     print u'{} ({}) ({}): {}'.format(
    #         n,
    #         ', '.join(n.lemma_names()),
    #         {h: h.lemma_names() for h in n.hypernyms()},
    #         n.definition())

    def single_word_lemma_names(synset):
        return [x for x in synset.lemma_names() if '_' not in x]

    snth = {}

    for femme_synset in noun_person_feminine:
        for hyper_synset in femme_synset.hypernyms():
            femme_lemmas = single_word_lemma_names(femme_synset)
            hyper_lemmas = single_word_lemma_names(hyper_synset)

            # eg spokeswoman has hypernym spokesperson and sibling spokesman.
            sibling_lemmas = []
            for sibling_synset in hyper_synset.hyponyms():
                if sibling_synset != femme_synset:
                    sibling_lemmas.extend(single_word_lemma_names(sibling_synset))

            if 'goddess' in femme_lemmas:
                import pdb; pdb.set_trace()

            if not femme_lemmas or not (hyper_lemmas + sibling_lemmas): continue

            if any(hyper_lemma in femme_synset.definition()
                   for hyper_lemma in hyper_lemmas):
                # Pair up each lemma for the female-gendered synset with its closest match
                # in the ungendered or masculine-gendered synset
                for femme_lemma in femme_lemmas:
                    candidates = [
                        (dist, hyper_lemma)
                        for hyper_lemma in (hyper_lemmas + sibling_lemmas)
                        for dist in (edit_distance(femme_lemma, hyper_lemma),)
                        if hyper_lemma != femme_lemma
                        # dist(goddess, god) == 4 > len(god)
                        if (femme_lemma.startswith(hyper_lemma) or
                            dist < min(len(femme_lemma), len(hyper_lemma)))
                        if femme_lemma.istitle() == hyper_lemma.istitle()
                    ]
                    snth.setdefault(femme_lemma, []).extend(candidates)

    # (u'sculptress', [(3, u'sculpturer'), (4, u'sculptor'), (8, u'carver')])
    # bit unfortunate              ^^^^
    for femme_lemma, candidates in sorted(snth.items()):
        if not candidates: continue
        candidates.sort()
        dist, lemmas = next(itertools.groupby(candidates, itemgetter(0)))
        if dist <= 4:
            yield femme_lemma, { other_lemma for (_, other_lemma) in lemmas }


def go():
    for femme_lemma, other_lemmas in rough_mapping():
        pprint.pprint((femme_lemma, other_lemmas))


if __name__ == '__main__':
    go()
