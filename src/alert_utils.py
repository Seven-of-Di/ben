from __future__ import annotations
from dataclasses import dataclass
import time
from bots import BotBid
from typing import Dict, List
from bidding import bidding
from nn.models import Models
import conf
import os


from utils import Card_, multiple_list_comparaison, remove_same_indexes, Direction, PlayerHand, Suit, Diag

# DEFAULT_MODEL_CONF = os.path.join(os.path.dirname(os.getcwd()), 'default.conf')
# HUMAN_MODEL_CONF = os.path.join(os.path.dirname(os.getcwd()), 'human.conf')
# MODELS_HUMAN = Models.from_conf(conf.load(HUMAN_MODEL_CONF))
# MODELS_GIB = Models.from_conf(conf.load(DEFAULT_MODEL_CONF))


class BidExplanations():
    """Contains the explanation for a given bid
    """

    def __init__(self, sample: PlayerHand) -> None:
        self.n_samples = 1
        self.samples = [sample.to_pbn()]
        self.min_hcp: int = sample.hcp()
        self.max_hcp: int = sample.hcp()
        self.hcp_distribution: Dict[int, int] = {i: 0 for i in range(38)}
        self.min_length: Dict[Suit, int] = {
            s: len(sample.suits[s]) for s in Suit}
        self.max_length: Dict[Suit, int] = {
            s: len(sample.suits[s]) for s in Suit}
        self.length_distribution: Dict[Suit, Dict[int, int]] = {
            s: {i: 0 for i in range(14)} for s in Suit}
        self.fill_distribution_dict(sample)

    def fill_distribution_dict(self, sample: PlayerHand):
        self.hcp_distribution[sample.hcp()] += 1
        for suit in Suit:
            self.length_distribution[suit][len(sample.suits[suit])] += 1

    def update(self, sample: PlayerHand) -> None:
        self.n_samples += 1
        self.samples.append(sample.to_pbn())
        self.min_hcp = min(sample.hcp(), self.min_hcp)
        self.max_hcp = max(sample.hcp(), self.max_hcp)
        self.min_length = {
            s: min(len(sample.suits[s]), self.min_length[s]) for s in Suit}
        self.max_length = {
            s: max(len(sample.suits[s]), self.max_length[s]) for s in Suit}
        self.fill_distribution_dict(sample)

    def __str__(self) -> str:
        return str(self.__dict__)

    def __repr__(self) -> str:
        return str(self.samples)
    
    def to_json(self) :
        pass


@dataclass
class BidPosition:
    sequence: List[str]
    vuls: List[bool]

    def __hash__(self):
        return hash(repr(self))


    def to_dict(self):
        return {
            "sequence": self.sequence,
            "vuls": self.vuls,
        }
