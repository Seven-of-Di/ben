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

DEFAULT_MODEL_CONF = os.path.join(os.path.dirname(os.getcwd()), 'default.conf')
MODELS = Models.from_conf(conf.load(DEFAULT_MODEL_CONF))


class BidExplanations():
    """Contains the explanation for a given bid
    """

    def __init__(self, sample : PlayerHand) -> None:
        self.n_samples = 1
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

    def update(self, sample : PlayerHand) -> None:
        self.n_samples += 1
        self.min_hcp = min(sample.hcp(), self.min_hcp)
        self.max_hcp = max(sample.hcp(), self.max_hcp)
        self.min_length = {s: min(len(sample.suits[s]), self.min_length[s]) for s in Suit}
        self.max_length = {s: max(len(sample.suits[s]), self.max_length[s]) for s in Suit}
        self.fill_distribution_dict(sample)

    def __str__(self) -> str:
        return str(self.__dict__)
    
    def __repr__(self) -> str:
        return str(self.__dict__)


@dataclass
class BidPosition:
    sequence: List[str]
    our_side_vul: bool
    their_side_vul: bool

    def __hash__(self) :
        return hash(repr(self))

start = time.time()
nn_time = 0
dict_of_alerts : Dict[BidPosition,BidExplanations]= {}
for i in range(100) :
    diag = Diag.generate_random()
    auction = []
    vuls = [True, False]
    while not bidding.auction_over(auction):
        nn_start = time.time()
        auction.append(BotBid(vuls, diag.hands[Direction(
            len(auction) % 4)].to_pbn(), MODELS).restful_bid(auction).bid)
        position = BidPosition(auction,vuls[(len(auction)+1)%2],vuls[len(auction)%2])
        nn_end = time.time()
        nn_time += nn_end-nn_start
        if position in dict_of_alerts and dict_of_alerts[position].n_samples>=1000:
            continue
        if position not in dict_of_alerts :
            dict_of_alerts[position]=BidExplanations(diag.hands[Direction(
            len(auction) % 4)])
        else :
            dict_of_alerts[position].update(diag.hands[Direction(len(auction) % 4)])
    
end = time.time()
print(end-start)
print(nn_time)

# for bid_position,alert in dict_of_alerts.items() :
#     print(bid_position)
#     print(alert)
#     print("---")
