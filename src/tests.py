import asyncio
from copy import deepcopy
from typing import List
from utils import board_number_to_vul, Direction, Card_, Diag, DIRECTIONS, BiddingSuit
from PlayRecord import Trick
from bidding import bidding
from DealRecord import DealRecord
from Deal import Deal
from Sequence import Sequence
from PlayRecord import PlayRecord
import json
from FullBoardPlayer import AsyncFullBoardPlayer
from score_calculation import calculate_score
from Board import Board
import git



def from_lin_to_request(lin_str: str, card_to_remove_after: Card_ | None = None, bid_to_remove_after: str | None = None):
    if card_to_remove_after is not None and bid_to_remove_after is not None:
        raise Exception("bid and play are both not None")

    lin_str = lin_str.replace("%7C", '|')
    lin_str = lin_str.split("lin=", maxsplit=1)[1]
    board_number = lin_str.split("Board%20")[1].split('|')[0]
    vul_str = board_number_to_vul(int(board_number))
    lin_str = lin_str.split("|", maxsplit=3)[3]
    lin_dealer_to_direction = {
        "1": Direction.SOUTH, "2": Direction.WEST, "3": Direction.NORTH, "4": Direction.EAST}
    dealer: Direction = lin_dealer_to_direction[lin_str[0]]
    diag_lin = lin_str[1:].split("|")[0]
    diag = Diag.init_from_lin(diag_lin)
    lin_str = lin_str[2:].split("|", maxsplit=1)[1]
    lin_str = "".join([substr for substr in lin_str.split("7C")])

    def bidding_el_to_pbn(el: str):
        trans_dict = {
            "d": "X",
            "r": "XX",
            "p": "PASS"
        }
        return el if el not in trans_dict else trans_dict[el]

    bidding_str = lin_str.split("mb|")[1:-1]
    bidding_str = [bidding_el_to_pbn(el.strip("|")) for el in bidding_str]
    print(bidding_str)

    play_str = lin_str.split("pc")[1:-1]
    play = [s.strip("|") for s in play_str]

    for i, card in enumerate(play):
        if card == str(card_to_remove_after):
            play = play[:i+1]
            break

    for i, bid in enumerate(bidding_str):
        if bid == bid_to_remove_after:
            bidding_str = bidding_str[:i+1]
            break

    n = 4
    play_as_list_of_list = [play[i * n:(i + 1) * n]
                            for i in range((len(play) + n - 1) // n)]

    # Full play json
    if card_to_remove_after is None and bid_to_remove_after is None:
        return json.dumps({
            "hands": diag.print_as_pbn(),
            "dealer": dealer.abbreviation(),
            "vuln": vul_str
        })

    # Bidding json
    if bid_to_remove_after is not None:
        turn_to_play = dealer.offset(len(bidding_str))
        return json.dumps({
            "hand": diag.hands[turn_to_play].print_as_pbn(),
            "dealer": dealer.abbreviation(),
            "vuln": vul_str,
            "auction": bidding_str
        })

    for card_str in play:
        diag.remove(Card_.from_str(card_str))
    # Card play json
    contract = bidding.get_contract(
        ['PAD_START'] * DIRECTIONS.index(dealer.abbreviation()) + bidding_str)
    if contract is None:
        raise Exception("No card play if all pass")
    declarer = Direction.from_str(contract[-1])
    leader = declarer.offset(1)
    turn_to_play = leader
    for trick in play_as_list_of_list:
        if len(trick) != 4:
            turn_to_play = leader.offset(len(trick))
            break
        leader = Trick.from_list(leader, [Card_.from_str(
            card_str) for card_str in trick]).winner(BiddingSuit.from_str(contract[1]))
        turn_to_play = leader

    return json.dumps({
        "hand": diag.hands[turn_to_play].print_as_pbn(),
        "dummy_hand": diag.hands[declarer.offset(2)].print_as_pbn(),
        "dealer": dealer.abbreviation(),
        "vuln": vul_str,
        "contract": contract,
        "contract_direction": declarer.abbreviation(),
        "auction": bidding_str,
        "next_player": turn_to_play.abbreviation(),
        "tricks": play_as_list_of_list
    })


def run_tests():
    from nn.models import MODELS
    with open("./test_data/test_data.pbn") as f:
        boards = f.read().split("\n\n")
        deal_records: List[Deal] = [Deal.from_pbn(board) for board in boards]

    def play_full_deal(deal: Deal):
        full_play = asyncio.run(AsyncFullBoardPlayer(diag=deepcopy(deal.diag), vuls=[
            deal.ns_vulnerable, deal.ew_vulnerable], dealer=deal.dealer, models=MODELS).async_full_board())
        print(full_play)
        sequence = Sequence.from_str_list(full_play["auction"])
        contract = sequence.calculate_final_contract(dealer=deal.dealer)
        if contract is None or contract.bid is None or contract.declarer is None:
            return DealRecord(sequence=sequence, play_record=None, score=0, names=None)
        play_record = PlayRecord.from_tricks_as_list(
            trump=contract.bid.suit, list_of_tricks=full_play["play"], declarer=contract.declarer)
        score=calculate_score(level=contract.bid.level,suit=contract.bid.suit,doubled=contract.declaration.value[0],tricks=play_record.tricks,vulnerable=deal.ns_vulnerable if contract.declarer in [Direction.NORTH,Direction.SOUTH] else deal.ew_vulnerable)
        return DealRecord(sequence=sequence, play_record=play_record, score=score,names=None)

    boards = [Board(deal,play_full_deal(deal)) for deal in deal_records]
    text_pbn = "\n".join([board.print_as_pbn() for board in boards])
    repo = git.Repo(search_parent_directories=True) #type:ignore
    sha = repo.head.object.hexsha
    with open("./test_data/{}.pbn".format(sha),"w") as f :
        f.write(text_pbn)
    print(boards[0].deal)


if __name__ == "__main__":
    tests = run_tests()
    # link = r"https://play.intobridge.com/hand?lin=pn|Bourricot,Ben,Ben,Ben|md|3SAHQJ43DKJ864CJ74,S872HA86DQT7CQT53,SQJT6HKTDA532CAK2,SK9543H9752D9C986|ah|Board%2013|mb|1N|mb|p|mb|2C|mb|p|mb|2S|mb|p|mb|3N|mb|p|mb|p|mb|p|pc|C9|pc|C4|pc|C3|pc|CA|pc|HK|pc|H9|pc|H3|pc|HA|pc|D7|pc|D2|pc|D9|pc|DJ|pc|H4|pc|H6|pc|HT|pc|H2|pc|DA|pc|S3|pc|D4|pc|DT|pc|D3|pc|S4|pc|DK|pc|DQ|pc|D8|pc|S2|pc|D5|pc|S5|pc|D6|pc|S7|pc|S6|pc|H5|pc|SA|pc|S8|pc|ST|pc|S9|pc|HQ|pc|H8|pc|SJ|pc|H7|pc|HJ|pc|C5|pc|SQ|pc|C6|pc|C7|pc|CT|pc|CK|pc|C8|pc|C2|pc|SK|pc|CJ|pc|CQ|mc|11|sv|b|"
    # print(from_lin_to_request(link, Card_.from_str("AH")))

    # print(from_lin_to_request(link, None))
