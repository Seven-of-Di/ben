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
from utils import Direction, PlayerHand, Suit, Diag
from alert_utils import BidExplanations, BidPosition
import pickle


DEFAULT_MODEL_CONF = os.path.join(os.path.dirname(os.getcwd()), 'default.conf')
MODELS_GIB = Models.from_conf(conf.load(DEFAULT_MODEL_CONF))


diags = [Diag.generate_random() for _ in range(100)]


def bid_and_extract_hand(diag: Diag, dict_of_alerts: Dict[BidPosition, BidExplanations]):
    # vuls = [bool(random.getrandbits(1)), bool(random.getrandbits(1))]
    vuls = [False, False]
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
            dict_of_alerts[position] = BidExplanations(
                deepcopy(diag.hands[current_direction]))
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
        print('{} diags alerts saved in {} seconds. Current number of sequence {}'.format(
            check_point, end-start, len(dict_of_alerts)))
        with open('alerts', 'wb') as f:
            pickle.dump(dict_of_alerts, f, pickle.HIGHEST_PROTOCOL)


def generate_usual_alert_from_dict(dic: Dict, ascending: bool) -> int:
    TRESHOLD = (5/100)*sum(dic.values())
    tuples_list = dic.items() if ascending else reversed(dic.items())
    cumulative_sum = 0
    for tested_key, occurences in tuples_list:
        cumulative_sum += occurences
        if cumulative_sum >= TRESHOLD:
            return tested_key
    raise Exception(
        "Treshold should be reached at some point, something fishy is going on. dict : {dic}".format(dic))


def generete_hcp_alert(bid_explanation: BidExplanations) -> str:
    strict_minimum_hcp = bid_explanation.min_hcp
    strict_maximum_hcp = bid_explanation.max_hcp
    usual_minimum_hcp = generate_usual_alert_from_dict(
        bid_explanation.hcp_distribution, ascending=True)
    usual_maximum_hcp = generate_usual_alert_from_dict(
        bid_explanation.hcp_distribution, ascending=False)
    minimum_text = str(strict_minimum_hcp) if strict_minimum_hcp == usual_minimum_hcp else "({}){}".format(
        strict_minimum_hcp, usual_minimum_hcp)
    maximum_text = str(strict_maximum_hcp) if strict_maximum_hcp == usual_maximum_hcp else "({}){}".format(
        usual_maximum_hcp, strict_maximum_hcp)
    return "{}-{}hcp".format(minimum_text, maximum_text)


def generate_suit_length_alert_as_dict(bid_explanation: BidExplanations, suit: Suit) -> Dict:
    strict_min_length = bid_explanation.min_length[suit]
    strict_max_length = bid_explanation.max_length[suit]
    suit_length_distribution = bid_explanation.length_distribution[suit]
    usual_min_length = generate_usual_alert_from_dict(
        suit_length_distribution, ascending=True)
    usual_max_length = generate_usual_alert_from_dict(
        suit_length_distribution, ascending=False)

    return {
        "strict_min_length": strict_min_length,
        "usual_min_length": usual_min_length,
        "strict_max_length": strict_max_length,
        "usual_max_length": usual_max_length,
    }


def print_suit_max_length(usual_max_length: int, strict_max_length: int, usual_min_length: int, strict_min_length: int, suit: Suit) -> str:
    max_parenthesis = usual_max_length != strict_max_length
    min_parenthesis = usual_min_length != strict_min_length
    if min_parenthesis and max_parenthesis:
        return "({}){}-{}({})!{}|".format(strict_min_length, usual_min_length, usual_max_length, strict_max_length, suit.abbreviation())
    if min_parenthesis:
        return "({}){}-{}!{}|".format(strict_min_length, usual_min_length, usual_max_length, suit.abbreviation())
    if max_parenthesis:
        return "{}-{}({})!{}|".format(usual_min_length, usual_max_length, strict_max_length, suit.abbreviation())
    if usual_max_length == usual_min_length:
        return "{}!{}|".format(strict_max_length, suit.abbreviation())
    return "{}-{}!{}|".format(strict_min_length, strict_max_length, suit.abbreviation())


def print_suit_min_length(usual_min_length: int, strict_min_length: int, suit: Suit) -> str:
    min_parenthesis = usual_min_length != strict_min_length
    if min_parenthesis:
        return "({}){}+!{}|".format(strict_min_length, usual_min_length, suit.abbreviation())
    return "{}+!{}|".format(usual_min_length, suit.abbreviation())


def generate_suits_length_alert(bid_explanation: BidExplanations) -> str:
    suits_length_alert_as_dict = {
        s: generate_suit_length_alert_as_dict(bid_explanation, s) for s in Suit}
    text = ""
    for s in Suit:
        print_max_length = suits_length_alert_as_dict[s]["strict_max_length"] < 4
        print_min_length = suits_length_alert_as_dict[s]["usual_min_length"] > 3
        if print_max_length:
            text += print_suit_max_length(usual_max_length=suits_length_alert_as_dict[s]["usual_max_length"], strict_max_length=suits_length_alert_as_dict[s]["strict_max_length"],
                                          usual_min_length=suits_length_alert_as_dict[s]["usual_min_length"], strict_min_length=suits_length_alert_as_dict[s]["strict_min_length"], suit=s)
        elif print_min_length:
            text += print_suit_min_length(usual_min_length=suits_length_alert_as_dict[s]["usual_min_length"],strict_min_length=suits_length_alert_as_dict[s]["strict_min_length"],suit=s)
    text = text[:-1] if text else text

    return "{}".format(text)


def generate_alert_from_bid_explanation(bid_explanation: BidExplanations) -> Dict:
    print(bid_explanation.samples)
    if bid_explanation.n_samples >= 10:
        print("Number of samples : {}".format(bid_explanation.n_samples))
        hcp_text = generete_hcp_alert(bid_explanation=bid_explanation)
        length_text = generate_suits_length_alert(bid_explanation)
        final_text = "{}\n{}".format(
            hcp_text, length_text)
        print(final_text)
        return {"text": final_text, "samples": bid_explanation.samples[:10]}
    return {"text": "No alert available", "samples": bid_explanation.samples}


if __name__ == "__main__":
    generate_alerts(100)
