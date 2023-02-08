from __future__ import annotations

from enum import Enum
from functools import total_ordering
from random import shuffle
from typing import Dict, Iterable, List
import numpy as np

"""
Common bridge concepts such as Cardinal Direction, Suit, and Card Rank represented as Enums
"""

DIRECTIONS = 'NESW'

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
    __to_str__ = {NORTH: "North", SOUTH: "South", EAST: "East", WEST: "West"}

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

    def teammates(self, other: Direction) -> bool:
        if self == other.partner() or self == other:
            return True
        return False

    def opponents(self, other: Direction) -> bool:
        return not self.teammates(other)

    def abbreviation(self) -> str:
        return self.name[0]

    def to_str(self) -> str:
        return self.__to_str__[self.value]

    def farest(self, dir1: Direction, dir2: Direction) -> Direction:
        for i in range(4):
            if self.offset(i) == dir1:
                return dir2
            if self.offset(i) == dir2:
                return dir1
        raise Exception("???")


@total_ordering
class Suit(Enum):
    SPADES = 0
    HEARTS = 1
    DIAMONDS = 2
    CLUBS = 3

    __from_str_map__ = {"S": SPADES, "H": HEARTS, "D": DIAMONDS,
                        "C": CLUBS, '♠': SPADES, '♥': HEARTS, '♦': DIAMONDS, '♣': CLUBS}

    __to_symbol__ = {SPADES: '♠', HEARTS: '♥', DIAMONDS: '♦', CLUBS: '♣'}

    __4_colors__ = {SPADES: 'blue', HEARTS: 'red',
                    DIAMONDS: 'orange', CLUBS: 'green'}

    @classmethod
    def from_str(cls, suit_str: str) -> Suit:
        return Suit(cls.__from_str_map__[suit_str.upper()])

    def __lt__(self, other: Suit) -> bool:
        return self.value > other.value

    def __repr__(self) -> str:
        return self.name

    def abbreviation(self) -> str:
        return self.name[0]

    def symbol(self) -> str:
        return self.__to_symbol__[self.value]

    def color(self) -> str:
        return self.__4_colors__[self.value]

    def is_major(self):
        return True if self.value >= 2 else False

    def is_minor(self):
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
    def from_integer(cls, rank_as_int: int) -> Rank:
        return [r for r in reversed(Rank)][rank_as_int]


    def to_integer(self) -> int:
        return [r for r in reversed(Rank)].index(self)

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

    def previous(self) -> Rank:
        return [r for r in Rank][[r for r in Rank].index(self)-1]

    def next(self) -> Rank:
        return [r for r in Rank][[r for r in Rank].index(self)+1]

    def offset(self, offset: int) -> Rank:
        return [r for r in Rank][[r for r in Rank].index(self)+offset]

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
    __to_symbol__ = {SPADES: '♠', HEARTS: '♥',
                     DIAMONDS: '♦', CLUBS: '♣', NO_TRUMP: "NT"}
    __4_colors__ = {SPADES: 'blue', HEARTS: 'red',
                    DIAMONDS: 'orange', CLUBS: 'green', NO_TRUMP: 'black'}
    __to_strain__ = {NO_TRUMP: 0, SPADES: 1, HEARTS: 2, DIAMONDS: 3, CLUBS: 4}

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

    def symbol(self) -> str:
        return self.__to_symbol__[self.value]

    def color(self) -> str:
        return self.__4_colors__[self.value]

    def strain(self):
        return self.__to_strain__[self.value]

    @classmethod
    def from_str(cls, bidding_suit_str: str) -> BiddingSuit:
        return BiddingSuit(cls.__from_str_map__[bidding_suit_str.upper()])


@total_ordering
class Card_:
    """A single card in a hand or deal of bridge"""

    def __init__(self, suit: Suit, rank: Rank):
        self.suit = suit
        self.rank = rank

    def __eq__(self, other) -> bool:
        return self.rank == other.rank and self.suit == other.suit

    def __lt__(self, other) -> bool:
        return self.rank < other.rank

    def __str__(self) -> str:
        return self.suit.abbreviation() + self.rank.abbreviation()

    def to_pbn(self) -> str:
        return self.suit.abbreviation() + self.rank.abbreviation()

    def suit_first_str(self) -> str:
        return self.to_pbn()

    def to_52(self) -> int:
        return self.suit.value * 13 + self.rank.to_integer()

    def to_32(self) -> int:
        return self.suit.value * 8 + 14-max(self.rank.rank(), 7)

    def __repr__(self) -> str:
        return self.rank.abbreviation()

    def __hash__(self) -> int:
        return hash(repr(self))

    def trump_comparaison(self, other: Card_, trump: BiddingSuit, lead: Suit) -> bool:
        if self.suit == other.suit:
            return self.rank > other.rank
        if self.suit == trump.to_suit():
            return True
        if other.suit == trump.to_suit():
            return False
        if self.suit == lead:
            return True
        if other.suit == lead:
            return False
        raise Exception("None of the card is a trump or the suit led")

    @classmethod
    def from_str(cls, card_str) -> Card_:
        try:
            return Card_(Suit.from_str(card_str[0]), Rank.from_str(card_str[1]))
        except:
            return Card_(Suit.from_str(card_str[1]), Rank.from_str(card_str[0]))

    @classmethod
    def get_from_52(cls, value: int):
        return Card_(suit=Suit(value//13), rank=Rank.from_integer((value) % 13))


class PlayerHand():
    """Contain one hand"""

    def __init__(self, suits: Dict[Suit, List[Rank]]):
        self.suits: Dict[Suit, List[Rank]] = suits
        self.cards: List[Card_] = []
        self.pair_vul = False
        self.opp_vul = False
        for suit in reversed(Suit):
            for rank in self.suits[suit]:
                self.cards.append(Card_(suit, rank))

    @staticmethod
    def from_cards(cards: Iterable[Card_]) -> PlayerHand:
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
                if index == 0:
                    cards.append(Card_(Suit.SPADES, Rank.from_str(rank)))
                elif index == 1:
                    cards.append(Card_(Suit.HEARTS, Rank.from_str(rank)))
                elif index == 2:
                    cards.append(Card_(Suit.DIAMONDS, Rank.from_str(rank)))
                elif index == 3:
                    cards.append(Card_(Suit.CLUBS, Rank.from_str(rank)))

        return PlayerHand.from_cards(cards)

    def remove(self, card: Card_):
        self.cards.remove(card)
        self.suits[card.suit].remove(card.rank)

    def append(self, card: Card_):
        if card not in self.cards:
            self.cards.append(card)
        if card.rank not in self.suits[card.suit]:
            self.suits[card.suit].append(card.rank)

    def get_as_32_list(self):
        cards_32 = [0]*32
        for i in self.cards:
            cards_32[i.to_32()] = 1
        return cards_32

    def to_pbn(self) -> str:
        suit_arrays = [[], [], [], []]
        for card in self.cards:
            suit_arrays[card.suit.value].append(repr(card))
        repr_str = ".".join("".join(suit) for suit in suit_arrays)
        return repr_str

    def __repr__(self) -> str:
        suit_arrays = [[], [], [], []]
        for card in self.cards:
            suit_arrays[card.suit.value].append(repr(card))
        repr_str = "|".join("".join(suit) for suit in suit_arrays)
        return f"PlayerHand({repr_str})"

    def __str__(self) -> str:
        suit_arrays = [['♠'], ['♥'], ['♦'], ['♣']]
        for card in sorted(self.cards, reverse=True):
            suit_arrays[card.suit.value].append(repr(card))
        repr_str = " ".join("".join(suit) for suit in suit_arrays)
        return f"{repr_str}"

    def number_of_figures(self, suit: Suit) -> int:
        return sum(el in self.suits[suit] for el in [Rank.ACE, Rank.KING, Rank.QUEEN, Rank.JACK])

    def len(self) -> int:
        # print(self.suits,self.cards)
        assert sum([len(ranks)
                   for ranks in self.suits.values()]) == len(self.cards)
        return sum([len(ranks) for ranks in self.suits.values()])

    def __len__(self) -> int:
        # print(self.suits,self.cards)
        assert sum([len(ranks)
                   for ranks in self.suits.values()]) == len(self.cards)
        return sum([len(ranks) for ranks in self.suits.values()])

    def print_as_pbn(self) -> str:
        suit_arrays = [[], [], [], []]
        for card in self.cards:
            suit_arrays[card.suit.value].append(repr(card))
        repr_str = ".".join("".join(suit) for suit in suit_arrays)
        return repr_str


TOTAL_DECK: List[Card_] = []
for rank in Rank:
    for suit in Suit:
        TOTAL_DECK.append(Card_(suit, rank))


class Diag():
    def __init__(self, hands: Dict[Direction, PlayerHand], autocomplete=True):
        self.hands = hands
        if autocomplete:
            self.auto_complete()
        self.player_cards = {
            direction: self.hands[direction].cards for direction in self.hands}

    def auto_complete(self) -> Dict[Direction, PlayerHand]:
        missing_cards = self.missing_cards()
        shuffle(missing_cards)
        for dir in Direction:
            if dir not in self.hands:
                self.hands[dir] = PlayerHand({suit: [] for suit in Suit})
            while self.hands[dir].len() < 13:
                if len(missing_cards) == 0:
                    print(self.hands)
                self.hands[dir].append(missing_cards.pop())
        return self.hands

    def missing_cards(self) -> List[Card_]:
        list_of_cards = []
        for player_hand in self.hands.values():
            for card in player_hand.cards:
                if card in list_of_cards:
                    print(self.hands)
                    print("Cette carte est en double", card)
                assert card not in list_of_cards
                list_of_cards.append(card)
        missing_cards = [
            card for card in TOTAL_DECK if card not in list_of_cards]
        return missing_cards

    def __len__(self):
        return sum(len(hand) for hand in self.hands.values())

    @staticmethod
    def init_from_pbn(string: str) -> Diag:
        """ Create a diag from this syntax : 'N:752.Q864.84.AT62 A98.AT9.Q753.J98 KT.KJ73.JT.K7543 QJ643.52.AK962.Q'"""
        dealer = Direction.from_str(string[0])
        string = string[2:]
        hand_list = string.split(" ")
        hands = {}
        for i, hand_str in enumerate(hand_list):
            hands[dealer.offset(i)] = PlayerHand.from_pbn(hand_str)

        return Diag(hands, autocomplete=False)

    def __str__(self) -> str:
        string = ""
        for direction in Direction:
            string += direction.name + " : " + \
                self.hands[direction].__str__() + "\n"
        return string

    def print_as_pbn(self) -> str:
        string = 'N:'
        for dir in Direction:
            string += self.hands[dir].print_as_pbn()
            string += " "
        return string[:-1]+''

    def is_valid(self):
        try:
            assert sum([len(self.hands[dir]) for dir in Direction]) == len(
                set((card for hand in self.hands.values() for card in hand.cards)))
        except:
            print(self)
            raise Exception


def compare_two_list(list_1: List[int], List_2: List[int]):
    list_1_sup = True
    list_2_sup = True
    for val_1, val_2 in zip(list_1, List_2):
        if val_1 < val_2:
            list_1_sup = False
            break
    for val_1, val_2 in zip(list_1, List_2):
        if val_2 < val_1:
            list_2_sup = False
            break
    if (not list_1_sup and not list_2_sup) or (list_1_sup and list_2_sup):
        return None
    if list_1_sup:
        return True
    if list_2_sup:
        return False


def multiple_list_comparaison(dd_results_dict: Dict[int, List]) -> List[int]:
    maximum_cards = []

    for card, dd_results in dd_results_dict.items():
        temp_max_cards = maximum_cards
        is_maximum = True
        for max_card in temp_max_cards:
            res = compare_two_list(dd_results_dict[max_card], dd_results)
            if res:
                is_maximum = False
                break
            if res == False:
                maximum_cards.remove(max_card)
        if is_maximum:
            maximum_cards.append(card)
    return maximum_cards

# print(multiple_list_comparaison({3:[6,5,1],0:[1,2,3],1:[2,2,3],2:[3,2,1]}))

# test = {
# 0 : [3, 3, 1, 1, 1, 2, 2, 1, 3, 2, 1, 1, 3, 1, 1, 4, 3, 3, 3, 1, 3, 2, 1, 4, 2, 1, 3, 4, 2, 2, 1, 1, 1, 1, 4, 0, 1, 2, 1, 2, 1, 2, 4, 4, 0, 2, 1, 1, 0, 2],
# 1 : [3, 3, 1, 1, 1, 2, 2, 1, 3, 2, 1, 1, 3, 1, 1, 4, 3, 3, 3, 1, 3, 2, 1, 4, 2, 1, 3, 4, 2, 2, 1, 1, 1, 1, 4, 0, 1, 2, 1, 2, 1, 2, 4, 4, 0, 2, 1, 1, 0, 2],
# 2 : [3, 3, 1, 1, 1, 2, 2, 1, 3, 2, 1, 1, 3, 1, 1, 4, 3, 3, 3, 1, 3, 2, 1, 4, 2, 1, 3, 4, 2, 2, 1, 1, 1, 1, 4, 0, 1, 2, 1, 2, 1, 2, 4, 4, 0, 2, 1, 1, 0, 2],
# 5 : [3, 3, 1, 1, 1, 3, 1, 1, 3, 2, 1, 1, 3, 1, 1, 4, 3, 3, 3, 1, 3, 1, 1, 3, 2, 1, 3, 4, 2, 1, 1, 1, 1, 1, 4, 0, 1, 2, 1, 1, 1, 3, 4, 4, 0, 2, 1, 1, 0, 1],
# 3 : [3, 3, 1, 1, 1, 1, 2, 1, 3, 2, 1, 1, 3, 1, 1, 4, 3, 3, 3, 1, 3, 2, 1, 4, 1, 1, 3, 4, 2, 2, 1, 1, 1, 1, 3, 0, 1, 1, 1, 2, 1, 1, 4, 4, 0, 2, 1, 1, 0, 2],
# 4 : [3, 3, 1, 1, 1, 1, 2, 1, 3, 2, 1, 1, 3, 1, 1, 4, 3, 3, 3, 1, 3, 2, 1, 4, 1, 1, 3, 4, 2, 2, 1, 1, 1, 1, 3, 0, 1, 1, 1, 2, 1, 1, 4, 4, 0, 2, 1, 1, 0, 2],
# }

# print(multiple_list_comparaison(test))


def remove_same_indexes(dict_to_clear,dict_to_take_values_from):
    transposed_lists = zip(*dict_to_take_values_from.values())
    indexes_to_remove = [index for index, values in enumerate(
        transposed_lists) if len(set(values)) == 1]
    if len(indexes_to_remove) == len(list(dict_to_clear.values())[0]) :
        return dict_to_clear
    for key in dict_to_clear.keys():
        for index in sorted(indexes_to_remove, reverse=True):
            dict_to_clear[key].pop(index)
    return dict_to_clear


# dict_to_clear = {1: [1, 2, 3, 4], 2: [1, 6, 3, 8], 3: [1, 10, 6, 12]}
# dict_to_take_values_from = {1: [1, 2, 3, 4], 2: [1, 6, 3, 8]}
# new_dict = remove_same_indexes(dict_to_clear,dict_to_take_values_from)
# print(new_dict)

def softmax(x):
    """Compute softmax values for each sets of scores in x."""
    e_x = np.exp(x - np.max(x))
    return e_x / e_x.sum(axis=0) # only difference