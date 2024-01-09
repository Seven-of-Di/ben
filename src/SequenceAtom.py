from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from functools import total_ordering
from typing import List, Optional, Tuple

from utils import BiddingSuit, Direction 
from parsing_tools import Pbn


@dataclass
@total_ordering
class Bid:
    level: int
    suit: BiddingSuit

    def __post_init__(self):
        if self.level not in range(1, 8):
            raise Exception("Invalid level (must be in 1-7 range)")

    def __lt__(self, other : Bid) -> bool:
        return self.level*5 + self.suit.rank() < other.level*5 + other.suit.rank()

    def __repr__(self) -> str:
        return str(self.level) + self.suit.abbreviation()

    def print_as_lin(self) -> str:
        return str(self.level)+self.suit.abbreviation(verbose_no_trump=False)

    def print_as_pbn(self) -> str:
        return str(self.level)+self.suit.abbreviation(verbose_no_trump=True)

    def __str__(self) -> str:
        return str(self.level)+self.suit.symbol()

    def to_symbol(self):
        return str(self.level)+self.suit.symbol()

    def value(self) -> int :
        return self.level*5 + self.suit.value[0]

    def to_text(self,verbose_NT=True):
        return str(self.level)+self.suit.abbreviation(verbose_NT)

    @staticmethod
    def from_str(string: str) -> Bid:
        return Bid(int(string[0]), BiddingSuit.from_str(string[1:]))


class Declaration(Enum):
    PASS = 0, "Pass", "p", "P"
    DOUBLE = 1, 'X', "d", "X"
    REDOUBLE = 2, "XX", "r", "XX"

    __from_str_map__ = {"PASS": PASS, "P": PASS, "X": DOUBLE, "XX": REDOUBLE}

    __color__ = {PASS: 'green', DOUBLE: 'red', REDOUBLE: "blue"}

    @classmethod
    def from_str(cls, declaration_str: str) -> Declaration:
        return Declaration(cls.__from_str_map__[declaration_str.upper()])

    @classmethod
    def from_int(cls, declaration_int: int) -> Declaration:
        if declaration_int == 1:
            return Declaration.DOUBLE
        if declaration_int == 2:
            return Declaration.REDOUBLE
        return Declaration.PASS

    def print_as_lin(self) -> str:
        return self.value[2]

    def print_as_pbn(self) -> str:
        return self.value[1]

    def abbreviation(self) -> str:
        return self.value[3]

    def color(self) -> str:
        return self.__color__[self.value]

    @classmethod
    def is_str_declaration(cls, bidding_suit_str) -> bool:
        if bidding_suit_str.upper() in cls.__from_str_map__:
            return True
        return False

    def __str__(self) -> str:
        return self.value[1]

@dataclass
class Alert:
    text: str
    artificial: bool = False
@dataclass
class SequenceAtom():
    declaration: Optional[Declaration]
    bid: Optional[Bid]
    alert: Optional[Alert] = None

    def __post_init__(self):
        if self.declaration and self.bid:
            raise Exception("A sequenceAtom can't be a bid and a declaration")

    def __hash__(self) -> int:
        return hash(repr(self))

    @staticmethod
    def from_str(string: str) -> SequenceAtom:
        if Declaration.is_str_declaration(string):
            return SequenceAtom(declaration=Declaration.from_str(string), bid=None, alert=None)
        return SequenceAtom(bid=Bid.from_str(string), declaration=None, alert=None)

    def to_str(self) -> str:
        if self.declaration != None:
            return self.declaration.__str__()
        elif self.bid != None:
            return self.bid.to_text(verbose_NT=False)
        return ""

    def to_symbol(self) -> str:
        if self.declaration != None:
            return self.declaration.__str__()
        elif self.bid != None:
            return self.bid.to_symbol()
        return ""

    def abbreviation(self) -> str:
        if self.declaration != None:
            return self.declaration.abbreviation()
        elif self.bid != None:
            return self.bid.to_text()
        return ""

    def __str__(self) -> str:
        string = ""
        if self.declaration != None:
            string += self.declaration.__str__()
        elif self.bid != None:
            string += self.bid.__str__()
        if self.alert != None:
            string += "("+self.alert.text+")"
        return string

    def __repr__(self) -> str:
        string = ""
        if self.declaration != None:
            string += self.declaration.__str__()
        elif self.bid != None:
            string += self.bid.__str__()
        if self.alert != None:
            string += "("+self.alert.text+")"
        return string

    def print_as_lin(self) -> str:
        if self.declaration != None:
            return self.declaration.print_as_lin()
        elif self.bid != None:
            return self.bid.print_as_lin()
        raise Exception("print_as_lin : Invalid sequence atom")

    def print_as_pbn(self) -> str:
        if self.declaration != None:
            return self.declaration.print_as_pbn()
        elif self.bid != None:
            return self.bid.print_as_pbn()
        raise Exception("print_as_lin : Invalid sequence atom")

    def is_bid(self) -> bool:
        if self.bid is not None:
            return True
        return False

    def is_not_pass(self) -> bool :
        return False if self.declaration==Declaration.PASS else True

    def is_declaration(self) -> bool:
        if self.declaration is not None:
            return True
        return False


@dataclass
class FinalContract:
    bid: Optional[Bid]
    declaration: Declaration
    declarer: Optional[Direction]

    @staticmethod
    def from_str(string: str) -> FinalContract:
        """
        4SXN,Pass...
        """
        string = string.replace(' ', '')
        if 'P' in string:
            return FinalContract(bid=None, declaration=Declaration.PASS, declarer=None)
        declarer = Direction.from_str(string[-1])
        string = string[:-1]
        declaration = Declaration.from_int(string.count('X'))
        string = string.replace('X', '')
        if string.upper() == "PASS" or string.upper() == "P":
            return FinalContract(bid=None, declaration=declaration, declarer=declarer)
        return FinalContract(bid=Bid.from_str(string), declaration=declaration, declarer=declarer)

    @staticmethod
    def from_pbn(string: str) -> Optional[FinalContract]:
        final_contract = Pbn.get_tag_content(
            string, "Contract")+Pbn.get_tag_content(string, "Declarer")
        if final_contract:
            return FinalContract.from_str(final_contract)
        else:
            return None

    def print_as_pbn(self) -> str:
        string = ""
        if self.declarer:
            string += Pbn.print_tag("Declarer", self.declarer.abbreviation())
        if not self.bid:
            return string + Pbn.print_tag("Contract", "Pass")
        elif self.declaration == Declaration.PASS:
            return string + Pbn.print_tag("Contract", self.bid.print_as_pbn())
        else:
            return string + Pbn.print_tag("Contract", self.bid.print_as_pbn()+self.declaration.print_as_pbn())

    def print_pbn_abbrevation(self) -> str:
        if not self.bid or not self.declarer:
            return "Pass"
        else:
            if self.declaration != Declaration.PASS:
                return self.bid.print_as_pbn()+self.declaration.value[1]
            else:
                return self.bid.print_as_pbn()

    def __str__(self) -> str:
        if not self.bid or not self.declarer:
            return "Contrat final : passe général"
        else:
            return "{}{}{}".format(self.bid.__str__(),self.declaration.abbreviation() if self.declaration!=Declaration.PASS else '',self.declarer.abbreviation())
    
    def abbreviation(self) -> str:
        if not self.bid or not self.declarer:
            return "P"
        else:
            return "{}{}{}".format(self.bid.print_as_pbn(),self.declaration.abbreviation() if self.declaration!=Declaration.PASS else '',self.declarer.abbreviation())
