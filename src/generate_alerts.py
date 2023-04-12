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
from utils import Direction, PlayerHand, Suit, Diag, BiddingSuit
from alert_utils import BidExplanations, BidPosition
from SequenceAtom import Bid
import pickle


DEFAULT_MODEL_CONF = os.path.join(os.path.dirname(os.getcwd()), 'default.conf')
MODELS = Models.from_conf(conf.load(DEFAULT_MODEL_CONF))


diags = [Diag.generate_random() for _ in range(100)]


def manual_alert(seq_str: List[str]) -> str | None:
    if len(seq_str) == seq_str.count("PASS"):
        return "0-11 hcp"
    if not(seq_str[-1] != "PASS" and len(seq_str)-seq_str.count("PASS") == 1):
        return None
    bid = Bid.from_str(seq_str[-1])
    if not bid <= Bid.from_str("3S"):
        return None
    if bid == Bid(1, BiddingSuit.CLUBS):
        return "Better minor, 12+hcp,3+!C"
    if bid == Bid(1, BiddingSuit.DIAMONDS):
        return "Better minor, 12+hcp,3+!D"
    if bid == Bid(1, BiddingSuit.HEARTS):
        return "5th major, 12+hcp,5+!H"
    if bid == Bid(1, BiddingSuit.SPADES):
        return "5th major, 12+hcp,5+!S"
    if bid == Bid(1, BiddingSuit.NO_TRUMP):
        return "15-17 hcp balanced"
    if bid == Bid(2, BiddingSuit.CLUBS):
        return "Any strong hand, 21+hcp"
    if bid == Bid(2, BiddingSuit.DIAMONDS):
        return "Natural preempt, 6-10 hcp, 6!D"
    if bid == Bid(2, BiddingSuit.HEARTS):
        return "Natural preempt, 6-10 hcp, 6!H"
    if bid == Bid(2, BiddingSuit.SPADES):
        return "Natural preempt, 6-10 hcp, 6!S"
    if bid == Bid(2, BiddingSuit.NO_TRUMP):
        return "20-21 hcp balanced"
    if bid == Bid(2, BiddingSuit.SPADES):
        return "Natural preempt, 6-10 hcp, 6!S"
    if bid == Bid(3, BiddingSuit.CLUBS):
        return "Natural preempt, 6-10 hcp, 7!C"
    if bid == Bid(3, BiddingSuit.DIAMONDS):
        return "Natural preempt, 6-10 hcp, 7!D"
    if bid == Bid(3, BiddingSuit.HEARTS):
        return "Natural preempt, 6-10 hcp, 7!H"
    if bid == Bid(3, BiddingSuit.SPADES):
        return "Natural preempt, 6-10 hcp, 7!S"

    raise Exception


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
            dict_of_alerts[BidPosition(auction[:i+1], vuls)]))
        print("------------")
    print("------------\n------------")


def generate_alerts(check_point: int):
    dict_of_alerts: Dict[BidPosition, BidExplanations] = {}

    with open('C:/Users/lucbe/OneDrive/Documents/Bridge/alerts.pickle', 'rb') as f:
        dict_of_alerts = pickle.load(f)

    while True:
        start = time.time()
        diags = [Diag.generate_random() for _ in range(check_point)]
        for i in range(check_point):
            bid_and_extract_hand(diags[i], dict_of_alerts)
        end = time.time()
        print('{} diags alerts saved in {} seconds. Current number of sequence {}'.format(
            check_point, end-start, len(dict_of_alerts)))
        with open('C:/Users/lucbe/OneDrive/Documents/Bridge/alerts.pickle', 'wb') as f:
            pickle.dump(dict_of_alerts, f, pickle.HIGHEST_PROTOCOL)


def generate_usual_alert_from_dict(dic: Dict, ascending: bool) -> int:
    TRESHOLD = (10/100)*sum(dic.values())
    tuples_list = dic.items() if ascending else reversed(list(dic.items()))
    cumulative_sum = 0
    for tested_key, occurences in tuples_list:
        cumulative_sum += occurences
        if cumulative_sum >= TRESHOLD:
            return tested_key
    raise Exception(
        "Treshold should be reached at some point, something fishy is going on. dict : {dic}".format(dic))


def generete_hcp_alert(bid_explanation: BidExplanations) -> str:
    strict_maximum_hcp = bid_explanation.max_hcp
    usual_minimum_hcp = generate_usual_alert_from_dict(
        bid_explanation.hcp_distribution, ascending=True)
    usual_maximum_hcp = generate_usual_alert_from_dict(
        bid_explanation.hcp_distribution, ascending=False)
    minimum_text = str(usual_minimum_hcp)
    maximum_text = str(strict_maximum_hcp)
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


def print_suit_max_length(usual_max_length: int, usual_min_length: int,  suit: Suit) -> str:
    usual_min_length = 0 if usual_min_length == 1 else usual_min_length
    return "{}-{}{}|".format(usual_min_length, usual_max_length, suit.symbol())


def print_suit_min_length(usual_min_length: int, suit: Suit) -> str:
    return "{}+{}|".format(usual_min_length, suit.symbol())


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
            suits_text += print_suit_max_length(
                usual_max_length=suits_length_alert_as_dict[s]["usual_max_length"], usual_min_length=suits_length_alert_as_dict[s]["usual_min_length"],  suit=s)
        elif print_min_length:
            long_suits.append(s)
            suits_text += print_suit_min_length(
                usual_min_length=suits_length_alert_as_dict[s]["usual_min_length"], suit=s)
    suits_text = suits_text[:-1] if suits_text else suits_text

    player_hands = [PlayerHand.from_pbn(pbn_hand)
                    for pbn_hand in bid_explanation.samples]
    two_suiter_mask = [player_hand.ordered_pattern(
    )[1] >= 4 and not player_hand.balanced() for player_hand in player_hands]
    two_suiter_proba = two_suiter_mask.count(True)/len(two_suiter_mask)

    if two_suiter_proba > 0.95:
        if len(long_suits) == 2:
            return "{}".format(suits_text)
        if len(long_suits) == 1 and len(short_suits) == 1 and suits_length_alert_as_dict[short_suits[0]]["usual_max_length"] <= 1:
            return "Splinter : {}".format(suits_text)
        if len(long_suits) == 1:
            return "Two suiter : {} and another".format(suits_text)
        else:
            return "Unknown two suiter".format()

    six_card_mask = [player_hand.ordered_pattern(
    )[0] >= 6 for player_hand in player_hands]
    six_card_proba = six_card_mask.count(True)/len(six_card_mask)

    if six_card_proba >= 0.95:
        if len(long_suits) == 1:
            return "{}".format(suits_text)
        else:
            return "Unknown one suiter {}".format(suits_text)

    five_card_mask = [player_hand.ordered_pattern(
    )[0] >= 5 for player_hand in player_hands]
    five_card_proba = five_card_mask.count(True)/len(five_card_mask)
    if five_card_proba == 0.95 and len(long_suits) == 0:
        return "An unkown five card + suit {}".format("suits_text")

    return "{}".format(suits_text)


def generate_alert_from_bid_explanation(bid_explanation: BidExplanations) -> str | None:
    if bid_explanation.n_samples >= 5:
        # print("Number of samples : {}".format(bid_explanation.n_samples))
        hcp_text = generete_hcp_alert(bid_explanation=bid_explanation)
        length_text = generate_suits_length_alert(bid_explanation)
        final_text = "{}{}{}".format(
            hcp_text, "\n" if length_text else "", length_text)
        return final_text

    return None


def request_from_pickle_file(str_sequence: List[str]) -> BidExplanations:
    with open('C:/Users/lucbe/OneDrive/Documents/Bridge/alerts.pickle', 'rb') as f:
        dict_of_alerts: Dict[BidPosition, BidExplanations] = pickle.load(f)

    position = BidPosition(str_sequence, [False, False])
    return (dict_of_alerts[position])


if __name__ == "__main__":
    generate_alerts(1000)
    # print(request_from_pickle_file(["2N"]).hcp_distribution)
    # print(manual_alert(["PASS", "PASS", "1S"]))
