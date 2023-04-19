from __future__ import annotations
from copy import deepcopy
import random
from typing import Dict, List
from tracing import tracer
import numpy as np
from datetime import datetime

from objects import Card
from utils import Direction, PlayerHand, VULNERABILITIES, Diag, Suit, Rank, Card_, TOTAL_DECK
from PlayRecord import PlayRecord, BiddingSuit

import bots
from bidding import bidding
import deck52
import sample

from game import AsyncCardPlayer
from claim_dds import check_claim_from_api

import os


def get_play_status(hand: PlayerHand, current_trick: List[Card_]):
    if current_trick == [] or len(current_trick) == 4:
        return "Lead"
    if len(hand.suits[current_trick[0].suit]) == 0:
        return "Discard"
    elif len(hand.suits[current_trick[0].suit]) == 1:
        return "Forced"
    else:
        return "Follow"


@tracer.start_as_current_span("get_ben_card_play_answer")
async def get_ben_card_play_answer(hand_str, dummy_hand_str, dealer_str, vuls, auction, contract, declarer_str, next_player_str, tricks_str, MODELS) -> Dict:
    n_samples = int(os.environ.get("LEADING_SAMPLES_COUNT", 100))
    claim_res = False

    padded_auction = ["PAD_START"] * \
        Direction.from_str(dealer_str).value + auction

    contract = bidding.get_contract(padded_auction)
    if contract is None:
        raise Exception("Contract is None !")

    level = int(contract[0])
    next_player = Direction.from_str(next_player_str)
    declarer = Direction.from_str(declarer_str)
    dummy = declarer.offset(2)
    strain_i = bidding.get_strain_i(contract)
    decl_i = bidding.get_decl_i(contract)
    is_decl_vuln = [vuls[0], vuls[1], vuls[0], vuls[1]][decl_i]
    play = [item for sublist in tricks_str for item in sublist]

    hands_for_diag = {dir: PlayerHand.from_pbn(
        hand_str if next_player == dir else "") for dir in Direction}
    if dummy == next_player:
        hands_for_diag[declarer] = PlayerHand.from_pbn(hand_str)

    hands_for_diag[dummy] = PlayerHand.from_pbn(dummy_hand_str)

    play_record = PlayRecord.from_tricks_as_list(
        declarer=declarer, list_of_tricks=tricks_str, trump=BiddingSuit.from_str(contract[1]))

    if play_record.record is None:
        raise Exception("Play record is None !")

    for trick in play_record.record:
        for dir, card in trick.cards.items():
            hands_for_diag[dir].append(card)
    random_diag = Diag(hands_for_diag)

    lefty_hand = random_diag.hands[declarer.offset(1)].to_pbn()
    dummy_hand = random_diag.hands[declarer.offset(2)].to_pbn()
    righty_hand = random_diag.hands[declarer.offset(3)].to_pbn()
    decl_hand = random_diag.hands[declarer].to_pbn()

    card_players = [
        bots.CardPlayer(MODELS.player_models, 0, lefty_hand,
                        dummy_hand, contract, is_decl_vuln, play_record, declarer=declarer, player_direction=next_player, player_hand=PlayerHand.from_pbn(hand_str),dummy_hand=PlayerHand.from_pbn(dummy_hand_str)),
        bots.CardPlayer(MODELS.player_models, 1, dummy_hand,
                        decl_hand, contract, is_decl_vuln, play_record, declarer=declarer, player_direction=next_player, player_hand=PlayerHand.from_pbn(hand_str),dummy_hand=PlayerHand.from_pbn(dummy_hand_str)),
        bots.CardPlayer(MODELS.player_models, 2, righty_hand,
                        dummy_hand, contract, is_decl_vuln, play_record, declarer=declarer, player_direction=next_player, player_hand=PlayerHand.from_pbn(hand_str),dummy_hand=PlayerHand.from_pbn(dummy_hand_str)),
        bots.CardPlayer(MODELS.player_models, 3, decl_hand,
                        dummy_hand, contract, is_decl_vuln, play_record, declarer=declarer, player_direction=next_player, player_hand=PlayerHand.from_pbn(hand_str),dummy_hand=PlayerHand.from_pbn(dummy_hand_str))
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
            card_players[player_i].tricks_left = 13-trick_i
            if trick_i == 0 and player_i == 0:
                for i, card_player in enumerate(card_players):
                    card_player.set_card_played(
                        trick_i=trick_i, leader_i=leader_i, i=0, card=opening_lead)
                continue

            card_i += 1
            if card_i >= len(play):
                play_status = get_play_status(hands_for_diag[next_player], [
                                              Card_.from_str(card) for card in tricks_str[-1]])
                if play_status == "Follow":
                    n_samples = 50
                if play_status == "Discard":
                    n_samples = 50
                rollout_states, probabilities_list = sample.init_rollout_states(trick_i, player_i, card_players, player_cards_played, shown_out_suits,
                                                                                current_trick, n_samples, padded_auction, card_players[player_i].hand_32.reshape((-1, 32)), vuls, MODELS)
                # card = card_players[player_i].debug=True
                card = card_players[player_i].play_card(
                    trick_i, leader_i, current_trick52, rollout_states, probabilities_list)
                if card_players[player_i].check_claim and next_player in [declarer, dummy]:
                    claim_res = await check_claim_from_api(hand_str, dummy_hand_str, declarer.abbreviation(), declarer_str, contract, tricks_str, 13-trick_i+card_players[player_i].n_tricks_taken)
                return {
                    "card": card,
                    # "card": play_real_card((PlayerHand.from_pbn(hand_str) if next_player != dummy else PlayerHand.from_pbn(dummy_hand_str)), resp.card.symbol(), trump=BiddingSuit.from_str(contract[1]), play_record=play_record, player_direction=next_player, declarer=declarer).__str__(),
                    "claim_the_rest": claim_res
                }

            card52 = Card.from_symbol(play[card_i]).code()
            card = deck52.card52to32(card52)
            current_trick.append(card)
            current_trick52.append(card52)

            for card_player in card_players:
                card_player.set_card_played(
                    trick_i=trick_i, leader_i=leader_i, i=player_i, card=card)

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
        for i, card_player in enumerate(card_players):
            assert np.min(card_player.x_play[:, trick_i + 1, 0:32]) == 0
            assert np.min(card_player.x_play[:, trick_i + 1, 32:64]) == 0
            assert np.sum(
                card_player.x_play[:, trick_i + 1, 0:32], axis=1) == 13 - trick_i - 1
            assert np.sum(
                card_player.x_play[:, trick_i + 1, 32:64], axis=1) == 13 - trick_i - 1

        trick_winner = (
            leader_i + deck52.get_trick_winner_i(current_trick52, (strain_i - 1) % 5)) % 4
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
    raise Exception(
        "The loop ended without returning a card, something weird is going on")
