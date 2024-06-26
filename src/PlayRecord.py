from __future__ import annotations
from dataclasses import dataclass
import logging
from typing import Dict, List, Optional, Set, Tuple

from utils import Direction, Card_, BiddingSuit, Suit
from parsing_tools import Pbn


@dataclass
class PlayRecord:
    number_of_tricks: int
    leader: Direction
    record: Optional[List[Trick]]
    shown_out_suits: Dict[Direction, Set[Suit]]
    cards_played_32: List[List[int]]

    @staticmethod
    def from_pbn(string: str) -> Optional[PlayRecord]:
        str_leader = Pbn.get_tag_content(string, "Play")
        str_result = Pbn.get_tag_content(string, "Result")

        if str_result=="":
            return None

        str_declarer = Pbn.get_tag_content(
            string, "Declarer") if str_leader else ""
        if str_declarer=="":
            return None
        trump = BiddingSuit.from_str(
            Pbn.get_tag_content(string, "Contract").replace('X', '')[1:])
        raw_tricks_data = Pbn.get_content_under_tag(string, "Play")
        str_tricks = raw_tricks_data.split('\n') if raw_tricks_data else None
        list_of_str_tricks = [[c for c in trick.split()]
                              for trick in str_tricks] if str_tricks else []

        return PlayRecord.from_tricks_as_list(trump, list_of_tricks=list_of_str_tricks, declarer=Direction.from_str(
            str_declarer))

    @staticmethod
    def from_tricks_as_list(trump: BiddingSuit, list_of_tricks: List[List[str]], declarer: Direction) -> PlayRecord:
        list_of_tricks_as_cards = [
            [Card_.from_str(card) for card in trick] for trick in list_of_tricks]
        tricks: List[Trick] = []
        tricks_count: int = 0
        turn = declarer.offset(1)
        shown_out_suits: Dict[Direction, Set[Suit]] = {
            d: set() for d in Direction}
        cards_played_32: List[List[int]] = [[] for _ in range(4)]
        for trick_as_list in list_of_tricks_as_cards:
            if len(trick_as_list) == 0:
                continue
            current_trick = {}
            for i, card in enumerate(trick_as_list):
                current_trick[turn.offset(i)] = card
                cards_played_32[turn.offset(i).value].append(card.to_32())
            trick = Trick(turn, current_trick)
            if trick.shown_out_suit != {}:
                for dir, suit in trick.shown_out_suit.items():
                    shown_out_suits[dir].add(suit)
            tricks.append(trick)
            if len(trick) != 4:
                # print("Length of trick is not 4")
                continue
            turn = trick.winner(trump)
            tricks_count += 1 if turn in [declarer, declarer.partner()] else 0

        return PlayRecord(number_of_tricks=tricks_count, leader=declarer.offset(1), record=tricks, shown_out_suits=shown_out_suits, cards_played_32=cards_played_32)

    def print_as_pbn(self) -> str:
        string = ""
        string += Pbn.print_tag("Result", str(self.number_of_tricks))
        string += Pbn.print_tag("Play", self.leader.abbreviation())
        if self.record:
            for trick in self.record:
                string += trick.print_as_pbn(self.leader)+"\n"
        return string + "*"

    def as_unordered_one_dimension_list(self) -> List[Card_]:
        return [card for trick in self.record for card in trick.cards.values()] if self.record is not None else []

    def __str__(self) -> str:
        string = "Tricks : " + str(self.number_of_tricks) + "\n"
        if self.record:
            string += '{0:3}{1:3}{2:3}{3:3}\n'.format('N', 'E', 'S', 'W')
            for trick in self.record:
                string += trick.__str__() + "\n"
        return string

    def __len__(self):
        if self.record is None:
            return 0
        else:
            return len(self.record)

    def length_wo_incomplete(self):
        if self.record is None:
            return 0
        else:
            return sum([1 if len(trick) == 4 else 0 for trick in self.record])

    def get_cards_played_by_direction(self, direction: Direction) -> List[Card_]:
        cards: List[Card_] = []
        if self.record is None:
            return []
        for trick in self.record:
            if direction in trick.cards:
                cards.append(trick.cards[direction])
        return cards


class Trick():
    def __init__(self, lead: Direction, cards: Dict[Direction, Card_]) -> None:
        self.lead: Direction = lead
        self.cards: Dict[Direction, Card_] = cards
        self.shown_out_suit: Dict[Direction, Suit] = {
            dir: cards[lead].suit for dir in cards.keys() if self.cards[dir].suit != self.cards[lead].suit}

    @staticmethod
    def from_list(leader: Direction, trick_as_list: List[Card_]) -> Trick:
        trick_as_dict = {}

        for i, card in enumerate(trick_as_list):
            trick_as_dict[leader.offset(i)] = card
        return Trick(lead=leader, cards=trick_as_dict)

    def winner(self, trump: BiddingSuit) -> Direction:
        winner = self.lead
        suit_led = self.lead  # Default value, should not append
        try:
            suit_led = self.cards[winner].suit
        except:
            logging.warning(
                "The winner of the last trick didn't play in the following one")
            return winner
        for dir, card in self.cards.items():
            if card.trump_comparaison(self.cards[winner], trump, suit_led):
                winner = dir

        return winner

    def __str__(self) -> str:
        string = ""
        for dir in Direction:
            if dir in self.cards:
                string += '{0:3}'.format(self.cards[dir].__str__())
        return string

    def print_as_pbn(self, first_dir: Direction) -> str:
        string = ""
        for _ in range(4):
            if first_dir in self.cards:
                string += self.cards[first_dir].to_pbn()+" "
            else:
                string += "-  "
            first_dir = first_dir.offset(1)
        return string[:-1]

    def get_as_32_list(self):
        trick_as_list: List[Tuple[Direction, int]] = []
        dir: Direction = self.lead
        for _ in range(len(self.cards)):
            trick_as_list.append((dir, self.cards[dir].to_32()))
            dir = dir.offset(1)
        return trick_as_list

    def __trick_as_tuple_list__(self) -> List[Tuple[Direction, Card_]]:
        trick_as_list: List[Tuple[Direction, Card_]] = []
        dir: Direction = self.lead
        for _ in range(len(self.cards)):
            trick_as_list.append((dir, self.cards[dir]))
            dir = dir.offset(1)
        return trick_as_list

    def __getitem__(self, key):
        return self.__trick_as_tuple_list__()[key]

    def __len__(self):
        return len(self.cards)
