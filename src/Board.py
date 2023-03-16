from __future__ import annotations
from dataclasses import dataclass
from DealRecord import DealRecord
from Deal import Deal
from parsing_tools import Pbn

@dataclass
class Board :
    deal : Deal
    deal_record : DealRecord

    def print_as_pbn(self) -> str :
        deal_pbn = self.deal.print_as_pbn() 
        record_pbn =self.deal_record.print_as_pbn(dealer = self.deal.dealer,ns_vulnerable=self.deal.ns_vulnerable,ew_vulnerable=self.deal.ew_vulnerable)
        return "{}{}{}\n".format(Pbn.print_tag("Event","Ben version Test"),deal_pbn,record_pbn)

    @staticmethod
    def from_pbn(str_data : str) -> Board :
        deal = Deal.from_pbn(str_data)
        deal_record = DealRecord.from_pbn(str_data)
        if deal_record is None :
            raise Exception("Empty deal record")
        print(deal.board_number)
        return Board(deal,deal_record)
    
