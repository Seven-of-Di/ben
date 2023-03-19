import asyncio
from copy import deepcopy
from typing import Dict, List

import requests
from utils import board_number_to_vul, Direction, Card_, Diag, DIRECTIONS, BiddingSuit, VULS_REVERSE
from PlayRecord import Trick
from bidding import bidding
from DealRecord import DealRecord
from Deal import Deal
from Sequence import Sequence, SequenceAtom
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
        deal_records: List[Deal] = [
            Deal.from_pbn(board) for board in boards[10:14]]

    def play_full_deal(deal: Deal):
        print(deal.board_number)
        full_play = asyncio.run(AsyncFullBoardPlayer(diag=deepcopy(deal.diag), vuls=[
            deal.ns_vulnerable, deal.ew_vulnerable], dealer=deal.dealer, models=MODELS).async_full_board())
        sequence = Sequence.from_str_list(full_play["auction"])
        contract = sequence.calculate_final_contract(dealer=deal.dealer)
        if contract is None or contract.bid is None or contract.declarer is None:
            return DealRecord(sequence=sequence, play_record=None, score=0, names=None)
        play_record = PlayRecord.from_tricks_as_list(
            trump=contract.bid.suit, list_of_tricks=full_play["play"], declarer=contract.declarer)
        score = calculate_score(level=contract.bid.level, suit=contract.bid.suit, doubled=contract.declaration.value[0], tricks=play_record.number_of_tricks, vulnerable=deal.ns_vulnerable if contract.declarer in [
                                Direction.NORTH, Direction.SOUTH] else deal.ew_vulnerable)
        return DealRecord(sequence=sequence, play_record=play_record, score=score, names=None)

    boards = [Board(deal, play_full_deal(deal)) for deal in deal_records]
    text_pbn = "\n".join([board.print_as_pbn() for board in boards])
    repo = git.Repo(search_parent_directories=True)  # type:ignore
    sha = repo.head.object.hexsha
    with open("./test_data/{}.pbn".format(sha), "w") as f:
        f.write(text_pbn)


def send_request(type_of_action: str, data: Dict, direction: Direction):
    port = "http://localhost:{}".format(
        "8081" if direction in [Direction.NORTH, Direction.SOUTH] else "8082")
    res = requests.post('{}/{}'.format(port, type_of_action), json=data)
    print(res.json())
    return res.json()


def run_tm_btwn_ben_versions():

    def play_full_deal(deal: Deal) -> DealRecord:
        sequence = Sequence([], None)
        current_player = deal.dealer

        # Bidding
        while not sequence.is_done():
            print(sequence)
            data = {
                "hand": deal.diag.hands[current_player].to_pbn(),
                "dealer": deal.dealer.abbreviation(),
                "vuln": VULS_REVERSE[(deal.ns_vulnerable, deal.ew_vulnerable)],
                "auction": sequence.get_as_ben_request()
            }
            res = send_request("place_bid", data, current_player)
            if not sequence.append_with_check(SequenceAtom.from_str(res["bid"])) :
                raise Exception
            current_player = current_player.offset(1)

        contract = sequence.calculate_final_contract(dealer=deal.dealer)
        if contract is None or contract.declarer is None or contract.bid is None:
            return DealRecord(sequence=sequence, play_record=None, score=0, names=None)

        # Leading
        declarer = contract.declarer
        current_player = declarer.offset(1)
        dummy = declarer.offset(2)
        data = {
            "hand": deal.diag.hands[current_player].to_pbn(),
            "dealer": deal.dealer.abbreviation(),
            "vuln": VULS_REVERSE[(deal.ns_vulnerable, deal.ew_vulnerable)],
            "auction": sequence.get_as_ben_request()
        }
        res = send_request(type_of_action="make_lead",
                           data=data, direction=current_player)
        deal.diag.hands[current_player].remove(Card_.from_str(res["card"]))
        tricks = [[res["card"]]]
        
        # Card playing
        leader = current_player
        current_player = dummy
        for _ in range(47):
            data = {
                "hand": deal.diag.hands[current_player].to_pbn() if current_player!=dummy else deal.diag.hands[declarer].to_pbn(),
                "dummy_hand": deal.diag.hands[dummy].to_pbn(),
                "dealer": deal.dealer.abbreviation(),
                "vuln": VULS_REVERSE[(deal.ns_vulnerable, deal.ew_vulnerable)],
                "auction": sequence.get_as_ben_request(),
                "contract": str(contract),
                "contract_direction": contract.declarer.abbreviation(),
                "next_player": current_player.abbreviation(),
                "tricks": tricks
            }
            res = send_request(type_of_action="play_card",
                               data=data, direction=current_player)
            tricks[-1].append(res["card"])
            deal.diag.hands[current_player].remove(Card_.from_str(res["card"]))
            if res["claim_the_rest"]:
                play_record = PlayRecord.from_tricks_as_list(
                    contract.bid.suit, tricks, declarer)
                tricks_count = play_record.length_wo_incomplete()
                tricks_left = 13-tricks_count
                score = calculate_score(contract.bid.level, suit=contract.bid.suit, doubled=contract.declaration.value[0], tricks=play_record.number_of_tricks +
                                        tricks_left, vulnerable=deal.ns_vulnerable if declarer in [Direction.NORTH, Direction.EAST] else deal.ew_vulnerable)
                return DealRecord(sequence=sequence, play_record=play_record, score=score, names=None)

            current_player = current_player.offset(1)
            if len(tricks[-1]) == 4:
                leader = Trick.from_list(leader=leader,trick_as_list=[Card_.from_str(c) for c in tricks[-1]]).winner(trump = contract.bid.suit)
                current_player=leader
                tricks.append([])

        # Last trick
        for _ in range(4):
            deal.diag.hands[current_player].remove(
                deal.diag.hands[current_player].cards[0])
            current_player = current_player.offset(1)
        play_record = PlayRecord.from_tricks_as_list(
            contract.bid.suit, tricks, declarer)
        score = calculate_score(contract.bid.level, suit=contract.bid.suit, doubled=contract.declaration.value[0], tricks=play_record.number_of_tricks,
                                vulnerable=deal.ns_vulnerable if declarer in [Direction.NORTH, Direction.EAST] else deal.ew_vulnerable)
        return DealRecord(sequence=sequence, play_record=play_record, score=score, names=None)

    with open("./test_data/test_data.pbn") as f:
        boards = f.read().split("\n\n")
        deals: List[Deal] = [
            Deal.from_pbn(board) for board in boards[:20]]

    boards = [Board(deal, play_full_deal(deepcopy(deal))) for deal in deals]
    text_pbn = "\n".join([board.print_as_pbn() for board in boards])
    with open("./test_data/{}.pbn".format("First test table"), "w") as f:
        f.write(text_pbn)


def load_test_pbn(file: str):
    with open("./test_data/{}".format(file)) as f:
        raw_str_data = f.read()

    boards_str = raw_str_data.split("\n\n")
    boards = [Board.from_pbn(board_str) for board_str in boards_str]
    return boards


def compare_two_boards(board_1: Board, board_2: Board):
    assert board_1.deal.diag == board_1.deal.diag
    assert board_1.deal_record.sequence and board_2.deal_record.sequence
    print(board_1.deal.board_number)
    if board_1.deal_record.sequence != board_2.deal_record.sequence:
        print("Different sequences")
    if board_1.deal_record.sequence.calculate_final_contract(board_1.deal.dealer) != board_2.deal_record.sequence.calculate_final_contract(board_1.deal.dealer):
        return
    if board_1.deal_record.play_record is None or board_2.deal_record.play_record is None:
        return
    if board_1.deal_record.score == board_2.deal_record.score:
        return
    print(board_1.deal_record.play_record.as_unordered_one_dimension_list())
    print(board_2.deal_record.play_record.as_unordered_one_dimension_list())


def compare_two_tests(set_of_boards_1: List[Board], set_of_boards_2: List[Board]):
    [compare_two_boards(board_1, board_2) for board_1,
     board_2 in zip(set_of_boards_1, set_of_boards_2)]


if __name__ == "__main__":
    run_tm_btwn_ben_versions()
    # tests = run_tests()
    # compare_two_tests(load_test_pbn("avant.pbn"),
    #                   load_test_pbn("après.pbn"))
    # load_test_pbn("c4f380988fc67c0fe6e5f4bc5502d67a3b45d2c0.pbn")
    # link = r"https://play.intobridge.com/hand?lin=pn|GiovanniM,Ben,Ben,Ben|md|3S8764H86DQ852C832,SAHQ7DKT9643CAKJ6,S3HAKJ9543D7CQ975,SKQJT952HT2DAJCT4|ah|Board%2013|mb|1H|mb|1S|mb|p|mb|3D|mb|3H|mb|3S|mb|p|mb|3N|mb|p|mb|4S|mb|p|mb|p|mb|p|pc|H8|pc|H7|pc|HJ|pc|H2|pc|HA|pc|HT|pc|H6|pc|HQ|pc|HK|pc|S2|pc|S4|pc|SA|pc|CA|pc|C5|pc|C4|pc|C2|pc|CK|pc|C7|pc|CT|pc|C3|pc|C6|pc|CQ|pc|S9|pc|C8|pc|ST|pc|S6|pc|D6|pc|S3|pc|SK|pc|S7|pc|D3|pc|H3|pc|DJ|pc|DQ|pc|DK|pc|D7|pc|CJ|pc|C9|pc|S5|pc|S8|pc|D2|pc|D4|pc|H4|pc|DA|pc|SJ|pc|D5|pc|D9|pc|H5|pc|SQ|pc|D8|pc|DT|pc|H9|mc|10|sv|b|"
    # print(from_lin_to_request(link, Card_.from_str("C9")))

    # print(from_lin_to_request(link, None))
