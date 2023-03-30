import sys
import re
import pprint
import asyncio
import numpy as np
from bidding import binary

import bots
import deck52
import sample

from nn.models import Models
from deck52 import decode_card
from bidding import bidding
from objects import Card

SEATS = ['North', 'East', 'South', 'West']


class TMClient:

    def __init__(self, name, seat, models):
        self.name = name
        self.seat = seat
        self.player_i = SEATS.index(self.seat)
        self.reader = None
        self.writer = None

        self.models = models

    async def run(self):
        self.dealer_i, self.vuln_ns, self.vuln_ew, self.hand_str = await self.receive_deal()

        auction = await self.bidding()

        self.contract = bidding.get_contract(auction)
        if self.contract is None:
            return

        level = int(self.contract[0])
        strain_i = bidding.get_strain_i(self.contract)
        self.decl_i = bidding.get_decl_i(self.contract)

        print(auction)
        print(self.contract)
        print(self.decl_i)

        opening_lead_card = await self.opening_lead(auction)
        opening_lead52 = Card.from_symbol(opening_lead_card).code()

        if self.player_i != (self.decl_i + 2) % 4:
            self.dummy_hand_str = await self.receive_dummy()

        await self.play(auction, opening_lead52)

    async def connect(self, host, port):
        self.reader, self.writer = await asyncio.open_connection(host, port)

        print('connected')

        await self.send_message(f'Connecting "{self.name}" as {self.seat} using protocol version 18.\n')

        print(await self.receive_line())

        await self.send_message(f'{self.seat} ready for teams.\n')

        print(await self.receive_line())

    async def bidding(self):
        vuln = [self.vuln_ns, self.vuln_ew]
        bot = bots.BotBid(vuln, self.hand_str, self.models)

        auction = ['PAD_START'] * self.dealer_i

        player_i = self.dealer_i

        while not bidding.auction_over(auction):
            if player_i == self.player_i:
                # now it's this player's turn to bid
                bid_resp = bot.bid(auction)
                auction.append(bid_resp.bid)
                await self.send_own_bid(bid_resp.bid)
            else:
                # just wait for the other player's bid
                bid = await self.receive_bid_for(player_i)
                auction.append(bid)

            player_i = (player_i + 1) % 4

        return auction

    async def opening_lead(self, auction):
        contract = bidding.get_contract(auction)
        decl_i = bidding.get_decl_i(contract)
        on_lead_i = (decl_i + 1) % 4

        if self.player_i == on_lead_i:
            # this player is on lead
            print(await self.receive_line())

            bot_lead = bots.BotLead(
                [self.vuln_ns, self.vuln_ew],
                self.hand_str,
                self.models
            )
            card_resp = bot_lead.lead(auction)
            card_symbol = card_resp.card.symbol()
            # card_symbol = 'D5'
            await self.send_card_played(card_symbol)
            return card_symbol
        else:
            # just send that we are ready for the opening lead
            return await self.receive_card_play_for(on_lead_i, 0)

    async def play(self, auction, opening_lead52):
        contract = bidding.get_contract(auction)

        level = int(contract[0])
        strain_i = bidding.get_strain_i(contract)
        decl_i = bidding.get_decl_i(contract)
        is_decl_vuln = [self.vuln_ns, self.vuln_ew,
                        self.vuln_ns, self.vuln_ew][decl_i]
        # lefty=0, dummy=1, righty=2, decl=3
        cardplayer_i = (self.player_i + 3 - decl_i) % 4
        print(
            f'play starts. decl_i={decl_i}, player_i={self.player_i}, cardplayer_i={cardplayer_i}')

        own_hand_str = self.hand_str
        dummy_hand_str = '...'

        if not cardplayer_i == 1:
            dummy_hand_str = self.dummy_hand_str

        lefty_hand_str = '...'
        if cardplayer_i == 0:
            lefty_hand_str = own_hand_str

        righty_hand_str = '...'
        if cardplayer_i == 2:
            righty_hand_str = own_hand_str

        decl_hand_str = '...'
        if cardplayer_i == 3:
            decl_hand_str = own_hand_str

        card_players = [
            bots.CardPlayer(self.models.player_models, 0, lefty_hand_str,
                            dummy_hand_str, contract, is_decl_vuln),
            bots.CardPlayer(self.models.player_models, 1,
                            dummy_hand_str, decl_hand_str, contract, is_decl_vuln),
            bots.CardPlayer(self.models.player_models, 2, righty_hand_str,
                            dummy_hand_str, contract, is_decl_vuln),
            bots.CardPlayer(self.models.player_models, 3,
                            decl_hand_str, dummy_hand_str, contract, is_decl_vuln)
        ]

        player_cards_played = [[] for _ in range(4)]
        shown_out_suits = [set() for _ in range(4)]

        leader_i = 0

        tricks = []
        tricks52 = []
        trick_won_by = []

        opening_lead = deck52.card52to32(opening_lead52)

        current_trick = [opening_lead]
        current_trick52 = [opening_lead52]

        card_players[0].hand52[opening_lead52] -= 1

        for trick_i in range(12):
            print("trick {}".format(trick_i))

            for player_i in map(lambda x: x % 4, range(leader_i, leader_i + 4)):
                print('player {}'.format(player_i))

                nesw_i = (decl_i + player_i + 1) % 4  # N=0, E=1, S=2, W=3

                if trick_i == 0 and player_i == 0:
                    print('skipping')
                    for i, card_player in enumerate(card_players):
                        card_player.set_card_played(
                            trick_i=trick_i, leader_i=leader_i, i=0, card=opening_lead)

                    continue

                card52 = None
                if player_i == 1 and cardplayer_i == 3:
                    # it's dummy's turn and this is the declarer
                    print('decls turn for dummy')

                    rollout_states = sample.init_rollout_states(trick_i, player_i, card_players, player_cards_played, shown_out_suits,
                                                                current_trick, 100, auction, card_players[player_i].hand_32.reshape((-1, 32)), [self.vuln_ns, self.vuln_ew], self.models)

                    card_resp = card_players[player_i].play_card(
                        trick_i, leader_i, current_trick52, rollout_states)

                    card52 = card_resp.card.code()

                    await self.send_card_played(card_resp.card.symbol())
                elif player_i == cardplayer_i and player_i != 1:
                    # we are on play
                    print(f'{player_i} turn')

                    rollout_states = sample.init_rollout_states(trick_i, player_i, card_players, player_cards_played, shown_out_suits,
                                                                current_trick, 100, auction, card_players[player_i].hand_32.reshape((-1, 32)), [self.vuln_ns, self.vuln_ew], self.models)

                    card_resp = card_players[player_i].play_card(
                        trick_i, leader_i, current_trick52, rollout_states)

                    card52 = card_resp.card.code()

                    await self.send_card_played(card_resp.card.symbol())
                else:
                    # another player is on play, we just have to wait for their card
                    card52_symbol = await self.receive_card_play_for(nesw_i, trick_i)
                    card52 = Card.from_symbol(card52_symbol).code()

                card = deck52.card52to32(card52)

                for card_player in card_players:
                    card_player.set_card_played(
                        trick_i=trick_i, leader_i=leader_i, i=player_i, card=card)

                current_trick.append(card)

                current_trick52.append(card52)

                card_players[player_i].set_own_card_played52(card52)
                if player_i == 1:
                    for i in [0, 2, 3]:
                        card_players[i].set_public_card_played52(card52)
                if player_i == 3:
                    card_players[1].set_public_card_played52(card52)

                # update shown out state
                # card is different suit than lead card
                if card // 8 != current_trick[0] // 8:
                    shown_out_suits[player_i].add(current_trick[0] // 8)

            # sanity checks after trick completed
            assert len(current_trick) == 4

            for i in [cardplayer_i] + ([1] if cardplayer_i == 3 else []):
                if cardplayer_i == 1:
                    break
                assert np.min(card_players[i].hand52) == 0
                assert np.min(card_players[i].public52) == 0
                assert np.sum(card_players[i].hand52) == 13 - trick_i - 1
                assert np.sum(card_players[i].public52) == 13 - trick_i - 1

            tricks.append(current_trick)
            tricks52.append(current_trick52)

            # initializing for the next trick
            # initialize hands
            for i, card in enumerate(current_trick):
                card_players[(leader_i + i) % 4].x_play[:, trick_i + 1,
                                                        0:32] = card_players[(leader_i + i) % 4].x_play[:, trick_i, 0:32]
                card_players[(leader_i + i) % 4].x_play[:,
                                                        trick_i + 1, 0 + card] -= 1

            # initialize public hands
            for i in (0, 2, 3):
                card_players[i].x_play[:, trick_i + 1,
                                       32:64] = card_players[1].x_play[:, trick_i + 1, 0:32]
            card_players[1].x_play[:, trick_i + 1,
                                   32:64] = card_players[3].x_play[:, trick_i + 1, 0:32]

            for card_player in card_players:
                # initialize last trick
                for i, card in enumerate(current_trick):
                    card_player.x_play[:, trick_i + 1, 64 + i * 32 + card] = 1

                # initialize last trick leader
                card_player.x_play[:, trick_i + 1, 288 + leader_i] = 1

                # initialize level
                card_player.x_play[:, trick_i + 1, 292] = level

                # initialize strain
                card_player.x_play[:, trick_i + 1, 293 + strain_i] = 1

            # sanity checks for next trick
            for i in [cardplayer_i] + ([1] if cardplayer_i == 3 else []):
                if cardplayer_i == 1:
                    break
                assert np.min(
                    card_players[i].x_play[:, trick_i + 1, 0:32]) == 0
                assert np.min(
                    card_players[i].x_play[:, trick_i + 1, 32:64]) == 0
                assert np.sum(
                    card_players[i].x_play[:, trick_i + 1, 0:32], axis=1) == 13 - trick_i - 1
                assert np.sum(
                    card_players[i].x_play[:, trick_i + 1, 32:64], axis=1) == 13 - trick_i - 1

            trick_winner = (
                leader_i + deck52.get_trick_winner_i(current_trick52, (strain_i - 1) % 5)) % 4
            trick_won_by.append(trick_winner)

            if trick_winner % 2 == 0:
                card_players[0].n_tricks_taken += 1
                card_players[2].n_tricks_taken += 1
            else:
                card_players[1].n_tricks_taken += 1
                card_players[3].n_tricks_taken += 1

            print('trick52 {} cards={}. won by {}'.format(
                trick_i, list(map(decode_card, current_trick52)), trick_winner))

            print('trick52 {} cards={}. won by {}'.format(
                trick_i, list(map(decode_card, current_trick52)), trick_winner))

            # update cards shown
            for i, card in enumerate(current_trick):
                player_cards_played[(leader_i + i) % 4].append(card)

            leader_i = trick_winner
            current_trick = []
            current_trick52 = []

            # player on lead will receive message (or decl if dummy on lead)
            if leader_i == 1:
                if cardplayer_i == 3:
                    await self.receive_line()
            elif leader_i == cardplayer_i:
                await self.receive_line()

        # play last trick
        for player_i in map(lambda x: x % 4, range(leader_i, leader_i + 4)):
            nesw_i = (decl_i + player_i + 1) % 4  # N=0, E=1, S=2, W=3
            card52 = None
            if player_i == 1 and cardplayer_i == 3 or player_i == cardplayer_i and player_i != 1:
                # we are on play
                card52 = np.nonzero(card_players[player_i].hand52)[0][0]
                card52_symbol = Card.from_code(card52).symbol()
                await self.send_card_played(card52_symbol)
            else:
                # someone else is on play. we just have to wait for their card
                card52_symbol = await self.receive_card_play_for(nesw_i, trick_i)
                card52 = Card.from_symbol(card52_symbol).code()

            card = deck52.card52to32(card52)

            current_trick.append(card)
            current_trick52.append(card52)

        tricks.append(current_trick)
        tricks52.append(current_trick52)

        trick_winner = (
            leader_i + deck52.get_trick_winner_i(current_trick52, (strain_i - 1) % 5)) % 4
        trick_won_by.append(trick_winner)

        print('last trick')
        print(current_trick)
        print(current_trick52)
        print(trick_won_by)

        pprint.pprint(list(zip(tricks, trick_won_by)))

        self.trick_winners = trick_won_by

    async def send_card_played(self, card_symbol):
        msg_card = f'{self.seat} plays {card_symbol[::-1]}\n'
        await self.send_message(msg_card)

    async def send_own_bid(self, bid):
        bid = bid.replace('N', 'NT')
        msg_bid = f'{SEATS[self.player_i]} bids {bid}.\n'
        if bid == 'PASS':
            msg_bid = f'{SEATS[self.player_i]} passes.\n'
        elif bid == 'X':
            msg_bid = f'{SEATS[self.player_i]} doubles.\n'
        elif bid == 'XX':
            msg_bid = f'{SEATS[self.player_i]} redoubles.\n'

        await self.send_message(msg_bid)

    async def receive_card_play_for(self, player_i, trick_i):
        msg_ready = f"{self.seat} ready for {SEATS[player_i]}'s card to trick {trick_i + 1}.\n"
        await self.send_message(msg_ready)

        card_resp = await self.receive_line()
        card_resp_parts = card_resp.strip().split()

        assert card_resp_parts[0] == SEATS[player_i]

        return card_resp_parts[-1][::-1].upper()

    async def receive_bid_for(self, player_i):
        msg_ready = f"{SEATS[self.player_i]} ready for {SEATS[player_i]}'s bid.\n"
        await self.send_message(msg_ready)

        bid_resp = await self.receive_line()
        bid_resp_parts = bid_resp.strip().split()

        assert bid_resp_parts[0] == SEATS[player_i]

        bid = bid_resp_parts[-1].rstrip('.').upper().replace('NT', 'N')

        return {
            'PASSES': 'PASS',
            'DOUBLES': 'X',
            'REDOUBLES': 'XX'
        }.get(bid, bid)

    async def receive_dummy(self):
        dummy_i = (self.decl_i + 2) % 4

        if self.player_i == dummy_i:
            return self.hand_str
        else:
            msg_ready = f'{self.seat} ready for dummy.\n'
            await self.send_message(msg_ready)
            line = await self.receive_line()
            # Dummy's cards : S A Q T 8 2. H K 7. D K 5 2. C A 7 6.
            return TMClient.parse_hand(line)

    async def send_ready(self):
        await self.send_message(f'{self.seat} ready to start.\n')

    async def receive_deal(self):
        print(await self.receive_line())

        await self.send_message(f'{self.seat} ready for deal.\n')

        # 'Board number 1. Dealer North. Neither vulnerable. \r\n'
        deal_line_1 = await self.receive_line()
        # "South's cards : S K J 9 3. H K 7 6. D A J. C A Q 8 7. \r\n"
        # "North's cards : S 9 3. H -. D J 7 5. C A T 9 8 6 4 3 2."
        deal_line_2 = await self.receive_line()

        rx_dealer_vuln = r'(?P<dealer>[a-zA-z]+?)\.\s(?P<vuln>.+?)\svulnerable'
        match = re.search(rx_dealer_vuln, deal_line_1)

        hand_str = TMClient.parse_hand(deal_line_2)

        dealer_i = 'NESW'.index(match.groupdict()['dealer'][0])
        vuln_str = match.groupdict()['vuln']
        assert vuln_str in {'Neither', 'N/S', 'E/W', 'Both'}
        vuln_ns = vuln_str == 'N/S' or vuln_str == 'Both'
        vuln_ew = vuln_str == 'E/W' or vuln_str == 'Both'

        return dealer_i, vuln_ns, vuln_ew, hand_str

    @staticmethod
    def parse_hand(s):
        return s[s.index(':') + 1: s.rindex('.')] \
            .replace(' ', '').replace('-', '').replace('S', '').replace('H', '').replace('D', '').replace('C', '')

    async def send_message(self, message: str):
        print(f'about to send: {message}')
        self.writer.write(message.encode())
        await self.writer.drain()
        print('sent successfully')

    async def receive_line(self) -> str:
        print('receiving message')
        message = await self.reader.readline()
        print(f'received: {message.decode()}')
        return message.decode()


async def main():
    host = sys.argv[1]
    port = int(sys.argv[2])
    name = sys.argv[3]
    seat = sys.argv[4]
    is_continue = len(sys.argv) > 5

    client = TMClient(name, seat, Models.load('../models'))
    await client.connect(host, port)

    if is_continue:
        await client.receive_line()

    await client.send_ready()

    while True:
        await client.run()

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
