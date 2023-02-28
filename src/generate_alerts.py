from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
import time
from bots import BotBid
from typing import Dict, List
from bidding import bidding
from nn.models import Models
import conf
import os
from utils import Card_, multiple_list_comparaison, remove_same_indexes, Direction, PlayerHand, Suit, Diag
from alert_utils import BidExplanations, BidPosition
import asyncio
import pickle
import random


DEFAULT_MODEL_CONF = os.path.join(os.path.dirname(os.getcwd()), 'default.conf')
MODELS_GIB = Models.from_conf(conf.load(DEFAULT_MODEL_CONF))


def background(f):
    def wrapped(*args, **kwargs):
        return asyncio.get_event_loop().run_in_executor(None, f, *args, **kwargs)

    return wrapped


diags = [Diag.generate_random() for _ in range(100)]


def bid_and_extract_hand(diag: Diag, dict_of_alerts: Dict[BidPosition, BidExplanations]):
    # vuls = [bool(random.getrandbits(1)), bool(random.getrandbits(1))]
    vuls = [False,False]
    auction = []
    bidder_bots: List[BotBid] = [BotBid(
        vuls, diag.hands[dir].to_pbn(), MODELS_GIB) for dir in Direction]
    while not bidding.auction_over(auction):
        nn_start = time.time()
        current_direction: Direction = Direction(len(auction) % 4)
        auction.append(bidder_bots[current_direction.value].bid(auction).bid)
        position = BidPosition(
            deepcopy(auction), vuls)
        nn_end = time.time()
        if position in dict_of_alerts and dict_of_alerts[position].n_samples >= 1000:
            continue
        if position not in dict_of_alerts:
            dict_of_alerts[position] = BidExplanations(deepcopy(diag.hands[current_direction]))
        else:
            dict_of_alerts[position].update(
                deepcopy(diag.hands[current_direction]))

def generate_alerts(check_point: int):
    dict_of_alerts: Dict[BidPosition, BidExplanations] = {}

    with open('alerts', 'rb') as f:
        dict_of_alerts = pickle.load(f)

    while True:
        start = time.time()
        diags = [Diag.generate_random() for _ in range(check_point)]
        for i in range(check_point):
            bid_and_extract_hand(diags[i], dict_of_alerts)
        end = time.time()
        print('{} diags alerts saved in {} seconds. Current number of sequence {}'.format(check_point, end-start, len(dict_of_alerts)))
        with open('alerts', 'wb') as f:
            pickle.dump(dict_of_alerts, f, pickle.HIGHEST_PROTOCOL)


if __name__ == "__main__":
    generate_alerts(100)
