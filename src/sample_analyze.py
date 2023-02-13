from __future__ import annotations
from typing import List

from utils import Card_,multiple_list_comparaison,remove_same_indexes,Direction,PlayerHand,Suit

class SampleAnalyzer() :
    def __init__(self, samples : List[PlayerHand]) -> None:
        self.n_samples = len(samples)
        self.min_hcp = min([sample.hcp() for sample in samples])
        self.max_hcp = max([sample.hcp() for sample in samples])
        self.average_hcp = sum([sample.hcp() for sample in samples])/len(samples)
        self.min_length = {s:min([len(sample.suits[s]) for sample in samples]) for s in Suit}
        self.max_length = {s:max([len(sample.suits[s]) for sample in samples]) for s in Suit}
        self.average_length = {s:sum([len(sample.suits[s]) for sample in samples])/len(samples) for s in Suit}

    def update(self, samples  : List[PlayerHand]) -> None :
        self.min_hcp = min(min([sample.hcp() for sample in samples]),self.min_hcp)
        self.max_hcp = max(max([sample.hcp() for sample in samples]),self.max_hcp)
        self.average_hcp = sum([sample.hcp() for sample in samples])/len(samples)
        self.min_length = {s:min([len(sample.suits[s]) for sample in samples]) for s in Suit}
        self.max_length = {s:max([len(sample.suits[s]) for sample in samples]) for s in Suit}
        self.average_length = {s:sum([len(sample.suits[s]) for sample in samples])/len(samples) for s in Suit}
        self.n_samples += len(samples)

    def __str__(self) -> str:
        return str(self.__dict__)