import sys
import re
import pprint
import asyncio
from typing import Dict
import numpy as np
from bidding import binary

import bots
import deck52
import sample

from nn.models import Models
from deck52 import decode_card
from bidding import bidding
from objects import Card
from utils import Direction, VULS_REVERSE, PlayerHand
from time import time
from Sequence import Sequence, SequenceAtom
from PlayRecord import PlayRecord, Trick, Card_
import requests

SEATS = ["North", "East", "South", "West"]


class TMClient:

    def __init__(self, name, seat):
        self.name = name
        self.seat = seat
        self.direction = Direction.from_str(seat)
        self.player_i = SEATS.index(self.seat)
        self.reader = None
        self.writer = None

    async def send_request_to_lia(self, type_of_action: str, data: Dict):
        # new_ben_called = (open_room and direction in [Direction.NORTH, Direction.SOUTH]) or (
        #     not open_room and direction in [Direction.EAST, Direction.WEST])
        port = "http://localhost:{}".format("5002")
        while True:
            try:
                res = requests.post("{}/{}".format(port, type_of_action), json=data)
                return res.json()
            except:
                await asyncio.sleep(1)

    async def send_request_to_ben(self, type_of_action: str, data: Dict):
        print(data)
        port = "http://localhost:{}".format("5001")
        while True:
            try:
                res = requests.post("{}/{}".format(port, type_of_action), json=data)
                return res.json()
            except:
                await asyncio.sleep(1)

    async def run(self):
        await asyncio.sleep(1)
        while True:
            try:
                self.dealer_i, self.vuln_ns, self.vuln_ew, self.hand_str = (
                    await self.receive_deal()
                )
                print(self.dealer_i, self.vuln_ns, self.vuln_ew, self.hand_str)
                break
            except:
                await asyncio.sleep(1)

        await asyncio.sleep(0.02)
        auction = await self.bidding()

        self.contract = self.sequence.get_current_contract(self.dealer)
        if self.contract is None or self.contract.bid is None:
            return
        self.declarer = self.contract.declarer
        if self.declarer is None:
            return
        print(auction)
        print(self.contract)

        opening_lead_card = await self.opening_lead()

        if self.direction != self.declarer.partner():
            self.dummy_hand_str = await self.receive_dummy()
        else:
            self.dummy_hand_str = self.hand_str

        await self.play(auction, opening_lead_card)

    async def connect(self, host, port):
        self.reader, self.writer = await asyncio.open_connection(host, port)

        print("connected")

        await self.send_message(
            f'Connecting "{self.name}" as {self.seat} using protocol version 18.\n'
        )

        print(await self.receive_line())

        await self.send_message(f"{self.seat} ready for teams.\n")

        print(await self.receive_line())

    async def bidding(self):
        vuln = [self.vuln_ns, self.vuln_ew]

        auction = Sequence([], None)

        current_player = self.dealer

        while auction.is_done() == False:
            await asyncio.sleep(0.01)
            if current_player == self.direction:
                # now it's this player's turn to bid
                bid_resp = await self.send_request_to_lia(
                    type_of_action="place_bid",
                    data={
                        "hand": self.hand_str,
                        "dealer": "NESW"[self.dealer_i],
                        "vuln": VULS_REVERSE[self.vuln_ns, self.vuln_ew],
                        "auction": auction.get_as_str_list(),
                        "conventions_ew": (
                            "DEFAULT" if self.seat in ["East","West"] else "SEF"
                        ),
                        "conventions_ns": (
                            "DEFAULT" if self.seat in ["North","South"] else "SEF"
                        ),
                    },
                )
                bid = bid_resp["bid"]
                await asyncio.sleep(0.01)
                auction.append_with_check(SequenceAtom.from_str(bid))
                await self.send_own_bid(bid)
            else:
                # just wait for the other player's bid
                bid = await self.receive_bid_for(current_player)
                auction.append_with_check(SequenceAtom.from_str(bid))

            current_player = current_player.next()

        print("Auction over")
        self.sequence = auction
        return auction.get_as_ben_request()

    async def opening_lead(self):
        if not self.declarer:
            raise Exception("No declarer")

        if self.direction == self.declarer.next():
            # this player is on lead
            print(await self.receive_line())
            data = {
                "hand": self.hand_str,
                "dealer": "NESW"[self.dealer_i],
                "vuln": VULS_REVERSE[self.vuln_ns, self.vuln_ew],
                "auction": [
                    a for a in self.sequence.get_as_ben_request() if a != "PAD_START"
                ],
                "conventions_ew": ("DEFAULT" if self.seat in ["East","West"] else "SEF"),
                "conventions_ns": (
                    "DEFAULT" if self.seat in ["North","South"] else "SEF"
                ),
            }
            lead = await self.send_request_to_lia(
                type_of_action="make_lead",
                data=data,
            )
            lead = lead["card"]
            # card_symbol = 'D5'
            print("Lead: ", lead)
            await asyncio.sleep(0.01)
            await self.send_card_played(lead)
            await asyncio.sleep(0.01)

            return lead
        else:
            # just send that we are ready for the opening lead
            return await self.receive_card_play_for(self.declarer.offset(1), 0)

    async def play(self, auction, lead):
        auction = Sequence.from_str_list(auction)
        contract = auction.get_current_contract(
            dealer=Direction.from_str("NESW"[self.dealer_i])
        )
        if contract is None:
            raise Exception("No contract")

        declarer = contract.declarer
        if declarer is None or contract.bid is None:
            raise Exception("No declarer")
        dummy = declarer.partner()
        leader = declarer.next()
        dummy_hand = PlayerHand.from_pbn(self.dummy_hand_str)
        my_hand = PlayerHand.from_pbn(self.hand_str)
        if self.direction == leader:
            my_hand.remove(Card_.from_str(lead))
        tricks = [[lead]]
        print(tricks)
        current_player = leader.offset(1)
        for _ in range(47):
            print(tricks)
            print("hand :", my_hand.to_pbn())
            print("dummy_hand :", dummy_hand.to_pbn())
            if (
                current_player == self.direction
                or (current_player == dummy and self.seat == declarer.to_str())
            ) and not self.direction == dummy:
                ranks_in_suit = (
                    my_hand.suits[Card_.from_str(tricks[-1][0]).suit]
                    if len(tricks[-1]) != 0 and current_player != dummy
                    else (
                        dummy_hand.suits[Card_.from_str(tricks[-1][0]).suit]
                        if len(tricks[-1]) != 0 and current_player == dummy
                        else []
                    )
                )
                if len(ranks_in_suit) == 1:  # Forced card
                    card = Card_(Card_.from_str(tricks[-1][0]).suit, ranks_in_suit[0])
                    card = card.suit_first_str()
                else:
                    data = {
                        "hand": (my_hand.to_pbn()),
                        "dummy_hand": dummy_hand.to_pbn(),
                        "dealer": "NESW"[self.dealer_i],
                        "vuln": VULS_REVERSE[self.vuln_ns, self.vuln_ew],
                        "auction": auction.get_as_ben_request(),
                        "contract": str(contract),
                        "contract_direction": declarer.abbreviation(),
                        "next_player": current_player.abbreviation(),
                        "tricks": tricks,
                        "playing_mode": "teams",
                    }
                    res = await self.send_request_to_ben(
                        type_of_action="play_card", data=data
                    )
                    print(res)
                    if "card" not in res :
                        print(data)
                        raise Exception("No card")
                    card = res["card"]
                await asyncio.sleep(0.1)
                await self.send_card_played(card)
                if current_player != dummy:
                    my_hand.remove(Card_.from_str(card))
            else:
                card = await self.receive_card_play_for(current_player, len(tricks))
            if current_player == dummy:
                dummy_hand.remove(Card_.from_str(card))
            current_player = current_player.offset(1)
            tricks[-1].append(card)
            if len(tricks[-1]) == 4:
                leader = Trick.from_list(
                    leader=leader, trick_as_list=[Card_.from_str(c) for c in tricks[-1]]
                ).winner(trump=contract.bid.suit)
                current_player = leader
                tricks.append([])
        for _ in range(4):
            if (
                current_player == self.direction
                or (current_player == dummy and self.seat == declarer.to_str())
            ) and not self.direction == dummy:
                card = (
                    my_hand.cards[0].suit_first_str()
                    if current_player != dummy
                    else dummy_hand.cards[0].suit_first_str()
                )
                await asyncio.sleep(0.5)
                await self.send_card_played(card)
            else:
                card = await self.receive_card_play_for(current_player, len(tricks))
            tricks[-1].append(card)
            current_player = current_player.offset(1)
            print(tricks)
        await asyncio.sleep(0.1)

    async def send_card_played(self, card_symbol):
        msg_card = f"{self.seat} plays {card_symbol[::-1]}\n"
        await self.send_message(msg_card)

    async def send_own_bid(self, bid):
        # bid = bid.replace("N", "NT")
        msg_bid = f"{SEATS[self.player_i]} bids {bid}\n"
        if bid in ["P", "PASS"]:
            msg_bid = f"{SEATS[self.player_i]} passes\n"
        elif bid == "X":
            msg_bid = f"{SEATS[self.player_i]} doubles\n"
        elif bid == "XX":
            msg_bid = f"{SEATS[self.player_i]} redoubles\n"

        await self.send_message(msg_bid)

    async def receive_card_play_for(self, current_player: Direction, trick_i: int):
        msg_ready = f"{self.seat} ready for {current_player.to_str()}'s card to trick {trick_i}.\n"
        await self.send_message(msg_ready)

        card_resp = await self.receive_line()
        card_resp_parts = card_resp.strip().split()

        try:
            assert card_resp_parts[0] == current_player.to_str()
            return card_resp_parts[-1][::-1].upper()
        except Exception as e:
            print(card_resp)
            print(card_resp_parts)
            print(e)
            return await self.receive_card_play_for(current_player, trick_i)

    async def receive_bid_for(self, player: Direction):
        msg_ready = f"{SEATS[self.player_i]} ready for {player.to_str()}'s bid.\n"
        await self.send_message(msg_ready)

        bid_resp = await self.receive_line()
        bid_resp_parts = bid_resp.strip().split()

        assert bid_resp_parts[0] == player.to_str()

        bid = bid_resp_parts[-1].rstrip(".").upper().replace("NT", "N")

        return {"PASSES": "PASS", "DOUBLES": "X", "REDOUBLES": "XX"}.get(bid, bid)

    async def receive_dummy(self):
        if not self.declarer:
            raise Exception("No declarer")
        if self.declarer.partner() == self.direction:
            return self.hand_str
        else:
            msg_ready = f"{self.seat} ready for dummy.\n"
            await self.send_message(msg_ready)
            line = await self.receive_line()
            # Dummy's cards : S A Q T 8 2. H K 7. D K 5 2. C A 7 6.
            return TMClient.parse_hand(line)

    async def send_ready(self):
        await self.send_message(f"{self.seat} ready to start.\n")

    async def receive_deal(self):
        print("Trying to receive deal")
        print(await self.receive_line())

        await self.send_message(f"{self.seat} ready for deal.\n")

        # 'Board number 1. Dealer North. Neither vulnerable. \r\n'
        deal_line_1 = await self.receive_line()
        # "South's cards : S K J 9 3. H K 7 6. D A J. C A Q 8 7. \r\n"
        # "North's cards : S 9 3. H -. D J 7 5. C A T 9 8 6 4 3 2."
        deal_line_2 = await self.receive_line()

        rx_dealer_vuln = r"(?P<dealer>[a-zA-z]+?)\.\s(?P<vuln>.+?)\svulnerable"
        match = re.search(rx_dealer_vuln, deal_line_1)
        if match is None:
            raise Exception(f"Could not parse deal line 1: {deal_line_1}")

        hand_str = TMClient.parse_hand(deal_line_2)

        dealer_i = "NESW".index(match.groupdict()["dealer"][0])
        vuln_str = match.groupdict()["vuln"]
        assert vuln_str in {"Neither", "N/S", "E/W", "Both"}
        vuln_ns = vuln_str == "N/S" or vuln_str == "Both"
        vuln_ew = vuln_str == "E/W" or vuln_str == "Both"
        self.dealer = Direction.from_str("NESW"[dealer_i])
        if self.dealer == self.direction:
            await asyncio.sleep(1)

        return dealer_i, vuln_ns, vuln_ew, hand_str

    @staticmethod
    def parse_hand(s):
        return (
            s[s.index(":") + 1 : s.rindex(".")]
            .replace(" ", "")
            .replace("-", "")
            .replace("S", "")
            .replace("H", "")
            .replace("D", "")
            .replace("C", "")
        )

    async def send_message(self, message: str):
        print(f"about to send: {message}")
        if self.writer is None:
            raise Exception("Writer is None")
        self.writer.write(message.encode())
        await self.writer.drain()
        print("sent successfully")

    async def receive_line(self) -> str:
        print("receiving message")
        if self.reader is None:
            raise Exception("Reader is None")
        message = await self.reader.readline()
        print(f"received: {message.decode()}")
        return message.decode()


async def main():
    host = sys.argv[1]
    port = int(sys.argv[2])
    name = sys.argv[3]
    seat = sys.argv[4]
    is_continue = len(sys.argv) > 5

    client = TMClient(
        name,
        seat,
    )
    await client.connect(host, port)

    if is_continue:
        print("Is continue")
        await client.receive_line()

    await client.send_ready()

    while True:
        print("Run client")
        await client.run()


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
