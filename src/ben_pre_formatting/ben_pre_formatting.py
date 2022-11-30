from __future__ import annotations
from typing import List
from .utils import Direction,PlayerHand,VULNERABILITIES
from .PlayRecord import PlayRecord,BiddingSuit

def convert_data_to_ben(
        hand_str : str,
        dummy_hand_str : str,
        dealer : str,
        vuln_str : str,
        auction : List,
        contract : str,
        declarer : str,
        next_player : str,
        tricks : List[List[str]]) :


    trick_i = sum([1 if len(trick)==4 else 0 for trick in tricks])
    player_i = Direction.from_str(declarer).next().to_str()
    play_record = PlayRecord.from_tricks_as_list(declarer=Direction.from_str(declarer),list_of_tricks = [[card for card in trick] for trick in tricks], trump = BiddingSuit.from_str(contract[1]))
    shown_out_suits = [set([s.value for s in play_record.shown_out_suits[dir]]) for dir in Direction]
    players_card_played = play_record.cards_played_32
    current_trick = play_record.record[-1].get_as_32_list()
    padded_auction = ["PAD_START"] * Direction.from_str(dealer).value + auction
    cards_player = PlayerHand.from_pbn(hand_str).get_as_32_list()
    vuls = VULNERABILITIES[vuln_str]


