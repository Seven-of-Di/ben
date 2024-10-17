from __future__ import annotations

import asyncio
from copy import deepcopy
import datetime
import time
from typing import Dict, List

import requests
from utils import (
    board_number_to_vul,
    Direction,
    Card_,
    Diag,
    DIRECTIONS,
    BiddingSuit,
    VULS_REVERSE,
    PlayingMode,
)
from PlayRecord import Trick
from SequenceAtom import Declaration, Alert
from bidding import bidding
from DealRecord import DealRecord
from Deal import Deal
from Sequence import Sequence, SequenceAtom
from PlayRecord import PlayRecord
import json
from FullBoardPlayer import AsyncFullBoardPlayer, PlayingMode
from score_calculation import calculate_score
from Board import Board

NEW_BIDDING_TIME: List[float] = [0, 0]
OLD_BIDDING_TIME: List[float] = [0, 0]
NEW_CARD_TIME: List[float] = [0, 0]
OLD_CARD_TIME: List[float] = [0, 0]
RECEIVING_BOT_NAME = "Ben"
RECEIVED_BOT_NAME = "Lia 2 over 1"
boards_with_different_leads = []
TIME_STAMP = datetime.datetime.now().strftime("%H-%M")
DATE = datetime.datetime.today().strftime("%m_%d_%Y")
CONVENTION_NS_OPEN = "TWO_OVER_ONE"
CONVENTION_NS_CLOSED = "TWO_OVER_ONE"

CONVENTION_EW_OPEN = CONVENTION_NS_CLOSED
CONVENTION_EW_CLOSED = CONVENTION_NS_OPEN

match_name = "{} vs {}".format(RECEIVING_BOT_NAME, RECEIVED_BOT_NAME)
file_name = "{} - {} - {}.pbn".format(match_name, DATE, TIME_STAMP)


def from_lin_to_request(
    lin_str: str,
    card_to_remove_after: Card_ | None = None,
    bid_to_remove_after: str | None = None,
):
    if card_to_remove_after is not None and bid_to_remove_after is not None:
        raise Exception("bid and play are both not None")

    lin_str = lin_str.replace("%7C", "|")
    lin_str = lin_str.split("lin=", maxsplit=1)[1] if "lin=" in lin_str else lin_str
    if "Board" in lin_str:
        lin_str = lin_str.split("Board", maxsplit=1)[1]
        board_number = lin_str.split("|", maxsplit=1)[0].strip()
    else:
        board_number = 1
    vul_str = board_number_to_vul(int(board_number))
    lin_str = lin_str.split("md|", maxsplit=1)[1]
    lin_dealer_to_direction = {
        "1": Direction.SOUTH,
        "2": Direction.WEST,
        "3": Direction.NORTH,
        "4": Direction.EAST,
    }
    # Remove all the alerts, format is |an|alert, with a regular expression
    while "|an|" in lin_str:
        lin_str = (
            lin_str.split("|an|", maxsplit=1)[0]
            + lin_str.split("|an|", maxsplit=1)[1].split("|", maxsplit=1)[1]
        )

    lin_str = lin_str.replace("|pg|", "")
    dealer: Direction = lin_dealer_to_direction[lin_str[0]]
    diag_lin = lin_str[1:].split("|")[0]
    diag = Diag.init_from_lin(diag_lin)
    lin_str = lin_str[2:].split("|", maxsplit=1)[1]
    lin_str = "".join([substr for substr in lin_str.split("7C")])

    def bidding_el_to_pbn(el: str):
        trans_dict = {"d": "X", "r": "XX", "p": "PASS"}
        return el if el not in trans_dict else trans_dict[el]

    bidding_str = lin_str.split("mb|")[1:-1]
    bidding_str.append("p")
    bidding_str = [bidding_el_to_pbn(el.strip("|")) for el in bidding_str]

    play_str = lin_str.split("pc")[1:-1]
    play = [s.strip("|") for s in play_str]

    for i, card in enumerate(play):
        if card == str(card_to_remove_after):
            play = play[: i + 1]
            break

    for i, bid in enumerate(bidding_str):
        if bid == bid_to_remove_after:
            bidding_str = bidding_str[: i + 1]
            break

    n = 4
    play_as_list_of_list = [
        play[i * n : (i + 1) * n] for i in range((len(play) + n - 1) // n)
    ]

    # Full play json
    if card_to_remove_after is None and bid_to_remove_after is None:
        return json.dumps(
            {
                "hands": diag.print_as_pbn(),
                "dealer": dealer.abbreviation(),
                "vuln": vul_str,
            }
        )

    # Bidding json
    if bid_to_remove_after is not None:
        turn_to_play = dealer.offset(len(bidding_str))
        return json.dumps(
            {
                "hand": diag.hands[turn_to_play].print_as_pbn(),
                "dealer": dealer.abbreviation(),
                "vuln": vul_str,
                "auction": bidding_str,
            }
        )

    for card_str in play:
        diag.remove(Card_.from_str(card_str))
    # Card play json
    contract = bidding.get_contract(
        ["PAD_START"] * DIRECTIONS.index(dealer.abbreviation()) + bidding_str
    )
    if contract is None:
        raise Exception("No card play if all pass")
    declarer = Direction.from_str(contract[-1])
    contract = contract[:-1]
    leader = declarer.offset(1)
    turn_to_play = leader
    for trick in play_as_list_of_list:
        if len(trick) != 4:
            turn_to_play = leader.offset(len(trick))
            break
        leader = Trick.from_list(
            leader, [Card_.from_str(card_str) for card_str in trick]
        ).winner(BiddingSuit.from_str(contract[1]))
        turn_to_play = leader

    return json.dumps(
        {
            "hand": (
                diag.hands[turn_to_play].print_as_pbn()
                if turn_to_play != declarer.offset(2)
                else diag.hands[declarer].print_as_pbn()
            ),
            "dummy_hand": diag.hands[declarer.offset(2)].print_as_pbn(),
            "dealer": dealer.abbreviation(),
            "vuln": vul_str,
            "contract": contract,
            "contract_direction": declarer.abbreviation(),
            "auction": bidding_str,
            "next_player": turn_to_play.abbreviation(),
            "tricks": play_as_list_of_list,
            # "cheating_diag_pbn": diag.print_as_pbn(),
        }
    )


def run_tests():
    from nn.models import MODELS

    with open("./test_data/test_data.pbn") as f:
        boards = f.read().split("\n\n")
        deal_records: List[Deal] = [Deal.from_pbn(board) for board in boards[10:14]]

    def play_full_deal(deal: Deal):
        print(deal.board_number)
        full_play = asyncio.run(
            AsyncFullBoardPlayer(
                diag=deepcopy(deal.diag),
                vuls=[deal.ns_vulnerable, deal.ew_vulnerable],
                dealer=deal.dealer,
                models=MODELS,
                playing_mode=PlayingMode.TEAMS,
            ).async_full_board()
        )
        sequence = Sequence.from_str_list(full_play["auction"])
        contract = sequence.calculate_final_contract(dealer=deal.dealer)
        if contract is None or contract.bid is None or contract.declarer is None:
            return DealRecord(sequence=sequence, play_record=None, score=0, names=None)
        play_record = PlayRecord.from_tricks_as_list(
            trump=contract.bid.suit,
            list_of_tricks=full_play["play"],
            declarer=contract.declarer,
        )
        score = calculate_score(
            level=contract.bid.level,
            suit=contract.bid.suit,
            doubled=contract.declaration.value[0],
            tricks=play_record.number_of_tricks,
            vulnerable=(
                deal.ns_vulnerable
                if contract.declarer in [Direction.NORTH, Direction.SOUTH]
                else deal.ew_vulnerable
            ),
        )
        return DealRecord(
            sequence=sequence, play_record=play_record, score=score, names=None
        )

    boards = [Board(deal, play_full_deal(deal)) for deal in deal_records]
    text_pbn = "\n".join([board.print_as_pbn() for board in boards])
    repo = git.Repo(search_parent_directories=True)  # type:ignore
    sha = repo.head.object.hexsha
    with open("./test_data/{}.pbn".format(sha), "w") as f:
        f.write(text_pbn)


def send_request(
    type_of_action: str, data: Dict, direction: Direction, open_room: bool
):
    # new_ben_called = (open_room and direction in [Direction.NORTH, Direction.SOUTH]) or (
    #     not open_room and direction in [Direction.EAST, Direction.WEST])
    ben_called = (
        (
        (
            open_room
            and direction in [Direction.NORTH, Direction.SOUTH]
            and RECEIVING_BOT_NAME == "Ben"
        )
        or (
            open_room
            and direction in [Direction.EAST, Direction.WEST]
            and RECEIVED_BOT_NAME == "Ben"
        )
        or (
            not open_room
            and direction in [Direction.EAST, Direction.WEST]
            and RECEIVING_BOT_NAME == "Ben"
        )
        or (
            not open_room
            and direction in [Direction.NORTH, Direction.SOUTH]
            and RECEIVED_BOT_NAME == "Ben"
        )
        # or type_of_action == "play_card"
    ) 

    ) and not type_of_action == "place_bid"
    port = "http://localhost:{}".format("5001" if ben_called else "5002")
    print("Sending to port {}".format(port))
    start = time.time()
    res = requests.post("{}/{}".format(port, type_of_action), json=data)
    request_time = time.time() - start
    if type_of_action == "play_card":
        if ben_called:
            NEW_CARD_TIME[0] += request_time
            NEW_CARD_TIME[1] += 1
        else:
            OLD_CARD_TIME[0] += request_time
            OLD_CARD_TIME[1] += 1
    elif type_of_action == "place_bid":
        if ben_called:
            NEW_BIDDING_TIME[0] += request_time
            NEW_BIDDING_TIME[1] += 1
        else:
            OLD_BIDDING_TIME[0] += request_time
            OLD_BIDDING_TIME[1] += 1
    
    print(res.json())
    return res.json()


def bid_deal(deal: Deal, open_room: bool):
    sequence = Sequence([], None)
    current_player = deal.dealer

    # Bidding
    while not sequence.is_done():
        print(sequence)
        data = {
            "hand": deal.diag.hands[current_player].to_pbn(),
            "dealer": deal.dealer.abbreviation(),
            "vuln": VULS_REVERSE[(deal.ns_vulnerable, deal.ew_vulnerable)],
            "auction": sequence.get_as_ben_request(),
            "conventions_ew": CONVENTION_EW_OPEN if open_room else CONVENTION_EW_CLOSED,
            "conventions_ns": CONVENTION_NS_OPEN if open_room else CONVENTION_NS_CLOSED,
            "debug_mode": "True",
        }
        res = (
            send_request("place_bid", data, current_player, open_room)
            # if current_player in [Direction.NORTH, Direction.SOUTH]
            # else {"bid": "P", "alert": ""}
        )
        if not sequence.append_with_check(SequenceAtom.from_str(res["bid"])):
            print(Declaration.is_str_declaration(res["bid"]))
            raise Exception(" |{}| is not valid ?".format(str(res["bid"])))
        if "alert" in res:
            if isinstance(res["alert"], str):
                sequence.sequence[-1].alert = Alert(text=res["alert"])
            elif isinstance(res["alert"], Dict):
                sequence.sequence[-1].alert = Alert(
                    text=res["alert"]["text"], artificial=res["alert"]["artificial"]
                )

        current_player = current_player.offset(1)

    return sequence


def lead_deal(deal: Deal, sequence: Sequence, open_room: bool) -> str:
    contract = sequence.calculate_final_contract(dealer=deal.dealer)
    if contract is None or contract.declarer is None or contract.bid is None:
        raise Exception("Final contract is probably pass, can't lead")

    # Leading
    declarer = contract.declarer
    leader = declarer.offset(1)
    data = {
        "hand": deal.diag.hands[leader].to_pbn(),
        "dealer": deal.dealer.abbreviation(),
        "vuln": VULS_REVERSE[(deal.ns_vulnerable, deal.ew_vulnerable)],
        "auction": sequence.get_as_ben_request(),
        "conventions_ew": CONVENTION_EW_OPEN if open_room else CONVENTION_EW_CLOSED,
        "conventions_ns": CONVENTION_NS_OPEN if open_room else CONVENTION_NS_CLOSED,
    }
    res = send_request(
        type_of_action="make_lead", data=data, direction=leader, open_room=open_room
    )
    return res["card"]


def full_card_play(
    deal: Deal, sequence: Sequence, lead: str, open_room: bool
) -> DealRecord:
    contract = sequence.calculate_final_contract(dealer=deal.dealer)
    if contract is None or contract.declarer is None or contract.bid is None:
        raise Exception("Final contract is probably pass, can't lead")
    declarer = contract.declarer
    current_player = declarer.offset(1)
    dummy = declarer.offset(2)
    deal.diag.hands[current_player].remove(Card_.from_str(lead))
    tricks = [[lead]]

    # Card playing
    leader = current_player
    current_player = dummy
    for _ in range(47):
        ranks_in_suit = (
            deal.diag.hands[current_player].suits[Card_.from_str(tricks[-1][0]).suit]
            if len(tricks[-1]) != 0
            else []
        )
        if len(ranks_in_suit) == 1:  # Forced card
            tricks[-1].append(
                Card_(
                    Card_.from_str(tricks[-1][0]).suit, ranks_in_suit[0]
                ).suit_first_str()
            )
            deal.diag.hands[current_player].remove(
                Card_(Card_.from_str(tricks[-1][0]).suit, ranks_in_suit[0])
            )
        else:
            data = {
                "hand": (
                    deal.diag.hands[current_player].to_pbn()
                    if current_player != dummy
                    else deal.diag.hands[declarer].to_pbn()
                ),
                "dummy_hand": deal.diag.hands[dummy].to_pbn(),
                "dealer": deal.dealer.abbreviation(),
                "vuln": VULS_REVERSE[(deal.ns_vulnerable, deal.ew_vulnerable)],
                "auction": sequence.get_as_ben_request(),
                "contract": str(contract),
                "contract_direction": contract.declarer.abbreviation(),
                "next_player": current_player.abbreviation(),
                "tricks": tricks,
                "conventions_ew": CONVENTION_EW_OPEN if open_room else CONVENTION_EW_CLOSED,
                "conventions_ns": CONVENTION_NS_OPEN if open_room else CONVENTION_NS_CLOSED,
                # "cheating_diag_pbn": deal.diag.print_as_pbn(),
                "playing_mode": "teams",
                "logging_infos": {
                    "board_number": deal.board_number,
                    "open_room": open_room,
                    "receiving_bot_name": RECEIVING_BOT_NAME,
                    "received_bot_name": RECEIVED_BOT_NAME,
                    "file_name": file_name,
                },
            }
            res = send_request(
                type_of_action="play_card",
                data=data,
                direction=current_player,
                open_room=open_room,
            )
            tricks[-1].append(res["card"])
            deal.diag.hands[current_player].remove(Card_.from_str(res["card"]))
            if res["claim_the_rest"]:
                play_record = PlayRecord.from_tricks_as_list(
                    contract.bid.suit, tricks, declarer
                )
                tricks_count = play_record.length_wo_incomplete()
                play_record.number_of_tricks += 13 - tricks_count
                score = calculate_score(
                    contract.bid.level,
                    suit=contract.bid.suit,
                    doubled=contract.declaration.value[0],
                    tricks=play_record.number_of_tricks,
                    vulnerable=(
                        deal.ns_vulnerable
                        if declarer in [Direction.NORTH, Direction.EAST]
                        else deal.ew_vulnerable
                    ),
                )
                return DealRecord(
                    sequence=sequence, play_record=play_record, score=score, names=None
                )

        current_player = current_player.offset(1)
        if len(tricks[-1]) == 4:
            leader = Trick.from_list(
                leader=leader, trick_as_list=[Card_.from_str(c) for c in tricks[-1]]
            ).winner(trump=contract.bid.suit)
            current_player = leader
            tricks.append([])

    # Last trick
    for _ in range(4):
        tricks[-1].append(deal.diag.hands[current_player].cards[0].suit_first_str())
        deal.diag.hands[current_player].remove(deal.diag.hands[current_player].cards[0])
        current_player = current_player.offset(1)
    play_record = PlayRecord.from_tricks_as_list(contract.bid.suit, tricks, declarer)
    score = calculate_score(
        contract.bid.level,
        suit=contract.bid.suit,
        doubled=contract.declaration.value[0],
        tricks=play_record.number_of_tricks,
        vulnerable=(
            deal.ns_vulnerable
            if declarer in [Direction.NORTH, Direction.EAST]
            else deal.ew_vulnerable
        ),
    )
    return DealRecord(
        sequence=sequence, play_record=play_record, score=score, names=None
    )


def play_full_deal(
    deal: Deal,
    force_same_sequence: bool,
    force_same_lead: bool,
    force_same_card_play: bool,
    other_play_record: DealRecord | None,
    open_room: bool,
) -> DealRecord:
    sequence = (
        other_play_record.sequence
        if force_same_sequence and other_play_record is not None
        else bid_deal(deal, open_room)
    )

    if sequence is None:
        raise Exception("Sequence should not be None")

    contract = sequence.calculate_final_contract(dealer=deal.dealer)

    if contract is None or contract.declarer is None or contract.bid is None:
        return DealRecord(sequence=sequence, play_record=None, score=0, names=None)

    lead = (
        other_play_record.play_record.as_unordered_one_dimension_list()[
            0
        ].suit_first_str()
        if force_same_lead and sequence == other_play_record.sequence
        else lead_deal(deal, sequence, open_room)
    )
    if lead is None:
        raise Exception("Leader shouldn't be None")

    if (
        force_same_card_play
        and contract
        == other_play_record.sequence.calculate_final_contract(dealer=deal.dealer)
        and other_play_record is not None
    ):
        if (
            lead
            == other_play_record.play_record.as_unordered_one_dimension_list()[
                0
            ].suit_first_str()
        ):
            play_record = deepcopy(other_play_record)
            play_record.sequence = sequence
            return play_record
        boards_with_different_leads.append(deal.board_number)

    return full_card_play(deal, sequence, lead, open_room)


def run_deal_on_both_rooms(
    deal: Deal,
    force_same_sequence: bool = False,
    force_same_lead: bool = False,
    force_same_card_play: bool = False,
    ditch_if_same_bidding: bool = False,
) -> str:
    open_room_record = play_full_deal(
        deepcopy(deal), False, False, False, None, open_room=True
    )
    open_room_record.names = {
        Direction.SOUTH: RECEIVING_BOT_NAME,
        Direction.NORTH: RECEIVING_BOT_NAME,
        Direction.EAST: RECEIVED_BOT_NAME,
        Direction.WEST: RECEIVED_BOT_NAME,
    }

    closed_room_record = play_full_deal(
        deepcopy(deal),
        force_same_sequence=force_same_sequence,
        force_same_lead=force_same_lead,
        force_same_card_play=force_same_card_play,
        other_play_record=open_room_record,
        open_room=False,
    )
    if (
        ditch_if_same_bidding
        and closed_room_record.sequence
        and open_room_record.sequence
        and (
            open_room_record.sequence.print_as_ben_format(dealer=deal.dealer)
            == closed_room_record.sequence.print_as_ben_format(dealer=deal.dealer)
        )
    ):
        return ""
    closed_room_record.names = {
        Direction.EAST: RECEIVING_BOT_NAME,
        Direction.WEST: RECEIVING_BOT_NAME,
        Direction.NORTH: RECEIVED_BOT_NAME,
        Direction.SOUTH: RECEIVED_BOT_NAME,
    }
    open_room_board = Board(deal, open_room_record)
    closed_room_board = Board(deal, closed_room_record)

    return "{}\n{}".format(
        open_room_board.print_as_pbn(open_room=True),
        closed_room_board.print_as_pbn(open_room=False),
    )


def count_average_hcp():
    with open("./test_data/10K_ranked_deals.pbn") as f:
        boards = f.read().strip("\n").split("\n\n")
        deals: List[Deal] = [Deal.from_pbn(board) for board in boards]
    hcp_per_dir = {dir: 0 for dir in Direction}
    for deal in deals:
        for dir in Direction:
            hcp_per_dir[dir] += deal.diag.hands[dir].hcp()
    average_hcp_per_dir = {
        dir: total_hcp / len(deals) for dir, total_hcp in hcp_per_dir.items()
    }
    print(len(boards))
    print(average_hcp_per_dir)


def run_tm_btwn_ben_versions(
    force_same_sequence: bool = False,
    force_same_lead: bool = False,
    force_same_card_play: bool = False,
    file: str = "./test_data/match_to_replay.pbn",
    specific_boards: None | List[int] = None,
    deal_random: bool = False,
    ditch_if_same_bidding: bool = False,
):
    with open(file) as f:
        text = f.read()
        boards = text.strip("\n").split("\n\n")
        deals: List[Deal] = [Deal.from_pbn(board) for board in boards]
        boards_number_seen = set()
        deals = [
            boards_number_seen.add(board.board_number) or board
            for board in deals
            if board.board_number not in boards_number_seen
        ]

        if specific_boards:
            deals = [deal for deal in deals if deal.board_number in specific_boards]

    for deal in deals:
        pbn = ""
        if deal_random:
            deal.diag = Diag.generate_random()
        if ditch_if_same_bidding:
            while ditch_if_same_bidding and not pbn and deal_random:
                deal.diag = Diag.generate_random()

                # while not deal.diag.hands[Direction.NORTH].hcp() + deal.diag.hands[Direction.SOUTH].hcp()>=26:
                #     deal.diag = Diag.generate_random()
                pbn = run_deal_on_both_rooms(
                    deal,
                    force_same_sequence,
                    force_same_lead,
                    force_same_card_play,
                    ditch_if_same_bidding,
                )
        else:
            pbn = run_deal_on_both_rooms(
                deal, force_same_sequence, force_same_lead, force_same_card_play
            )
        # print(
        #     "Ben times average : bidding : {},carding : {}".format(
        #         NEW_BIDDING_TIME[0] / NEW_BIDDING_TIME[1],
        #         NEW_CARD_TIME[0] / NEW_CARD_TIME[1],
        #     )
        # )
        # print("Lia times average : bidding : {},carding : {}".format(
        #     OLD_BIDDING_TIME[0]/OLD_BIDDING_TIME[1], OLD_CARD_TIME[0]/OLD_CARD_TIME[1]))
        print("Boards with differents leads : {}".format(boards_with_different_leads))
        name_of_the_match = "{} vs {}".format(RECEIVING_BOT_NAME, RECEIVED_BOT_NAME)
        with open(
            "./test_data/{} - {} - {}.pbn".format(name_of_the_match, DATE, TIME_STAMP),
            "a+",
        ) as f:
            f.write("\n{}".format(pbn))


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
    if board_1.deal_record.sequence.calculate_final_contract(
        board_1.deal.dealer
    ) != board_2.deal_record.sequence.calculate_final_contract(board_1.deal.dealer):
        return
    if (
        board_1.deal_record.play_record is None
        or board_2.deal_record.play_record is None
    ):
        return
    if board_1.deal_record.score == board_2.deal_record.score:
        return
    print(board_1.deal_record.play_record.as_unordered_one_dimension_list())
    print(board_2.deal_record.play_record.as_unordered_one_dimension_list())


def compare_two_tests(set_of_boards_1: List[Board], set_of_boards_2: List[Board]):
    [
        compare_two_boards(board_1, board_2)
        for board_1, board_2 in zip(set_of_boards_1, set_of_boards_2)
    ]


if __name__ == "__main__":
    run_tm_btwn_ben_versions(
        force_same_lead=True,
        # force_same_card_play=True,
        deal_random=True,
        force_same_sequence=True,
        # ditch_if_same_bidding=True,
    )
    # tests = run_tests()
    # compare_two_tests(load_test_pbn("avant.pbn"),
    #                   load_test_pbn("après.pbn"))
    # load_test_pbn("c4f380988fc67c0fe6e5f4bc5502d67a3b45d2c0.pbn")
    link = r"pn|Ben,Lia 2 over 1,Ben,Lia 2 over 1|qx|c19,BOARD 19|rh||ah|Board 19|md|1S7HKJT982DAK7CAJ6,SQ86H7DQ8654C8732,SA93HA653D3CQT954|sv|e|sa|0|mb|1H|an|11-23 hcp -- 5+!H|mb|p|mb|4D|an|ART3-6!S 4-7!H 3-6!C -- Game values -- Splinter - !D|mb|4S|mb|d|an|Penalty Double|mb|p|mb|p|an|4-6!H -- |mb|p|pg||pc|DA|pc|D4|pc|D3|pc|D2|pg||pc|HJ|pc|H7|pc|HA|pc|H4|pg||pc|C5|pc|CK|pc|CA|pc|C2|pg||pc|DK|pc|D5|pc|H5|pc|D9|pg||pc|S7|pc|S6|pc|SA|pc|S5|pg||pc|CT|pc|ST|mc|8|pg||"
    print(from_lin_to_request(link, Card_.from_str("D9")))
    # print(from_lin_to_request(link, bid_to_remove_after="X"))

    # print(from_lin_to_request(link, None))
    # count_average_hcp()
