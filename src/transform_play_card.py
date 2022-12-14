from __future__ import annotations
from typing import List
import numpy as np

from objects import Card
from utils import Direction,PlayerHand,VULNERABILITIES,Diag,Suit
from PlayRecord import PlayRecord,BiddingSuit

import bots
from bidding import bidding
import deck52
import sample

from game import AsyncCardPlayer


async def get_ben_card_play_answer(hand_str, dummy_hand_str, dealer_str, vuln_str, auction, contract, declarer_str, next_player_str, tricks_str, MODELS):
    padded_auction = ["PAD_START"] * Direction.from_str(dealer_str).value + auction
    
    contract = bidding.get_contract(padded_auction)
        
    level = int(contract[0])
    next_player = Direction.from_str(next_player_str) 
    declarer = Direction.from_str(declarer_str)
    dummy = declarer.offset(2)
    strain_i = bidding.get_strain_i(contract)
    decl_i = bidding.get_decl_i(contract)
    vuls = VULNERABILITIES[vuln_str]
    is_decl_vuln = [vuls[0], vuls[1], vuls[0], vuls[1]][decl_i]
    play = [item for sublist in tricks_str for item in sublist]

    hands_for_diag = {d:PlayerHand.from_pbn(hand_str if next_player==d else "") for d in Direction}
    if dummy == next_player:
        hands_for_diag[declarer] = PlayerHand.from_pbn(hand_str)

    hands_for_diag[dummy]=PlayerHand.from_pbn(dummy_hand_str)

    play_record = PlayRecord.from_tricks_as_list(declarer=declarer,list_of_tricks = tricks_str, trump = BiddingSuit.from_str(contract[1]))

    for trick in play_record.record :
        for dir,card in trick.cards.items() :
            hands_for_diag[dir].append(card)
    random_diag = Diag(hands_for_diag)

    lefty_hand = random_diag.hands[declarer.offset(1)].to_pbn()
    dummy_hand = random_diag.hands[declarer.offset(2)].to_pbn()
    righty_hand = random_diag.hands[declarer.offset(3)].to_pbn()
    decl_hand = random_diag.hands[declarer].to_pbn()

    card_players = [
            AsyncCardPlayer(MODELS.player_models, 0, lefty_hand, dummy_hand, contract, is_decl_vuln),
            AsyncCardPlayer(MODELS.player_models, 1, dummy_hand, decl_hand, contract, is_decl_vuln),
            AsyncCardPlayer(MODELS.player_models, 2, righty_hand, dummy_hand, contract, is_decl_vuln),
            AsyncCardPlayer(MODELS.player_models, 3, decl_hand, dummy_hand, contract, is_decl_vuln)
        ]

    player_cards_played = [[] for _ in range(4)]
    shown_out_suits = [set() for _ in range(4)]

    leader_i = 0

    tricks = []
    tricks52 = []
    trick_won_by = []

    opening_lead52 = Card.from_symbol(play[0]).code()
    opening_lead = deck52.card52to32(opening_lead52)

    current_trick = [opening_lead]
    current_trick52 = [opening_lead52]

    card_players[0].hand52[opening_lead52] -= 1
    card_i = 0

    for trick_i in range(12):
            for player_i in map(lambda x: x % 4, range(leader_i, leader_i + 4)):
                if trick_i == 0 and player_i == 0:
                    for i, card_player in enumerate(card_players):
                        card_player.set_card_played(trick_i=trick_i, leader_i=leader_i, i=0, card=opening_lead)
                    continue
                

                card_i += 1
                if card_i >= len(play):
                    rollout_states = sample.init_rollout_states(trick_i, player_i, card_players, player_cards_played, shown_out_suits, current_trick, 200, padded_auction, card_players[player_i].hand.reshape((-1, 32)), vuls, MODELS)
                    resp = await card_players[player_i].async_play_card(trick_i, leader_i, current_trick52, rollout_states)

                    best_choice = list(resp.to_dict().values())[0]
                    if best_choice[1]=="x" :
                        return best_choice[0]+sorted(random_diag.hands[next_player].suits[Suit.from_str(best_choice[0])])[0].abbreviation()
                    return best_choice

                card52 = Card.from_symbol(play[card_i]).code() 
                card = deck52.card52to32(card52)
                current_trick.append(card)
                current_trick52.append(card52)

                for card_player in card_players:
                    card_player.set_card_played(trick_i=trick_i, leader_i=leader_i, i=player_i, card=card)


                card_players[player_i].set_own_card_played52(card52)
                if player_i == 1:
                    for i in [0, 2, 3]:
                        card_players[i].set_public_card_played52(card52)
                if player_i == 3:
                    card_players[1].set_public_card_played52(card52)

                # update shown out state
                if card // 8 != current_trick[0] // 8:  # card is different suit than lead card
                    shown_out_suits[player_i].add(current_trick[0] // 8)

            # sanity checks after trick completed
            assert len(current_trick) == 4

            for i, card_player in enumerate(card_players):
                assert np.min(card_player.hand52) == 0
                assert np.min(card_player.public52) == 0
                assert np.sum(card_player.hand52) == 13 - trick_i - 1
                assert np.sum(card_player.public52) == 13 - trick_i - 1

            tricks.append(current_trick)
            tricks52.append(current_trick52)

            # initializing for the next trick
            # initialize hands
            for i, card in enumerate(current_trick):
                card_players[(leader_i + i) % 4].x_play[:, trick_i + 1, 0:32] = card_players[(leader_i + i) % 4].x_play[:, trick_i, 0:32]
                card_players[(leader_i + i) % 4].x_play[:, trick_i + 1, 0 + card] -= 1

            # initialize public hands
            for i in (0, 2, 3):
                card_players[i].x_play[:, trick_i + 1, 32:64] = card_players[1].x_play[:, trick_i + 1, 0:32]
            card_players[1].x_play[:, trick_i + 1, 32:64] = card_players[3].x_play[:, trick_i + 1, 0:32]

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
            for i, card_player in enumerate(card_players):
                assert np.min(card_player.x_play[:, trick_i + 1, 0:32]) == 0
                assert np.min(card_player.x_play[:, trick_i + 1, 32:64]) == 0
                assert np.sum(card_player.x_play[:, trick_i + 1, 0:32], axis=1) == 13 - trick_i - 1
                assert np.sum(card_player.x_play[:, trick_i + 1, 32:64], axis=1) == 13 - trick_i - 1

            trick_winner = (leader_i + deck52.get_trick_winner_i(current_trick52, (strain_i - 1) % 5)) % 4
            trick_won_by.append(trick_winner)

            if trick_winner % 2 == 0:
                card_players[0].n_tricks_taken += 1
                card_players[2].n_tricks_taken += 1
            else:
                card_players[1].n_tricks_taken += 1
                card_players[3].n_tricks_taken += 1

            # update cards shown
            for i, card in enumerate(current_trick):
                player_cards_played[(leader_i + i) % 4].append(card)
            
            leader_i = trick_winner
            current_trick = []
            current_trick52 = []
