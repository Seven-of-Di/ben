from __future__ import annotations
from dataclasses import dataclass
import logging
from typing import Dict, List, Optional, Set, Tuple

from utils  import Direction, Card_, BiddingSuit, Suit


@dataclass
class PlayRecord:
    tricks: int
    leader: Direction
    record: Optional[List[Trick]]
    shown_out_suits : Dict[Direction,Set(Suit)]
    cards_played_32 : List[List[int]] 


    @staticmethod
    def from_tricks_as_list(trump : BiddingSuit,list_of_tricks : List[List[str]], declarer : Direction) -> PlayRecord :
        list_of_tricks = [[Card_.from_str(card) for card in trick] for trick in list_of_tricks]
        tricks : List[Trick] = []
        tricks_count = 0
        turn = declarer.offset(1)
        shown_out_suits : Dict[Direction,Set(Suit)] = {d:set() for d in Direction}
        cards_played_32 : List[List[int]] = [[] for _ in range(4)]
        print(list_of_tricks)
        for trick_as_list in list_of_tricks :
            current_trick = {}
            for i,card in enumerate(trick_as_list) :
                current_trick[turn.offset(i)] = card
                cards_played_32[turn.offset(i).value].append(card.to_32())
            trick = Trick(turn,current_trick)
            if trick.shown_out_suit != {} :
                for key,value in trick.shown_out_suit.items() :
                    shown_out_suits[key].add(value)
                
            turn = trick.winner(trump)
            tricks_count +=1 if turn in [declarer,declarer.partner()] else 0
            tricks.append(trick)

        return PlayRecord(tricks=tricks_count,leader = declarer.offset(1),record=tricks,shown_out_suits=shown_out_suits,cards_played_32=cards_played_32)

    def __str__(self) -> str:
        string = "Tricks : " + str(self.tricks) + "\n"
        if self.record:
            string += '{0:3}{1:3}{2:3}{3:3}\n'.format('N', 'E', 'S', 'W')
            for trick in self.record:
                string += trick.__str__() + "\n"
        return string

    def __len__(self) :
        if self.record is None :
            return 0
        else :
            return len(self.record)


class Trick():
    def __init__(self, lead : Direction, cards : Dict[Direction,Card_], shown_out_suit : Dict[Direction,Suit]={}) -> None:
        self.lead: Direction = lead
        self.cards: Dict[Direction, Card_] = cards
        self.shown_out_suit : Dict[Direction,Suit] = shown_out_suit

    def winner(self, trump: BiddingSuit) -> Direction:
        winner = self.lead
        suit_led = self.lead #Default value, should not append
        try :
            suit_led = self.cards[winner].suit
        except :
            logging.warning("The winner of the last trick didn't play in the following one")
            return winner
        if trump == BiddingSuit.NO_TRUMP:
            for dir, card in self.cards.items():
                if card.suit == suit_led:
                    if card > self.cards[winner]:
                        winner = dir
                else :
                    self.shown_out_suit[dir].add(card.suit)
        else:  # Trump
            for dir, card in self.cards.items():
                if card.suit == trump.to_suit():
                    if self.cards[winner].suit == suit_led:
                        winner = dir
                    if self.cards[winner].suit == trump.to_suit():
                        if card > self.cards[winner]:
                            winner = dir
                elif card.suit == suit_led and self.cards[winner].suit == suit_led:
                    if card > self.cards[winner]:
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
        for i in range(len(Direction)):
            if self.cards[first_dir]:
                string += self.cards[first_dir].to_pbn()+" "
            else:
                string += "-  "
            first_dir = first_dir.offset(1)
        return string[:-1]

    def get_as_32_list(self) :
        trick_as_list : List[Tuple[Direction,Card_]]= []
        dir : Direction = self.lead
        for _ in range(len(self.cards)) :
            trick_as_list.append(self.cards[dir].to_32())
            dir = dir.offset(1)
        return trick_as_list

    def __trick_as_list__(self) -> List[Tuple[Direction,Card_]] :
        trick_as_list : List[Tuple[Direction,Card_]]= []
        dir : Direction = self.lead
        for _ in range(len(self.cards)) :
            trick_as_list.append((dir,self.cards[dir]))
            dir = dir.offset(1)
        return trick_as_list

    def __getitem__(self,key) :
        return self.__trick_as_list__()[key]

    def __len__(self) :
        return len(self.cards)