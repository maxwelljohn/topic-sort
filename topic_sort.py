#!/usr/bin/env python -O

import argparse
import nltk
import numpy as np
import pytest
import re

import optimizers
import order_problem

nltk.download('stopwords', quiet=True)
nltk.download('punkt', quiet=True)
nltk.download('wordnet', quiet=True)

PASSAGE_SEPARATOR = "\n\n"
STOPWORDS = set(nltk.corpus.stopwords.words('english'))
STOPWORDS.add('http')
STOPWORDS.add('https')
WORD_RE = re.compile(r'^\w+$')
MAX_NGRAM_N = 3


class TopicSortProblem(order_problem.OrderingProblem):
    def __init__(self, passage_file):
        self.passages = passage_file.read().strip().split(PASSAGE_SEPARATOR)
        super().__init__(len(self.passages))
        self.additions_needed = len(self.passages) - 1
        wnl = nltk.WordNetLemmatizer()
        passage_ngrams = {}
        ngram_document_frequency = nltk.FreqDist()

        for passage in self.passages:
            lemmas = [wnl.lemmatize(t) for t in
                      nltk.word_tokenize(passage.lower())]
            lemmas = [l for l in lemmas if l not in STOPWORDS and
                      re.match(WORD_RE, l)]

            ngrams = []
            for n in range(1, MAX_NGRAM_N+1):
                ngrams.extend(nltk.ngrams(lemmas, n))
            passage_ngrams[passage] = nltk.FreqDist(ngrams)

            unique_ngrams = set(ngrams)
            for ngram in unique_ngrams:
                ngram_document_frequency[ngram] += 1

        for index1, passage1 in enumerate(self.passages):
            for offset, passage2 in enumerate(self.passages[index1+1:]):
                index2 = index1+1 + offset
                ngrams1 = passage_ngrams[passage1]
                ngrams2 = passage_ngrams[passage2]
                similarity_score = 0
                for g in ngrams1:
                    if ngrams2[g] > 0:
                        # TF-IDF weighting
                        similarity_score += (1 + np.log(ngrams1[g])) * \
                            (1 + np.log(ngrams2[g])) * \
                            (np.log(len(self.passages) /
                             ngram_document_frequency[g]))
                # "Costs" are negative; we want similar passages to be close.
                # Scaling by 1000 lets us use a matrix of ints.
                self.costs[index1, index2] = -1000 * similarity_score / \
                    min(len(passage1), len(passage2))


class TopicSortSolution(order_problem.OrderingSolution):
    def __init__(self, problem):
        super().__init__(problem)

    def ensure_completion(self):
        super().ensure_completion()
        assert np.sum(self.edges_added, axis=(0, 1)) == (self.dimension - 1)
        assert np.sum(self.node_degrees == 2, axis=0) == (self.dimension - 2)
        assert np.sum(self.node_degrees == 1, axis=0) == 2

    def add_edge(self, node_a, node_b):
        super().add_edge(node_a, node_b)

        if not self.feasible_edges.any():
            self.finish()
        else:
            self.ensure_validity()

    def __str__(self):
        components = self.components()
        assert len(components) == 1
        traversal_order = components[0]
        return PASSAGE_SEPARATOR.join(
            [self.problem.passages[i] for i in traversal_order]
        ) + '\n'


TopicSortProblem.solution_type = TopicSortSolution


@pytest.fixture
def sample_problem():
    with open('sample_text.txt', 'r') as infile:
        result = TopicSortProblem(infile)
    return result


def test_greedy(sample_problem):
    '''
    Verify the greedy solver produces the correct result on the sample text.
    '''
    soln = optimizers.greedy(sample_problem)
    soln.ensure_completion()
    assert str(soln) == """apples bananas

bananas oranges

oranges pears plums

pears plums
"""


def test_genetic(sample_problem):
    '''
    Verify the genetic solver produces the correct result on the sample text.
    '''
    soln = optimizers.genetic(sample_problem, 20, 20, 1000)
    soln.ensure_completion()
    assert str(soln) == """apples bananas

bananas oranges

oranges pears plums

pears plums
"""


def main(passage_file, slow=False):
    problem = TopicSortProblem(passage_file)
    if slow:
        soln = optimizers.genetic(problem, 20, 20, 1000)
    else:
        soln = optimizers.greedy(problem)
    print(soln)


if __name__ == '__main__':
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "filepath",
        help="path to the file of text passages to sort by topic; - for stdin"
    )
    parser.add_argument(
        '-s', "--slow",
        action='store_true',
        help="sort the file slowly & carefully (quick & dirty is the default)",
    )
    args = parser.parse_args()
    if args.filepath == '-':
        passage_file = sys.stdin
        main(passage_file, args.slow)
    else:
        passage_filepath = args.filepath
        with open(passage_filepath, 'r') as passage_file:
            main(passage_file, args.slow)
