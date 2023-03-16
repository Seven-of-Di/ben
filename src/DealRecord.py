from __future__ import annotations

from dataclasses import InitVar, dataclass
from msilib import sequence
from typing import Dict, List, Optional

from utils import Direction, Card_
from parsing_tools import Pbn
from Sequence import Sequence
from PlayRecord import PlayRecord


@dataclass()
class DealRecord:
    """
    The record of a played deal.
    """

    sequence: Optional[Sequence]
    play_record: Optional[PlayRecord]
    score: int
    names: Optional[Dict[Direction, str]]

    @staticmethod
    def from_pbn(string: str) -> Optional[DealRecord]:
        score = Pbn.get_score(string)
        if score is None:
            return None
        sequence = Sequence.from_pbn(string)
        play_record = PlayRecord.from_pbn(string)
        names = {dir: Pbn.get_tag_content(
            string, Pbn.direction_to_tag(dir)) for dir in Direction}
        return DealRecord(sequence=sequence, play_record=play_record, names=names, score=score)

    def __str__(self) -> str:
        string = ""
        if self.names:
            for dir in Direction:
                if self.names[dir]:
                    string += '{0:10}'.format(self.names[dir])
            string += "\n"
        else:
            string += '{0:10}{1:10}{2:10}{3:10}\n'.format('N', 'E', 'S', 'W')
        if self.sequence:
            string += self.sequence.__str__()
        if self.play_record:
            string += self.play_record.__str__()
        return string

    def print_as_pbn(self, dealer: Direction, ns_vulnerable: bool, ew_vulnerable: bool) -> str:
        string = ""
        if self.names:
            for dir in Direction:
                if self.names[dir]:
                    string += Pbn.print_tag(Pbn.direction_to_tag(dir),
                                            self.names[dir])
            string += "\n"
        if self.sequence:
            if not self.play_record:
                string += self.sequence.print_as_pbn(
                    dealer=dealer, tricks=0, ns_vulnerable=ns_vulnerable, ew_vulnerable=ew_vulnerable)
            else:
                string += self.sequence.print_as_pbn(dealer=dealer, tricks=self.play_record.number_of_tricks,
                                                     ns_vulnerable=ns_vulnerable, ew_vulnerable=ew_vulnerable)
        if self.play_record:
            string += self.play_record.print_as_pbn()
        return string
