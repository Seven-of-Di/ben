import time
from typing import List

import numpy as np

import binary

from bidding import bidding
from utils import convert_to_probability
from util import get_all_hidden_cards, view_samples
from tracing import tracer
from nn.bidder import Bidder


def distr_vec(x):
    xpos = np.maximum(x, 0) + 0.1
    pvals = xpos / np.sum(xpos, axis=1, keepdims=True)

    p_cumul = np.cumsum(pvals, axis=1)

    indexes = np.zeros(pvals.shape[0], dtype=np.int32)
    rnd = np.random.rand(pvals.shape[0])

    for k in range(p_cumul.shape[1]):
        indexes = indexes + (rnd > p_cumul[:, k])

    return indexes


def distr2_vec(x1, x2):
    x1pos = np.maximum(x1, 0) + 0.1
    x2pos = np.maximum(x2, 0) + 0.1

    pvals1 = x1pos / np.sum(x1pos, axis=1, keepdims=True)
    pvals2 = x2pos / np.sum(x2pos, axis=1, keepdims=True)

    pvals = pvals1 * pvals2
    pvals = pvals / np.sum(pvals, axis=1, keepdims=True)

    return distr_vec(pvals)


def get_small_out_i(small_out):
    x = small_out.copy()
    dec = np.minimum(1, x)

    result = []
    while np.max(x) > 0:
        result.extend(np.nonzero(x)[0])
        x = x - dec
        dec = np.minimum(1, x)

    return result


def sample_cards_vec(n_samples, p_hcp, p_shp, my_hand):
    deck = np.ones(32)
    deck[[7, 15, 23, 31]] = 6

    # unseen A K
    ak = np.zeros(32, dtype=int)
    ak[[0, 1, 8, 9, 16, 17, 24, 25]] = 1

    ak_out = ak - ak * my_hand
    ak_out_i_list = list(np.nonzero(ak_out)[0])
    ak_out_i = np.zeros((n_samples, len(ak_out_i_list)), dtype=int)
    ak_out_i[:, :] = np.array(ak_out_i_list)

    my_hand_small = my_hand * (1 - ak)

    small = deck * (1 - ak)

    small_out = small - my_hand_small
    small_out_i_list = get_small_out_i(small_out)
    small_out_i = np.zeros((n_samples, len(small_out_i_list)), dtype=int)
    small_out_i[:, :] = np.array(small_out_i_list)

    c_hcp = (lambda x: 4 * x + 10)(p_hcp.copy())
    c_shp = (lambda x: 1.75 * x + 3.25)(p_shp.copy()).reshape((3, 4))

    r_hcp = np.zeros((n_samples, 3)) + c_hcp
    r_shp = np.zeros((n_samples, 3, 4)) + c_shp

    lho_pard_rho = np.zeros((n_samples, 3, 32), dtype=int)
    cards_received = np.zeros((n_samples, 3), dtype=int)

    ak_out_i = np.vectorize(np.random.permutation,
                            signature='(n)->(n)')(ak_out_i)
    small_out_i = np.vectorize(
        np.random.permutation, signature='(n)->(n)')(small_out_i)

    s_all = np.arange(n_samples)

    # distribute A and K
    js = np.zeros(n_samples, dtype=int)
    while np.min(js) < ak_out_i.shape[1]:
        cards = ak_out_i[s_all, js]
        receivers = distr2_vec(r_shp[s_all, :, cards//8], r_hcp)

        can_receive_cards = cards_received[s_all, receivers] < 13

        cards_received[s_all[can_receive_cards],
                       receivers[can_receive_cards]] += 1
        lho_pard_rho[s_all[can_receive_cards],
                     receivers[can_receive_cards], cards[can_receive_cards]] += 1
        r_hcp[s_all[can_receive_cards], receivers[can_receive_cards]] -= 3
        r_shp[s_all[can_receive_cards], receivers[can_receive_cards],
              cards[can_receive_cards] // 8] -= 0.5
        js[can_receive_cards] += 1

    # distribute small cards
    js = np.zeros(n_samples, dtype=int)
    while True:
        s_all_r = s_all[js < small_out_i.shape[1]]
        if len(s_all_r) == 0:
            break

        js_r = js[s_all_r]

        cards = small_out_i[s_all_r, js_r]
        receivers = distr_vec(r_shp[s_all_r, :, cards//8])

        can_receive_cards = cards_received[s_all_r, receivers] < 13

        cards_received[s_all_r[can_receive_cards],
                       receivers[can_receive_cards]] += 1
        lho_pard_rho[s_all_r[can_receive_cards],
                     receivers[can_receive_cards], cards[can_receive_cards]] += 1
        r_shp[s_all_r[can_receive_cards], receivers[can_receive_cards],
              cards[can_receive_cards] // 8] -= 0.5
        js[s_all_r[can_receive_cards]] += 1

    # re-apply constraints
    accept_hcp = np.ones(n_samples).astype(bool)

    for i in range(3):
        if np.round(c_hcp[i]) >= 11:
            accept_hcp &= binary.get_hcp(
                lho_pard_rho[:, i, :]) >= np.round(c_hcp[i]) - 5

    accept_shp = np.ones(n_samples).astype(bool)

    for i in range(3):
        for j in range(4):
            if np.round(c_shp[i, j] >= 5):
                accept_shp &= np.sum(
                    lho_pard_rho[:, i, (j*8):((j+1)*8)], axis=1) >= np.round(c_shp[i, j]) - 1

    accept = accept_hcp & accept_shp

    if np.sum(accept) > 10:
        return lho_pard_rho[accept]
    else:
        return lho_pard_rho


def sample_cards_auction(n_samples, n_steps, auction, nesw_i, hand, vuln, bidder_model, binfo_model):
    n_steps = 1 + len(auction) // 4

    A = binary.get_auction_binary(n_steps, auction, nesw_i, hand, vuln)
    A_lho = binary.get_auction_binary(
        n_steps, auction, (nesw_i + 1) % 4, hand, vuln)
    A_pard = binary.get_auction_binary(
        n_steps, auction, (nesw_i + 2) % 4, hand, vuln)
    A_rho = binary.get_auction_binary(
        n_steps, auction, (nesw_i + 3) % 4, hand, vuln)

    p_hcp, p_shp = binfo_model.model(A)

    p_hcp = p_hcp.reshape((-1, n_steps, 3))[:, -1, :]
    p_shp = p_shp.reshape((-1, n_steps, 12))[:, -1, :]

    lho_pard_rho = sample_cards_vec(
        n_samples, p_hcp[0], p_shp[0], hand.reshape(32))

    n_samples = lho_pard_rho.shape[0]

    X_lho = np.zeros((n_samples, n_steps, A.shape[-1]))
    X_pard = np.zeros((n_samples, n_steps, A.shape[-1]))
    X_rho = np.zeros((n_samples, n_steps, A.shape[-1]))

    X_lho[:, :, :] = A_lho
    X_lho[:, :, 7:39] = lho_pard_rho[:, 0:1, :]
    X_lho[:, :, 2] = (binary.get_hcp(
        lho_pard_rho[:, 0, :]).reshape((-1, 1)) - 10) / 4
    X_lho[:, :, 3:7] = (binary.get_shape(
        lho_pard_rho[:, 0, :]).reshape((-1, 1, 4)) - 3.25) / 1.75
    lho_actual_bids = bidding.get_bid_ids(auction, (nesw_i + 1) % 4, n_steps)
    lho_sample_bids = bidder_model.model_seq(
        X_lho).reshape((n_samples, n_steps, -1))

    X_pard[:, :, :] = A_pard
    X_pard[:, :, 7:39] = lho_pard_rho[:, 1:2, :]
    X_pard[:, :, 2] = (binary.get_hcp(
        lho_pard_rho[:, 1, :]).reshape((-1, 1)) - 10) / 4
    X_pard[:, :, 3:7] = (binary.get_shape(
        lho_pard_rho[:, 1, :]).reshape((-1, 1, 4)) - 3.25) / 1.75
    pard_actual_bids = bidding.get_bid_ids(auction, (nesw_i + 2) % 4, n_steps)
    pard_sample_bids = bidder_model.model_seq(
        X_pard).reshape((n_samples, n_steps, -1))

    X_rho[:, :, :] = A_rho
    X_rho[:, :, 7:39] = lho_pard_rho[:, 2:, :]
    X_rho[:, :, 2] = (binary.get_hcp(
        lho_pard_rho[:, 2, :]).reshape((-1, 1)) - 10) / 4
    X_rho[:, :, 3:7] = (binary.get_shape(
        lho_pard_rho[:, 2, :]).reshape((-1, 1, 4)) - 3.25) / 1.75
    rho_actual_bids = bidding.get_bid_ids(auction, (nesw_i + 3) % 4, n_steps)
    rho_sample_bids = bidder_model.model_seq(
        X_rho).reshape((n_samples, n_steps, -1))

    min_scores = np.ones(n_samples)

    for i in range(n_steps):
        if lho_actual_bids[i] not in (bidding.BID2ID['PAD_START'], bidding.BID2ID['PAD_END']):
            min_scores = np.minimum(
                min_scores, lho_sample_bids[:, i, lho_actual_bids[i]])
        if pard_actual_bids[i] not in (bidding.BID2ID['PAD_START'], bidding.BID2ID['PAD_END']):
            min_scores = np.minimum(
                min_scores, pard_sample_bids[:, i, pard_actual_bids[i]])
        if rho_actual_bids[i] not in (bidding.BID2ID['PAD_START'], bidding.BID2ID['PAD_END']):
            min_scores = np.minimum(
                min_scores, rho_sample_bids[:, i, rho_actual_bids[i]])

    accept_threshold = 0.1

    accepted_samples = lho_pard_rho[min_scores > accept_threshold]

    while accepted_samples.shape[0] < 20:
        accept_threshold -= 0.01
        accepted_samples = lho_pard_rho[min_scores > accept_threshold]

    return accepted_samples


@tracer.start_as_current_span("shuffle_cards_bidding_info")
def shuffle_cards_bidding_info(n_samples, binfo, auction, hand, vuln, known_nesw, h_1_nesw, h_2_nesw, visible_cards, hidden_cards, cards_played, shown_out_suits):
    n_cards_to_receive = np.array(
        [len(hidden_cards) // 2, len(hidden_cards) - len(hidden_cards) // 2])

    n_steps = 1 + len(auction) // 4

    A = binary.get_auction_binary(n_steps, auction, known_nesw, hand, vuln)

    p_hcp, p_shp = binfo.model(A)

    p_hcp = p_hcp.reshape((-1, n_steps, 3))[:, -1, :]
    p_shp = p_shp.reshape((-1, n_steps, 12))[:, -1, :]

    def f_trans_hcp(x): return 4 * x + 10
    def f_trans_shp(x): return 1.75 * x + 3.25

    p_hcp = f_trans_hcp(
        p_hcp[0, [(h_1_nesw - known_nesw) % 4 - 1, (h_2_nesw - known_nesw) % 4 - 1]])
    p_shp = f_trans_shp(p_shp[0].reshape(
        (3, 4))[[(h_1_nesw - known_nesw) % 4 - 1, (h_2_nesw - known_nesw) % 4 - 1], :])

    # print(p_hcp)

    h1_h2 = np.zeros((n_samples, 2, 32), dtype=int)
    cards_received = np.zeros((n_samples, 2), dtype=int)

    card_hcp = [4, 3, 2, 1, 0, 0, 0, 0] * 4

    # acknowledge all played cards
    for i, cards in enumerate(cards_played):
        for c in cards:
            p_hcp[i] -= card_hcp[c] / 1.2
            suit = c // 8
            p_shp[i, suit] -= 0.5

    # distribute all cards of suits which are known to have shown out
    cards_shownout_suits = []
    for i, suits in enumerate(shown_out_suits):
        for suit in suits:
            for card in filter(lambda x: x // 8 == suit, hidden_cards):
                other_hand_i = (i + 1) % 2
                h1_h2[:, other_hand_i, card] += 1
                cards_received[:, other_hand_i] += 1
                p_hcp[other_hand_i] -= card_hcp[card] / 1.2
                p_shp[other_hand_i, suit] -= 0.5
                cards_shownout_suits.append(card)

    hidden_cards = [c for c in hidden_cards if c not in cards_shownout_suits]
    ak_cards = [c for c in hidden_cards if c in {0, 1, 8, 9, 16, 17, 24, 25}]
    small_cards = [c for c in hidden_cards if c not in {
        0, 1, 8, 9, 16, 17, 24, 25}]

    ak_out_i = np.array([np.random.permutation(ak_cards)
                        for _ in range(n_samples)], dtype=int)
    small_out_i = np.array([np.random.permutation(small_cards)
                           for _ in range(n_samples)], dtype=int)

    r_hcp = np.zeros((n_samples, 2)) + p_hcp
    r_shp = np.zeros((n_samples, 2, 4)) + p_shp

    s_all = np.arange(n_samples)

    n_max_cards = np.zeros((n_samples, 2), dtype=int) + n_cards_to_receive

    js = np.zeros(n_samples, dtype=int)
    while True:
        s_all_r = s_all[js < ak_out_i.shape[1]]
        if len(s_all_r) == 0:
            break

        js_r = js[s_all_r]
        cards = ak_out_i[s_all_r, js_r]
        receivers = distr2_vec(r_shp[s_all_r, :, cards//8], r_hcp[s_all_r])

        can_receive_cards = cards_received[s_all_r,
                                           receivers] < n_max_cards[s_all_r, receivers]

        cards_received[s_all_r[can_receive_cards],
                       receivers[can_receive_cards]] += 1
        h1_h2[s_all_r[can_receive_cards], receivers[can_receive_cards],
              cards[can_receive_cards]] += 1
        r_hcp[s_all_r[can_receive_cards], receivers[can_receive_cards]] -= 3
        r_shp[s_all_r[can_receive_cards], receivers[can_receive_cards],
              cards[can_receive_cards] // 8] -= 0.5
        js[s_all_r[can_receive_cards]] += 1

    js = np.zeros(n_samples, dtype=int)
    while True:
        s_all_r = s_all[js < small_out_i.shape[1]]
        if len(s_all_r) == 0:
            break

        js_r = js[s_all_r]
        cards = small_out_i[s_all_r, js_r]
        receivers = distr_vec(r_shp[s_all_r, :, cards//8])

        can_receive_cards = cards_received[s_all_r,
                                           receivers] < n_max_cards[s_all_r, receivers]

        cards_received[s_all_r[can_receive_cards],
                       receivers[can_receive_cards]] += 1
        h1_h2[s_all_r[can_receive_cards], receivers[can_receive_cards],
              cards[can_receive_cards]] += 1
        r_shp[s_all_r[can_receive_cards], receivers[can_receive_cards],
              cards[can_receive_cards] // 8] -= 0.5
        js[s_all_r[can_receive_cards]] += 1

    assert np.sum(h1_h2) == n_samples * np.sum(n_cards_to_receive)

    return h1_h2


@tracer.start_as_current_span("get_opening_lead_scores")
def get_opening_lead_scores(auction, vuln, binfo_model, lead_model, hand, opening_lead_card):
    contract = bidding.get_contract(auction)

    level = int(contract[0])
    strain = bidding.get_strain_i(contract)
    doubled = int('X' in contract)
    redbld = int('XX' in contract)

    x = np.zeros((hand.shape[0], 42))
    x[:, 0] = level
    x[:, 1 + strain] = 1
    x[:, 6] = doubled
    x[:, 7] = redbld

    decl_index = bidding.get_decl_i(contract)
    lead_index = (decl_index + 1) % 4

    vuln_us = vuln[lead_index % 2]
    vuln_them = vuln[decl_index % 2]

    x[:, 8] = vuln_us
    x[:, 9] = vuln_them
    x[:, 10:] = hand

    b = np.zeros((hand.shape[0], 15))

    n_steps = 1 + len(auction) // 4

    A = binary.get_auction_binary(n_steps, auction, lead_index, hand, vuln)

    p_hcp, p_shp = binfo_model.model(A)

    b[:, :3] = p_hcp.reshape((-1, n_steps, 3))[:, -1, :].reshape((-1, 3))
    b[:, 3:] = p_shp.reshape((-1, n_steps, 12))[:, -1, :].reshape((-1, 12))

    lead_softmax = lead_model.model(x, b)
    return convert_to_probability(lead_softmax[:, opening_lead_card])

@tracer.start_as_current_span("get_bid_scores")
def get_bid_scores(nesw_i, auction, vuln, hand, bidder_model: Bidder):
    n_steps = 1 + len(auction) // 4

    A = binary.get_auction_binary(n_steps, auction, nesw_i, hand, vuln)

    X = np.zeros((hand.shape[0], n_steps, A.shape[-1]))

    X[:, :, :2] = A[0, 0, :2]
    X[:, :, 7:39] = hand.reshape((-1, 1, 32))
    X[:, :, 39:] = A[0, :, 39:]
    X[:, :, 2] = (binary.get_hcp(hand).reshape((-1, 1)) - 10) / 4
    X[:, :, 3:7] = (binary.get_shape(hand).reshape((-1, 1, 4)) - 3.25) / 1.75
    actual_bids = bidding.get_bid_ids(auction, nesw_i, n_steps)
    sample_bids = bidder_model.model_seq(
        X).reshape((hand.shape[0], n_steps, -1))

    scores = np.ones(hand.shape[0])

    for i in range(n_steps):
        if actual_bids[i] not in (bidding.BID2ID['PAD_START'], bidding.BID2ID['PAD_END']):
            scores = np.multiply(scores, sample_bids[:, i, actual_bids[i]])

    return convert_to_probability(scores)


def player_to_nesw_i(player_i, contract):
    decl_i = bidding.get_decl_i(contract)
    return (decl_i + player_i + 1) % 4


def f_trans_hcp(x): return 4 * x + 10
def f_trans_shp(x): return 1.75 * x + 3.25

@tracer.start_as_current_span("init_rollout_states")
def init_rollout_states(trick_i, player_i, card_players, player_cards_played, shown_out_suits, current_trick, n_samples, auction, hand, vuln, models):
    leader_i = (player_i - len(current_trick)) % 4

    hidden_1_i, hidden_2_i = [(3, 2), (0, 2), (0, 3), (2, 0)][player_i]

    # sample the unknown cards
    public_hand_i = 3 if player_i == 1 else 1
    public_hand = card_players[public_hand_i].x_play[0, trick_i, :32]
    vis_cur_trick_nonpub = [c for i, c in enumerate(
        current_trick) if (leader_i + i) % 4 != public_hand_i]
    visible_cards = np.concatenate(
        [binary.get_cards_from_binary_hand(card_players[player_i].x_play[0, trick_i, :32]), binary.get_cards_from_binary_hand(public_hand)] +
        [np.array(vis_cur_trick_nonpub)] +
        [np.array(x, dtype=int) for x in player_cards_played]
    )
    hidden_cards = get_all_hidden_cards(visible_cards)

    contract = bidding.get_contract(auction)
    known_nesw = player_to_nesw_i(player_i, contract)
    h_1_nesw = player_to_nesw_i(hidden_1_i, contract)
    h_2_nesw = player_to_nesw_i(hidden_2_i, contract)

    h1_h2 = shuffle_cards_bidding_info(
        40*n_samples,
        models.binfo,
        auction,
        hand,
        vuln,
        known_nesw,
        h_1_nesw,
        h_2_nesw,
        visible_cards,
        hidden_cards,
        [player_cards_played[hidden_1_i], player_cards_played[hidden_2_i]],
        [shown_out_suits[hidden_1_i], shown_out_suits[hidden_2_i]]
    )

    h1_h2 = np.unique(h1_h2, axis=0)

    hidden_hand1, hidden_hand2 = h1_h2[:, 0], h1_h2[:, 1]

    samples_as_np_array = [np.zeros((hidden_hand1.shape[0], 13, 298)) for _ in range(4)]

    # we can reuse the x_play array from card_players except the player's hand
    for k in range(4):
        for i in range(trick_i + 1):
            samples_as_np_array[k][:, i, 32:] = card_players[k].x_play[0, i, 32:]

    # for player_i we can use the hand from card_players x_play (because the cards are known)
    for i in range(trick_i + 1):
        samples_as_np_array[player_i][:, i, :32] = card_players[player_i].x_play[0, i, :32]

    # all players know dummy's cards
    if player_i in (0, 2, 3):
        for i in range(trick_i + 1):
            samples_as_np_array[player_i][:, i, 32:64] = card_players[1].x_play[0, i, :32]
            samples_as_np_array[1][:, i, :32] = card_players[1].x_play[0, i, :32]

    # dummy knows declarer's cards
    if player_i == 1:
        for i in range(trick_i + 1):
            samples_as_np_array[player_i][:, i, 32:64] = card_players[3].x_play[0, i, :32]
            samples_as_np_array[3][:, i, :32] = card_players[3].x_play[0, i, :32]

    # add the current trick cards to the hidden hands
    if len(current_trick) > 0:
        for i, card in enumerate(current_trick):
            if (leader_i + i) % 4 == hidden_1_i:
                hidden_hand1[:, card] += 1
            if (leader_i + i) % 4 == hidden_2_i:
                hidden_hand2[:, card] += 1

    for k in range(trick_i + 1):
        samples_as_np_array[hidden_1_i][:, k, :32] = hidden_hand1
        samples_as_np_array[hidden_2_i][:, k, :32] = hidden_hand2
        for card in player_cards_played[hidden_1_i][k:]:
            samples_as_np_array[hidden_1_i][:, k, card] += 1
        for card in player_cards_played[hidden_2_i][k:]:
            samples_as_np_array[hidden_2_i][:, k, card] += 1

    # re-apply constraints
    n_steps = 1 + len(auction) // 4

    A = binary.get_auction_binary(n_steps, auction, known_nesw, hand, vuln)

    p_hcp, p_shp = models.binfo.model(A)

    p_hcp = p_hcp.reshape((-1, n_steps, 3))[:, -1, :]
    p_shp = p_shp.reshape((-1, n_steps, 12))[:, -1, :]

    p_hcp = f_trans_hcp(
        p_hcp[0, [(h_1_nesw - known_nesw) % 4 - 1, (h_2_nesw - known_nesw) % 4 - 1]])
    p_shp = f_trans_shp(p_shp[0].reshape(
        (3, 4))[[(h_1_nesw - known_nesw) % 4 - 1, (h_2_nesw - known_nesw) % 4 - 1], :])

    c_hcp = p_hcp.copy()
    c_shp = p_shp.copy()

    accept_hcp = np.ones(samples_as_np_array[0].shape[0]).astype(bool)

    for i in range(2):
        if np.round(c_hcp[i]) >= 11:
            accept_hcp &= binary.get_hcp(
                samples_as_np_array[[hidden_1_i, hidden_2_i][i]][:, 0, :32]) >= np.round(c_hcp[i]) - 5
    
    accept_shp = np.ones(samples_as_np_array[0].shape[0]).astype(bool)

    for i in range(2):
        for j in range(4):
            if np.round(c_shp[i, j] >= 5):
                accept_shp &= np.sum(
                    samples_as_np_array[[hidden_1_i, hidden_2_i][i]][:, 0, (j*8):((j+1)*8)], axis=1) >= np.round(c_shp[i, j]) - 1

    accept = accept_hcp & accept_shp

    if np.sum(accept) < n_samples:
        accept = np.ones_like(accept).astype(bool)
    # end of re-applyconstraints

    samples_as_np_array = [state[accept] for state in samples_as_np_array]
    probability_of_occurence = np.ones(len(samples_as_np_array[0]))

    # reject samples inconsistent with the opening lead
    lead_scores = np.ones(hidden_hand1.shape[0])
    if hidden_1_i == 0 or hidden_2_i == 0:
        opening_lead = current_trick[0] if trick_i == 0 else player_cards_played[0][0]
        lead_scores = get_opening_lead_scores(
            auction, vuln, models.binfo, models.lead, samples_as_np_array[0][:, 0, :32], opening_lead)

        probability_of_occurence = np.multiply(
            probability_of_occurence, lead_scores)

    # reject samples inconsistent with the bidding
    min_bid_scores = np.ones(samples_as_np_array[0].shape[0])

    for h_i in [hidden_1_i, hidden_2_i]:
        h_i_nesw = player_to_nesw_i(h_i, contract)
        if h_i_nesw >= samples_as_np_array[h_i].shape[0]:
            continue
        bid_scores = get_bid_scores(
            h_i_nesw, auction, vuln, samples_as_np_array[h_i][:, 0, :32], models.bidder_model)

        min_bid_scores = np.multiply(min_bid_scores, bid_scores)
    min_bid_scores = convert_to_probability(min_bid_scores)
    probability_of_occurence = np.multiply(
        probability_of_occurence, min_bid_scores)
    probability_of_occurence = convert_to_probability(probability_of_occurence)

    # reject samples inconsistent with the play
    min_scores = np.ones(samples_as_np_array[0].shape[0])

    for p_i in [hidden_1_i, hidden_2_i]:

        if trick_i == 0 and p_i == 0:
            continue

        card_played_current_trick = []
        for i, card in enumerate(current_trick):
            if (leader_i + i) % 4 == p_i:
                card_played_current_trick.append(card)

        cards_played_prev_tricks = player_cards_played[p_i][1:
                                                            trick_i] if p_i == 0 else player_cards_played[p_i][:trick_i]

        cards_played = cards_played_prev_tricks + card_played_current_trick

        if len(cards_played) == 0:
            continue

        n_tricks_pred = max(10, trick_i + len(card_played_current_trick))

        with tracer.start_as_current_span("card_play_coherence"):
            p_cards = models.player_models[p_i].model(
                samples_as_np_array[p_i][:, :n_tricks_pred, :])

        card_scores = p_cards[:, np.arange(
            len(cards_played)), cards_played]

        min_scores = np.multiply(min_scores, np.min(card_scores, axis=1))

    probability_of_occurence = np.multiply(
        probability_of_occurence, min_scores)

    probability_of_occurence = convert_to_probability(probability_of_occurence)

    n_diag_to_keep = min(n_samples,len(probability_of_occurence))

    # Get the indices of the n highest probabilities 
    highest_indices = np.argpartition(probability_of_occurence, -n_diag_to_keep)[-n_diag_to_keep:]

    # Get the indices that would sort the probabilities in descending order
    sorted_indices = highest_indices[np.argsort(probability_of_occurence[highest_indices])[::-1]]

    top_probs = probability_of_occurence[sorted_indices][:n_diag_to_keep]
    mask = top_probs >= 0.0001
    top_indices = sorted_indices[mask]

    # Get the n highest probabilities
    highest_probs = probability_of_occurence[top_indices]

    # Get the objects associated with the n highest probabilities
    highest_states = [obj[top_indices] for obj in samples_as_np_array]
    
    
    # print(time.time()-start)

    final_result = highest_states, highest_probs
    return final_result
