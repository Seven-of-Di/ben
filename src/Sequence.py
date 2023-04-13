from __future__ import annotations
from dataclasses import dataclass
import logging

from utils import Direction, BiddingSuit
from parsing_tools import Pbn
from score_calculation import calculate_score


from SequenceAtom import Declaration, FinalContract, SequenceAtom, Bid
from typing import Dict, List, Optional


@dataclass
class Sequence:
    sequence: List[SequenceAtom]
    final_contract: Optional[FinalContract]

    def delete(self) -> None:
        """Delete the last bid"""
        self.sequence.pop()

    def check_append_validity(self, seq_atom_to_add: SequenceAtom) -> bool:
        """Check if a new bid is valid"""
        if self.is_done():
            logging.warning("Bidding done, can't add")
            return False
        if seq_atom_to_add.bid:  # If bid
            for seq_atom in reversed(self.sequence):
                if seq_atom.bid:
                    if seq_atom_to_add.bid > seq_atom.bid:
                        return True
                    return False
            return True
        if seq_atom_to_add.declaration == Declaration.PASS:  # If Pass
            return True
        if seq_atom_to_add.declaration == Declaration.DOUBLE:  # If Double
            if len(self.sequence) >= 1 and self.sequence[-1].bid:
                return True
            if len(self.sequence) >= 3 and self.sequence[-3].bid and self.sequence[-2].declaration == Declaration.PASS:
                return True
        if seq_atom_to_add.declaration == Declaration.REDOUBLE:  # If Redouble
            if len(self.sequence) >= 1 and self.sequence[-1].declaration == Declaration.DOUBLE:
                return True
            if len(self.sequence) >= 3 and self.sequence[-3].declaration == Declaration.DOUBLE and self.sequence[-2].declaration == Declaration.PASS and self.sequence[-1].declaration == Declaration.PASS:
                return True
        return False

    def get_all_available_bids(self) -> List[SequenceAtom]:
        aivalable_bid_list: List[SequenceAtom] = []
        for atom in [SequenceAtom(declaration=None, bid=Bid(i, s), alert=None) for i in range(1, 8) for s in BiddingSuit]:
            if self.check_append_validity(atom):
                aivalable_bid_list.append(atom)

        for atom in [SequenceAtom(declaration=d, bid=None, alert=None) for d in Declaration]:
            if self.check_append_validity(atom):
                aivalable_bid_list.append(atom)

        return aivalable_bid_list

    def append_with_check(self, seq_atom_to_add: SequenceAtom) -> bool:
        """Add a bid if it's valid, return true if it's the case"""
        if self.check_append_validity(seq_atom_to_add=seq_atom_to_add):
            self.sequence.append(seq_atom_to_add)
            return True
        return False

    def get_current_contract(self, dealer: Direction) -> FinalContract:
        contract = FinalContract(None, Declaration.PASS, None)
        for index, seq_atom in enumerate(reversed(self.sequence)):
            if seq_atom.bid is not None:
                contract.bid = seq_atom.bid
                contract.declarer = self.get_declarer(
                    dealer, contract.bid.suit, dealer.offset(len(self.sequence)-index-1))
                return contract
            if seq_atom.declaration is not None and seq_atom.declaration.value[0] > contract.declaration.value[0]:
                contract.declaration = seq_atom.declaration
        return contract

    def calculate_final_contract(self, dealer: Direction) -> Optional[FinalContract]:
        if self.is_done():
            declaration = Declaration.PASS
            for index, seq_atom in enumerate(reversed(self.sequence)):
                if seq_atom.declaration != Declaration.PASS and seq_atom.declaration != None and declaration == Declaration.PASS:
                    declaration = seq_atom.declaration
                if seq_atom.bid != None:
                    return FinalContract(bid=seq_atom.bid, declaration=declaration, declarer=self.get_declarer(dealer=dealer, suit=seq_atom.bid.suit, side=dealer.offset(len(self.sequence)-index-1)))
            return FinalContract(bid=None, declaration=declaration, declarer=None)
        return None

    def get_declarer(self, dealer: Direction, suit: BiddingSuit, side: Direction) -> Direction:
        for index, seq_atom in enumerate(self.sequence):
            if seq_atom.bid and seq_atom.bid.suit == suit and (side == dealer.offset(index) or side == dealer.offset(index).partner()):
                return dealer.offset(index)
        raise Exception("Get_declarer function isn't working")

    def is_valid(self) -> bool:
        checking_seq = Sequence([], None)
        for seq_atom in self.sequence:
            if not checking_seq.append_with_check(seq_atom):
                logging.error("Invalid atom : ", seq_atom)
                return False
        return True

    def is_done(self) -> bool:
        if len(self.sequence) <= 3:
            return False
        elif len(self.sequence) == 4:
            for seq_atom in self.sequence[1:]:
                if seq_atom.declaration != Declaration.PASS:
                    return False
            return True
        elif len(self.sequence) >= 5:
            for seq_atom in self.sequence[-3:]:
                if seq_atom.declaration != Declaration.PASS:
                    return False
            return True
        return False

    def get_str_bidding_by_direction(self, dealer: Direction) -> Dict[Direction, List[str]]:
        dic = {dir: [] for dir in Direction}
        for i, atom in enumerate(self.sequence):
            dic[Direction(i % 4).offset(dealer.value)
                ].append(atom.abbreviation())
        return dic

    def get_bidding_by_direction(self, dealer: Direction) -> Dict[Direction, List[SequenceAtom]]:
        dic = {dir: [] for dir in Direction}
        for i, atom in enumerate(self.sequence):
            dic[Direction(i % 4).offset(dealer.value)
                ].append(atom)
        return dic

    def is_two_players_bidding(self, player_dir: Direction, dealer: Direction):
        bidding_by_direction = self.get_bidding_by_direction(dealer=dealer)
        for dir, atom_list in bidding_by_direction.items():
            if not player_dir.opponents(dir):
                continue
            for seq_atom in atom_list:
                if seq_atom.declaration != Declaration.PASS:
                    return False
        return True

    def get_opening(self) -> SequenceAtom | None:
        for atom in self.sequence:
            if atom.is_bid():
                return atom
        return None

    def get_first_available_bid_in_suit(self, bidding_suit: BiddingSuit) -> Bid | None:
        for atom in self.get_all_available_bids():
            if atom.bid and atom.bid.suit == bidding_suit:
                return atom.bid
        return None

    def is_responder(self,dealer:Direction,dir:Direction) :
        for i,atom in enumerate(self.sequence) :
            if atom.is_bid() and dealer.offset(i) in [dir,dir.partner()] :
                return True if dealer.offset(i)==dir.partner() else False
        return False



    #### Scrapping ####

    @staticmethod
    def from_str_list(str_list: List[str], dealer: Optional[Direction] = None) -> Sequence:
        if dealer:
            return Sequence([SequenceAtom.from_str(str_atom) for str_atom in str_list], Sequence([SequenceAtom.from_str(str_atom) for str_atom in str_list], None).calculate_final_contract(dealer))
        else:
            return Sequence([SequenceAtom.from_str(str_atom) for str_atom in str_list], None)

    @staticmethod
    def from_pbn(string: str) -> Optional[Sequence]:
        sequence = []
        str_sequence = Pbn.get_content_under_tag(string, "Auction")
        if str_sequence is None:
            return None
        alerts = Pbn.get_all_alerts(string)
        for str_seq_atom in str_sequence.split():
            if "=" in str_seq_atom:
                sequence[-1].alert = alerts.pop(0)
            else:
                sequence.append(SequenceAtom.from_str(str_seq_atom))
        return Sequence(sequence, FinalContract.from_pbn(string))

    @staticmethod
    def from_lin(string: str) -> Sequence:
        sequence = []
        for str_seq_atom in string.split():
            sequence.append(SequenceAtom.from_str(str_seq_atom))
        return Sequence(sequence, None)

    #### Writing ####

    def print_as_lin(self) -> str:
        string = ""
        for atom in self.sequence:
            string += "|mb|"+atom.print_as_lin()
            if atom.alert:
                string += "!|an|"+atom.alert
        return string

    def print_as_pbn(self, dealer: Direction, tricks: int, ns_vulnerable: bool, ew_vulnerable: bool) -> str:
        string = ""
        final_contract = self.calculate_final_contract(dealer)
        if final_contract:
            string += final_contract.print_as_pbn()
            if final_contract.declarer and final_contract.bid:  # No 4 Passes
                string += Pbn.print_tag("Result", str(tricks))
                if final_contract.declarer == Direction.NORTH or final_contract.declarer == Direction.SOUTH:
                    string += Pbn.print_tag("Score", "NS "+str(calculate_score(level=final_contract.bid.level, suit=final_contract.bid.suit,
                                            doubled=final_contract.declaration.value[0], tricks=tricks, vulnerable=ns_vulnerable)))
                else:
                    string += Pbn.print_tag("Score", "NS "+str(-calculate_score(level=final_contract.bid.level, suit=final_contract.bid.suit,
                                            doubled=final_contract.declaration.value[0], tricks=tricks, vulnerable=ns_vulnerable)))
            else:
                string += Pbn.print_tag("Score", "NS 0")
        string += Pbn.print_tag("Auction", dealer.abbreviation())
        i = 0
        alerts = {}
        for j, atom in enumerate(self.sequence):
            string += '{0:7}'.format(atom.print_as_pbn())
            if atom.alert:
                string += "="+str(i+1)+"= "
                alerts[i] = atom.alert
                i += 1
            if j % 4 == 3:
                string += "\n"
        string += "\n" if string[-1]!="\n" else ""
        for index in range(i):
            string += '[Note "{}:'.format(index+1)+alerts[index]+'"]\n'
        string = string[:-1] if string[-2:]=="\n\n" else string
        return string

    def __str__(self):
        string = ""
        #string += '{0:10}{1:10}{2:10}{3:10}\n'.format('N','E','S','W')
        for i in range(0, len(self.sequence)):
            string += '{0:10}'.format(self.sequence[i].__str__())
            if i % 4 == 3:
                string += "\n"
        return string

    def get_as_str_list(self) -> List[str]:
        return [at.to_str() for at in self.sequence]
    
    def get_as_ben_request(self) -> List[str]:
        return [at.to_str().upper() for at in self.sequence]

    def print_as_ben_format(self, dealer: Direction) -> List[str]:
        res: List[str] = []
        for dir in Direction:
            if dir == dealer:
                break
            dir.offset(1)
            res.append('PAD_START')
        res += [at.print_as_pbn().upper() for at in self.sequence]
        return res

    def __len__(self):
        return len(self.sequence)
