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
MODELS = Models.from_conf(conf.load(DEFAULT_MODEL_CONF))


diags = [Diag.generate_random() for _ in range(100)]


def bid_and_extract_hand(diag: Diag, dict_of_alerts: Dict[BidPosition, BidExplanations], verbose=False):
    # vuls = [bool(random.getrandbits(1)), bool(random.getrandbits(1))]
    vuls = [False, False]
    auction = []
    bidder_bots: List[BotBid] = [BotBid(
        vuls, diag.hands[dir].to_pbn(), MODELS) for dir in Direction]
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
    if not verbose:
        return
    print(auction)
    for i, _ in enumerate(auction):
        print(auction[i], ":", generate_alert_from_bid_explanation(
            dict_of_alerts[BidPosition(auction[:i+1], vuls)])["text"])
        print("------------")
    print("------------\n------------")


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
    TRESHOLD = (10/100)*sum(dic.values())
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
    maximum_text = str(strict_maximum_hcp) if strict_maximum_hcp == usual_maximum_hcp else "{}({})".format(
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
    strict_min_length = 0 if strict_min_length == 1 else strict_min_length
    usual_min_length = 0 if usual_min_length == 1 else usual_min_length
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
    suits_text = ""
    long_suits: List[Suit] = []
    short_suits: List[Suit] = []
    for s in Suit:
        print_max_length = (suits_length_alert_as_dict[s]["strict_max_length"] <=
                            3) if bid_explanation.n_samples >= 50 else suits_length_alert_as_dict[s]["usual_max_length"] <= 1
        print_min_length = suits_length_alert_as_dict[s][
            "usual_min_length"] >= 4 or suits_length_alert_as_dict[s]["strict_min_length"] >= 3
        if print_max_length:
            short_suits.append(s)
            suits_text += print_suit_max_length(usual_max_length=suits_length_alert_as_dict[s]["usual_max_length"], strict_max_length=suits_length_alert_as_dict[s]["strict_max_length"],
                                                usual_min_length=suits_length_alert_as_dict[s]["usual_min_length"], strict_min_length=suits_length_alert_as_dict[s]["strict_min_length"], suit=s)
        elif print_min_length:
            long_suits.append(s)
            suits_text += print_suit_min_length(
                usual_min_length=suits_length_alert_as_dict[s]["usual_min_length"], strict_min_length=suits_length_alert_as_dict[s]["strict_min_length"], suit=s)
    suits_text = suits_text[:-1] if suits_text else suits_text

    player_hands = [PlayerHand.from_pbn(pbn_hand)
                    for pbn_hand in bid_explanation.samples]
    two_suiter_mask = [player_hand.ordered_pattern(
    )[1] >= 4 and not player_hand.balanced() for player_hand in player_hands]
    two_suiter_proba = two_suiter_mask.count(True)/len(two_suiter_mask)

    if two_suiter_proba > 0.95:
        is_sure = two_suiter_proba == 1
        if len(long_suits) == 2:
            return "{}two suiter, with {}".format("Usually " if not is_sure else "", suits_text)
        if len(long_suits) == 1 and len(short_suits) == 1 and suits_length_alert_as_dict[short_suits[0]]["usual_max_length"] <= 1:
            return "{}splinter, with {}".format("Usually " if not (is_sure and suits_length_alert_as_dict[short_suits[0]]["strict_max_length"] <= 1) else "", suits_text)
        if len(long_suits) == 1:
            return "{}two suiter, with {} and another unkown suit".format("Usually " if not is_sure else "", suits_text)
        else:
            return "{}unknown two suiter, {}".format("Usually " if not is_sure else "", suits_text)

    six_card_mask = [player_hand.ordered_pattern(
    )[0] >= 6 for player_hand in player_hands]
    six_card_proba = six_card_mask.count(True)/len(six_card_mask)

    if six_card_proba >= 0.95:
        is_sure = six_card_proba == 1
        if len(long_suits) == 1:
            return "{}one suiter, with {}".format("Usually " if not is_sure else "", suits_text)
        else:
            return "{}unknown one suiter {}".format("Usually " if not is_sure else "", suits_text)

    five_card_mask = [player_hand.ordered_pattern(
    )[0] >= 5 for player_hand in player_hands]
    five_card_proba = five_card_mask.count(True)/len(five_card_mask)
    if five_card_proba == 0.95 and len(long_suits) == 0:
        is_sure = five_card_proba == 1
        return "{}an unkown five card + suit {}".format("Usually " if not is_sure else "", suits_text)

    return "{}".format(suits_text)


def generate_alert_from_bid_explanation(bid_explanation: BidExplanations) -> Dict:
    if bid_explanation.n_samples >= 5:
        # print("Number of samples : {}".format(bid_explanation.n_samples))
        hcp_text = generete_hcp_alert(bid_explanation=bid_explanation)
        length_text = generate_suits_length_alert(bid_explanation)
        final_text = "{}{}{}".format(
            hcp_text, "\n" if length_text else "", length_text)
        return {"text": final_text, "samples": bid_explanation.samples[:5]}
    return {"text": "No alert available", "samples": bid_explanation.samples}


if __name__ == "__main__":
    generate_alerts(100)
