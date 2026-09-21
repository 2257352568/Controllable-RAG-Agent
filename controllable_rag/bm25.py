"""Small deterministic BM25 implementation for offline retrieval baselines."""

import math
import re
from collections import Counter, defaultdict

TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def tokenize(text):
    return TOKEN_PATTERN.findall(str(text).lower())


class BM25Index:
    def __init__(self, texts, k1=1.5, b=0.75):
        if not texts:
            raise ValueError("BM25 requires at least one document")
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("BM25 requires k1 > 0 and b in [0, 1]")
        self.k1 = float(k1)
        self.b = float(b)
        self.term_frequencies = [Counter(tokenize(text)) for text in texts]
        self.lengths = [sum(frequencies.values()) for frequencies in self.term_frequencies]
        self.average_length = sum(self.lengths) / len(self.lengths)
        document_frequency = defaultdict(int)
        for frequencies in self.term_frequencies:
            for term in frequencies:
                document_frequency[term] += 1
        count = len(texts)
        self.idf = {
            term: math.log(1 + (count - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in document_frequency.items()
        }

    def scores(self, query):
        terms = tokenize(query)
        scores = []
        for frequencies, length in zip(self.term_frequencies, self.lengths):
            normalization = self.k1 * (
                1 - self.b + self.b * length / (self.average_length or 1)
            )
            score = sum(
                self.idf.get(term, 0)
                * frequencies.get(term, 0)
                * (self.k1 + 1)
                / (frequencies.get(term, 0) + normalization)
                for term in terms
                if frequencies.get(term, 0)
            )
            scores.append(score)
        return scores

    def search(self, query, k):
        scores = self.scores(query)
        return sorted(range(len(scores)), key=lambda index: (-scores[index], index))[:k]
