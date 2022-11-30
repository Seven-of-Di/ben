from __future__ import annotations

from enum import Enum
from functools import total_ordering
from typing import Dict, Iterable, List

"""
Common bridge concepts such as Cardinal Direction, Suit, and Card Rank represented as Enums
"""

VULNERABILITIES = {
    'None': [False, False],
    'N-S': [True, False],
    'E-W': [False, True],
    'Both': [True, True]
}

@total_ordering
class Direction(Enum):
    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3

    __from_str_map__ = {"N": NORTH, "E": EAST, "S": SOUTH, "W": WEST}
    __to_str__ = {NORTH : "North",SOUTH : "South",EAST : "East",WEST : "West"}

    @classmethod
    def from_str(cls, direction_str: str) -> Direction:
        return Direction(cls.__from_str_map__[direction_str.upper()])

    def __lt__(self, other: Direction) -> bool:
        return self.value < other.value

    def __repr__(self) -> str:
        return self.name

    def next(self) -> Direction:
        return self.offset(1)

    def partner(self) -> Direction:
        return self.offset(2)

    def previous(self) -> Direction:
        return self.offset(3)

    def offset(self, offset: int) -> Direction:
        return Direction((self.value + offset) % 4)
    
    def teammates(self, other : Direction) -> bool :
        if self == other.partner() or self == other :
            return True
        return False

    def opponents(self,other:Direction) -> bool :
        return not self.teammates(other)

    def abbreviation(self) -> str:
        return self.name[0]

    def to_str(self) -> str :
        return self.__to_str__[self.value]


@total_ordering
class Suit(Enum):
    SPADES = 0
    HEARTS = 1
    DIAMONDS = 2
    CLUBS = 3

    __from_str_map__ = {"S": SPADES, "H": HEARTS, "D": DIAMONDS,
                        "C": CLUBS, '♠': SPADES, '♥': HEARTS, '♦': DIAMONDS, '♣': CLUBS}

    __to_symbol__ = {SPADES : '♠',HEARTS : '♥',DIAMONDS:'♦',CLUBS:'♣'}

    __4_colors__ = {SPADES : 'blue',HEARTS : 'red',DIAMONDS:'orange',CLUBS:'green'}

    @classmethod
    def from_str(cls, suit_str: str) -> Suit:
        return Suit(cls.__from_str_map__[suit_str.upper()])

    def __lt__(self, other: Suit) -> bool:
        return self.value > other.value

    def __repr__(self) -> str:
        return self.name

    def abbreviation(self) -> str:
        return self.name[0]

    def symbol(self) -> str :
        return self.__to_symbol__[self.value]

    def color(self) -> str :
        return self.__4_colors__[self.value]

    def is_major(self) :
        return True if self.value >=2 else False
    
    def is_minor(self) :
        return not self.is_major()
            


@total_ordering
class Rank(Enum):
    TWO = 2, "2", 0
    THREE = 3, "3", 0
    FOUR = 4, "4", 0
    FIVE = 5, "5", 0
    SIX = 6, "6", 0
    SEVEN = 7, "7", 0
    EIGHT = 8, "8", 0
    NINE = 9, "9", 0
    TEN = 10, "T", 0
    JACK = 11, "J", 1
    QUEEN = 12, "Q", 2
    KING = 13, "K", 3
    ACE = 14, "A", 4

    __from_str_map__ = {
        "2": TWO,
        "3": THREE,
        "4": FOUR,
        "5": FIVE,
        "6": SIX,
        "7": SEVEN,
        "8": EIGHT,
        "9": NINE,
        "10": TEN,
        "T": TEN,
        "J": JACK,
        "Q": QUEEN,
        "K": KING,
        "A": ACE,
    }

    @classmethod
    def from_str(cls, rank_str: str) -> Rank:
        return Rank(cls.__from_str_map__[rank_str.upper()])

    def __lt__(self, other: Rank) -> bool:
        return self.value < other.value

    def __repr__(self) -> str:
        return self.name

    def rank(self) -> int:
        return self.value[0]

    def __str__(self) -> str:
        return self.value[1]

    def abbreviation(self) -> str:
        return self.value[1]

    def hcp(self) -> int:
        return self.value[2]

    def __hash__(self) -> int:
        return hash(repr(self))


@total_ordering
class BiddingSuit(Enum):
    CLUBS = 3, Suit.CLUBS
    DIAMONDS = 2, Suit.DIAMONDS
    HEARTS = 1, Suit.HEARTS
    SPADES = 0, Suit.SPADES
    NO_TRUMP = 4, None

    __from_str_map__ = {"S": SPADES, "H": HEARTS,
                        "D": DIAMONDS, "C": CLUBS, "N": NO_TRUMP, "NT": NO_TRUMP,
                        '♠': SPADES, '♥': HEARTS, '♦': DIAMONDS, '♣': CLUBS, 'SA': NO_TRUMP}
    __to_symbol__ = {SPADES : '♠',HEARTS : '♥',DIAMONDS:'♦',CLUBS:'♣', NO_TRUMP : "NT"}
    __4_colors__ = {SPADES : 'blue',HEARTS : 'red',DIAMONDS:'orange',CLUBS:'green',NO_TRUMP : 'black'}

    def __lt__(self, other) -> bool:
        return self.value > other.value

    def __repr__(self) -> str:
        return self.name

    def to_suit(self) -> Suit:
        return self.value[1]

    def abbreviation(self, verbose_no_trump=True) -> str:
        if self.value == BiddingSuit.NO_TRUMP.value and verbose_no_trump:
            return "NT"
        return self.name[0]

    def symbol(self) -> str :
        return self.__to_symbol__[self.value]
    
    def color(self) -> str :
        return self.__4_colors__[self.value]

    @classmethod
    def from_str(cls, bidding_suit_str: str) -> BiddingSuit:
        return BiddingSuit(cls.__from_str_map__[bidding_suit_str.upper()])


@total_ordering
class Card:
    """A single card in a hand or deal of bridge"""

    def __init__(self, suit: Suit, rank: Rank):
        self.suit = suit
        self.rank = rank

    def __eq__(self, other) -> bool:
        return self.rank == other.rank and self.suit == other.suit

    def __lt__(self, other) -> bool:
        return self.rank < other.rank

    def __str__(self) -> str:
        return self.rank.abbreviation() + self.suit.abbreviation()

    def to_pbn(self) -> str:
        return self.suit.abbreviation() + self.rank.abbreviation()

    def suit_first_str(self) -> str :
        return self.to_pbn()

    def to_52(self) -> int :
        return self.suit.value *13 + self.rank.value

    def to_32(self) -> int :
        return self.suit.value * 8 + min(self.rank.value,7)

    def __repr__(self) -> str:
        return self.rank.abbreviation()

    def __hash__(self) -> int:
        return hash(repr(self))

    def trump_comparaison(self, other : Card, trump : BiddingSuit, lead : Suit) -> bool :
        if self.suit == other.suit :
            return self.rank>other.rank
        if self.suit == trump.to_suit() :
            return True
        if other.suit == trump.to_suit() :
            return False
        if self.suit == lead :
            return True
        if other.suit == lead :
            return False
        raise Exception("None of the card is a trump or the suit led")


    @classmethod
    def from_str(cls, card_str) -> Card:
        try:
            return Card(Suit.from_str(card_str[0]), Rank.from_str(card_str[1]))
        except:
            return Card(Suit.from_str(card_str[1]), Rank.from_str(card_str[0]))


class PlayerHand():
    """Contain one hand"""

    def __init__(self, suits: Dict[Suit, List[Rank]]):
        self.suits: Dict[Suit, List[Rank]] = suits
        self.cards: List[Card] = []
        self.pair_vul = False
        self.opp_vul = False
        for suit in reversed(Suit):
            for rank in self.suits[suit]:
                self.cards.append(Card(suit, rank))

    @staticmethod
    def from_cards(cards: Iterable[Card]) -> PlayerHand:
        suits = {
            Suit.CLUBS: sorted([card.rank for card in cards if card.suit == Suit.CLUBS], reverse=True),
            Suit.DIAMONDS: sorted([card.rank for card in cards if card.suit == Suit.DIAMONDS], reverse=True),
            Suit.HEARTS: sorted([card.rank for card in cards if card.suit == Suit.HEARTS], reverse=True),
            Suit.SPADES: sorted([card.rank for card in cards if card.suit == Suit.SPADES], reverse=True),
        }
        return PlayerHand(suits)

    @staticmethod
    def from_pbn(string: str) -> PlayerHand:
        """Create a hand from a string with the following syntax '752.Q864.84.AT62'"""
        tab_of_suit = string.split('.')
        cards = []
        for index, suit in enumerate(tab_of_suit):
            temp = suit.replace("10", "T").replace("X", "T")
            while temp.find('x') != -1:
                for rank in Rank:
                    if rank.abbreviation() in temp:
                        continue
                    temp = temp.replace('x', rank.abbreviation(), 1)
            for rank in temp:
                match index:
                    case 0:
                        cards.append(Card(Suit.SPADES, Rank.from_str(rank)))
                    case 1:
                        cards.append(Card(Suit.HEARTS, Rank.from_str(rank)))
                    case 2:
                        cards.append(Card(Suit.DIAMONDS, Rank.from_str(rank)))
                    case 3:
                        cards.append(Card(Suit.CLUBS, Rank.from_str(rank)))

        return PlayerHand.from_cards(cards)

    def get_as_32_list(self) :
        return [c.to_32() for c in self.cards]

TOTAL_DECK : List[Card] = []
for rank in Rank:
    for suit in Suit:
        TOTAL_DECK.append(Card(suit, rank))
