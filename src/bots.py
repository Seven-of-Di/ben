from copy import deepcopy
from math import ceil
import time
import random
import pprint
from typing import Dict, List, Optional

import numpy as np

from tracing import tracer
from ddsolver import ddsolver
import binary
import nn.player as player
import deck52
import sample
import scoring
import nn.models

from objects import BidResp, CandidateBid, Card, CardResp, CandidateCard
from bidding import bidding
from bidding.binary import parse_hand_f

from util import hand_to_str, expected_tricks, p_make_contract
from utils import (
    Card_,
    multiple_list_comparaison,
    Direction,
    PlayerHand,
    BiddingSuit,
    Rank,
    Suit,
    TOTAL_DECK,
    Diag,
    convert_to_probability,
    PlayingMode,
)
from human_carding import play_real_card
from PlayRecord import PlayRecord
from Sequence import Sequence

DDS = ddsolver.DDSolver()


class BotBid:
    def __init__(
        self, vuln, hand_str, models: nn.models.Models, human_model: bool = False
    ):
        self.vuln = vuln
        self.hand_str = hand_str
        self.hand = binary.parse_hand_f(32)(hand_str)
        self.min_candidate_score = 0.15
        self.getting_doubled = False

        self.model = (
            models.bidder_model if not human_model else models.wide_bidder_model
        )
        self.state = (
            models.bidder_model.zero_state
            if not human_model
            else models.wide_bidder_model.zero_state
        )
        self.lead_model = models.lead
        self.sd_model = models.sd_model

        self.binfo_model = models.binfo

    @staticmethod
    def get_n_steps_auction(auction):
        hand_i = len(auction) % 4
        i = hand_i
        while i < len(auction) and auction[i] == "PAD_START":
            i += 4
        return 1 + (len(auction) - i) // 4

    def get_binary(self, auction):
        n_steps = BotBid.get_n_steps_auction(auction)
        hand_ix = len(auction) % 4

        X = binary.get_auction_binary(n_steps, auction, hand_ix, self.hand, self.vuln)
        return X[:, -1, :]

    def restful_bid(self, auction) -> BidResp:
        auction = [element for element in auction if element != "PAD_START"]
        self.getting_doubled = len(auction) >= 3 and (
            (auction[-3:] == ["X", "PASS", "PASS"]) or auction[-2:] == ["XX", "PASS"]
        )
        self.min_candidate_score = (
            0.01 if self.getting_doubled else self.min_candidate_score
        )

        position_minus_1 = len(auction) % 4

        for i in range(len(auction) // 4):
            self.get_bid_candidates(auction[: i * 4 + position_minus_1])

        bid = self.bid(auction)

        return bid

    def get_samples_from_auction(self, auction) -> List[PlayerHand]:
        auction = [element for element in auction if element != "PAD_START"]
        # print(auction)

        position_minus_1 = len(auction) % 4
        for i in range(len(auction) // 4):
            self.get_bid_candidates(auction[: i * 4 + position_minus_1])

        hands_np = self.sample_hands(auction)

        samples = [
            PlayerHand.from_pbn(hand_to_str(hands_np[i, (len(auction) - 1) % 4, :]))
            for i in range(hands_np.shape[0])
        ]

        # for dir, sample in samples.items() :
        #     print(dir,":")
        #     print(SampleAnalyzer(sample))

        samples_str = []
        for i in range(hands_np.shape[0]):
            samples_str.append(
                "%s %s %s %s"
                % (
                    hand_to_str(hands_np[i, 0, :]),
                    hand_to_str(hands_np[i, 1, :]),
                    hand_to_str(hands_np[i, 2, :]),
                    hand_to_str(hands_np[i, 3, :]),
                )
            )

        # print(samples_str[:5])

        return samples

    def bid(self, auction):
        candidates = self.get_bid_candidates(auction)
        hands_np = self.sample_hands(auction)

        samples = []
        for i in range(min(5, hands_np.shape[0])):
            samples.append(
                "%s %s %s %s"
                % (
                    hand_to_str(hands_np[i, 0, :]),
                    hand_to_str(hands_np[i, 1, :]),
                    hand_to_str(hands_np[i, 2, :]),
                    hand_to_str(hands_np[i, 3, :]),
                )
            )

        # print(samples)

        if BotBid.do_rollout(auction, candidates):
            ev_candidates = []
            for candidate in candidates:
                auctions_np = self.bidding_rollout(auction, candidate.bid, hands_np)
                contracts, decl_tricks_softmax = self.expected_tricks(
                    hands_np, auctions_np
                )
                ev = self.expected_score(
                    len(auction) % 4, contracts, decl_tricks_softmax
                )
                if candidate.bid == "XX":
                    # Please stop redoubling if you are not 100% sure
                    ev -= 300
                ev_c = candidate.with_expected_score(np.mean(ev))
                ev_candidates.append(ev_c)
            candidates = sorted(
                ev_candidates, key=lambda c: c.expected_score, reverse=True
            )

            return BidResp(
                bid=candidates[0].bid, candidates=candidates, samples=samples
            )

        return BidResp(bid=candidates[0].bid, candidates=candidates, samples=samples)

    @staticmethod
    def do_rollout(auction, candidates: List[CandidateBid]):
        if len(candidates) == 1:
            return False

        if BotBid.get_n_steps_auction(auction) > 1:
            return True

        if any(bid not in ("PASS", "PAD_START") for bid in auction):
            return True

        if all(candidate.bid != "PASS" for candidate in candidates):
            return True

        return False

    def get_bid_candidates(self, auction) -> List[CandidateBid]:
        bid_softmax = self.next_bid_np(auction)[0]

        candidates = []
        while True:
            bid_i = np.argmax(bid_softmax)
            if bid_softmax[bid_i] < self.min_candidate_score and len(candidates) > 0:
                break
            if bidding.can_bid(bidding.ID2BID[bid_i], auction):
                candidates.append(
                    CandidateBid(
                        bid=bidding.ID2BID[bid_i], insta_score=bid_softmax[bid_i]
                    )
                )
            bid_softmax[bid_i] = 0

        return candidates

    def next_bid_np(self, auction):
        x = self.get_binary(auction)
        bid_np, next_state = self.model.model(x, self.state)
        self.state = next_state

        return bid_np

    def sample_hands(self, auction_so_far):
        turn_to_bid = len(auction_so_far) % 4
        n_steps = BotBid.get_n_steps_auction(auction_so_far)
        lho_pard_rho = sample.sample_cards_auction(
            2048,
            n_steps,
            auction_so_far,
            turn_to_bid,
            self.hand,
            self.vuln,
            self.model,
            self.binfo_model,
        )[:64]
        n_samples = lho_pard_rho.shape[0]

        hands_np = np.zeros((n_samples, 4, 32), dtype=np.int32)
        hands_np[:, turn_to_bid, :] = self.hand
        for i in range(1, 4):
            hands_np[:, (turn_to_bid + i) % 4, :] = lho_pard_rho[:, i - 1, :]

        return hands_np

    def bidding_rollout(self, auction_so_far, candidate_bid, hands_np):
        auction = [*auction_so_far, candidate_bid]

        n_samples = hands_np.shape[0]

        n_steps_vals = [0, 0, 0, 0]
        for i in range(1, 5):
            n_steps_vals[
                (len(auction_so_far) % 4 + i) % 4
            ] = BotBid.get_n_steps_auction(auction_so_far + ["?"] * i)

        # initialize auction vector
        auction_np = (
            np.ones((n_samples, 64), dtype=np.int32) * bidding.BID2ID["PAD_END"]
        )
        for i, bid in enumerate(auction):
            auction_np[:, i] = bidding.BID2ID[bid]

        bid_i = len(auction) - 1
        turn_i = len(auction) % 4
        while not np.all(auction_np[:, bid_i] == bidding.BID2ID["PAD_END"]):
            X = binary.get_auction_binary(
                n_steps_vals[turn_i],
                auction_np,
                turn_i,
                hands_np[:, turn_i, :],
                self.vuln,
            )
            bid_np = self.model.model_seq(X).reshape(
                (n_samples, n_steps_vals[turn_i], -1)
            )[:, -1, :]

            bid_i += 1
            auction_np[:, bid_i] = np.argmax(bid_np, axis=1)

            n_steps_vals[turn_i] += 1
            turn_i = (turn_i + 1) % 4

        return auction_np

    def expected_tricks(self, hands_np, auctions_np):
        n_samples = hands_np.shape[0]
        s_all = np.arange(n_samples, dtype=np.int32)
        auctions, contracts = [], []
        declarers = np.zeros(n_samples, dtype=np.int32)
        strains = np.zeros(n_samples, dtype=np.int32)
        X_ftrs = np.zeros((n_samples, 42))
        B_ftrs = np.zeros((n_samples, 15))

        for i in range(n_samples):
            sample_auction = [
                bidding.ID2BID[bid_i] for bid_i in list(auctions_np[i, :]) if bid_i != 1
            ]
            auctions.append(sample_auction)
            contract = bidding.get_contract(sample_auction)
            contracts.append(contract)
            strains[i] = "NSHDC".index(contract[1])
            declarers[i] = "NESW".index(contract[-1])

            hand_on_lead = hands_np[i : i + 1, (declarers[i] + 1) % 4, :]

            X_ftrs[i, :], B_ftrs[i, :] = binary.get_lead_binary(
                sample_auction, hand_on_lead, self.binfo_model, self.vuln
            )

        lead_softmax = self.lead_model.model(X_ftrs, B_ftrs)
        lead_cards = np.argmax(lead_softmax, axis=1)

        X_sd = np.zeros((n_samples, 32 + 5 + 4 * 32))

        X_sd[s_all, 32 + strains] = 1
        # lefty
        X_sd[:, (32 + 5 + 0 * 32) : (32 + 5 + 1 * 32)] = hands_np[
            s_all, (declarers + 1) % 4
        ]
        # dummy
        X_sd[:, (32 + 5 + 1 * 32) : (32 + 5 + 2 * 32)] = hands_np[
            s_all, (declarers + 2) % 4
        ]
        # righty
        X_sd[:, (32 + 5 + 2 * 32) : (32 + 5 + 3 * 32)] = hands_np[
            s_all, (declarers + 3) % 4
        ]
        # declarer
        X_sd[:, (32 + 5 + 3 * 32) :] = hands_np[s_all, declarers]

        X_sd[s_all, lead_cards] = 1

        decl_tricks_softmax = self.sd_model.model(X_sd)

        return contracts, decl_tricks_softmax

    def expected_score(self, turn_to_bid, contracts, decl_tricks_softmax):
        n_samples = len(contracts)
        scores_by_trick = np.zeros((n_samples, 14))
        for i, contract in enumerate(contracts):
            scores_by_trick[i] = scoring.contract_scores_by_trick(
                contract, tuple(self.vuln)
            )
            decl_i = "NESW".index(contract[-1])
            if (turn_to_bid + decl_i) % 2 == 1:
                # the other side is playing the contract
                scores_by_trick[i, :] *= -1

        res = np.sum(decl_tricks_softmax * scores_by_trick, axis=1)
        average = sum(res) / len(res)
        return res


class BotLead:
    def __init__(self, vuln, hand_str, models):
        self.vuln = vuln
        self.hand_str = hand_str
        self.hand = binary.parse_hand_f(32)(hand_str)
        self.hand52 = binary.parse_hand_f(52)(hand_str)

        self.lead_model = models.lead
        self.bidder_model = models.bidder_model
        self.binfo_model = models.binfo
        self.sd_model = models.sd_model

    def lead(self, auction):
        contract = bidding.get_contract(auction)
        if contract is None:
            raise Exception("Contract should not be None if asking for a lead")
        if len(self.hand_str)!=16 :
            raise Exception("Not 13 cards in hand")
        level = int(contract[0])
        tricks_to_defeat_contract = 13 - (6 + level) + 1
        strain = bidding.get_strain_i(contract)

        lead_card_indexes, lead_softmax = self.get_lead_candidates(auction, level)
        if len(lead_card_indexes) == 1:
            return CardResp(
                card=Card.from_code(lead_card_indexes[0], xcards=True),
                candidates=[
                    CandidateCard(
                        card=Card.from_code(lead_card_indexes[0], xcards=True),
                        insta_score=lead_softmax[0, lead_card_indexes[0]],
                        p_make_contract=None,
                        expected_tricks=None,
                    )
                ],
                samples=[],
            )
        accepted_samples = self.get_accepted_samples(4096, auction)

        samples = []

        base_diag = Diag({d: PlayerHand({s: [] for s in Suit}) for d in Direction})
        base_diag.hands[Direction.WEST] = PlayerHand.from_pbn(self.hand_str)
        samples = [
            deepcopy(base_diag) for i in range(min(100, accepted_samples.shape[0]))
        ]
        pips = {s: [] for s in Suit}
        for card in TOTAL_DECK:
            if (
                card not in base_diag.hands[Direction.WEST].cards
                and card.rank <= Rank.SEVEN
            ):
                pips[card.suit].append(card.rank)
        for i in range(min(100, accepted_samples.shape[0])):
            temp_pips = deepcopy(pips)
            samples[i].hands[Direction.NORTH] = PlayerHand.from_pbn(
                hand_to_str(accepted_samples[i, 0, :]), temp_pips
            )
            samples[i].hands[Direction.EAST] = PlayerHand.from_pbn(
                hand_to_str(accepted_samples[i, 1, :]), temp_pips
            )
            samples[i].hands[Direction.SOUTH] = PlayerHand.from_pbn(
                hand_to_str(accepted_samples[i, 2, :]), temp_pips
            )

        dd_solved = DDS.solve(
            strain,
            0,
            [],
            [diag.print_as_pbn(first_direction=Direction.WEST) for diag in samples],
        )
        dd_solved = {Card_.get_from_52(k): v for k, v in dd_solved.items()}
        # print(dd_solved)

        candidate_cards: List[CandidateCard] = []
        for i, card_i in enumerate(lead_card_indexes):
            x_card = str(Card.from_code(card_i, xcards=True))
            card = (
                Card_.from_str(x_card)
                if x_card[1] != "x"
                else Card_(
                    Suit.from_str(x_card[0]),
                    min(
                        base_diag.hands[Direction.WEST].suits[Suit.from_str(x_card[0])]
                    ),
                )
            )
            candidate_cards.append(
                CandidateCard(
                    card=Card.from_code(card_i, xcards=True),
                    insta_score=lead_softmax[0, card_i],
                    p_make_contract=1
                    - sum(
                        [
                            1 if v >= tricks_to_defeat_contract else 0
                            for v in dd_solved[card]
                        ]
                    )
                    / len(dd_solved[card]),
                    expected_tricks=sum((dd_solved[card])) / len(dd_solved[card]),
                )
            )
            pass
        # for c in candidate_cards :
        #     print(c.card,c.p_make_contract)
        candidate_cards = sorted(
            candidate_cards,
            key=lambda c: c.p_make_contract if c.p_make_contract != None else 1,
        )

        return CardResp(
            card=candidate_cards[0].card, candidates=candidate_cards, samples=samples
        )

    def get_lead_candidates(self, auction, level):
        x_ftrs, b_ftrs = binary.get_lead_binary(
            auction, self.hand, self.binfo_model, self.vuln
        )
        lead_softmax = self.lead_model.model(x_ftrs, b_ftrs)
        lead_softmax = player.follow_suit(
            lead_softmax, self.hand, np.array([[0, 0, 0, 0]])
        )

        candidates = set()
        suits = set()
        hand = PlayerHand.from_pbn(self.hand_str)
        suit_length = len([s for s in Suit if len(hand.suits[s]) >= 1])

        while True:
            c = np.argmax(lead_softmax[0])
            card = Card.from_code(c, xcards=True)
            score = lead_softmax[0][c]
            if score < 0.05 and not (level >= 6 and card.suit not in suits):
                if level >= 6 and not len(suits) == suit_length:
                    lead_softmax[0][c] = 0
                    continue
                break
            lead_softmax[0][c] = 0
            if (
                level >= 6
                and Rank.ACE in hand.suits[Suit(card.suit)]
                and card.rank != 0
            ):
                continue
            suits.add(card.suit)
            if card.rank >= 5:
                card.rank = 7
            # print(card.code())
            candidates.add(card.code())
            if score > 0.85:
                break

        if level >= 6:
            for suit in Suit:
                if Rank.ACE in hand.suits[suit]:
                    candidates.add(Card(suit.value, rank=0, xcards=True).code())

        return list(candidates), lead_softmax

    def get_accepted_samples(self, n_samples, auction):
        contract = bidding.get_contract(auction)

        decl_i = bidding.get_decl_i(contract)
        lead_index = (decl_i + 1) % 4

        n_steps = 1 + len(auction) // 4

        accepted_samples = sample.sample_cards_auction(
            n_samples,
            n_steps,
            auction,
            lead_index,
            self.hand,
            self.vuln,
            self.bidder_model,
            self.binfo_model,
        )

        n_accepted = accepted_samples.shape[0]

        X_sd = np.zeros((n_accepted, 32 + 5 + 4 * 32))

        strain_i = bidding.get_strain_i(contract)

        X_sd[:, 32 + strain_i] = 1
        # lefty
        X_sd[:, (32 + 5 + 0 * 32) : (32 + 5 + 1 * 32)] = self.hand.reshape(32)
        # dummy
        X_sd[:, (32 + 5 + 1 * 32) : (32 + 5 + 2 * 32)] = accepted_samples[
            :, 0, :
        ].reshape((n_accepted, 32))
        # righty
        X_sd[:, (32 + 5 + 2 * 32) : (32 + 5 + 3 * 32)] = accepted_samples[
            :, 1, :
        ].reshape((n_accepted, 32))
        # declarer
        X_sd[:, (32 + 5 + 3 * 32) :] = accepted_samples[:, 2, :].reshape(
            (n_accepted, 32)
        )

        return accepted_samples


class CardPlayer:
    def __init__(
        self,
        player_models,
        player_i,
        hand_str,
        public_hand_str,
        contract,
        is_decl_vuln,
        play_record: PlayRecord,
        declarer: Direction,
        player_direction: Direction,
        dummy_hand: PlayerHand,
        player_hand: PlayerHand,
        playing_mode: PlayingMode,
        debug: bool = False,
    ):
        self.player_models = player_models
        self.model = player_models[player_i]
        self.player_i = player_i
        self.hand_32 = parse_hand_f(32)(hand_str).reshape(32)
        self.hand52 = parse_hand_f(52)(hand_str).reshape(52)
        self.public52 = parse_hand_f(52)(public_hand_str).reshape(52)
        self.contract = contract
        self.is_decl_vuln = is_decl_vuln
        self.n_tricks_taken = 0
        self.check_claim = False
        self.tricks_left = 13
        self.verbose = False
        self.level = int(contract[0])
        self.strain_i = bidding.get_strain_i(contract)
        self.trump = BiddingSuit.from_str(contract[1])
        self.play_record = play_record
        self.current_trick_as_dict = (
            play_record.record[-1].cards
            if play_record.record and len(play_record.record[-1]) != 4
            else {}
        )
        self.player_direction = player_direction
        self.declarer = declarer
        self.dummy_hand: PlayerHand = dummy_hand
        self.hand: PlayerHand = player_hand
        self.playing_mode = playing_mode
        self.hidden_cards = [
            card
            for card in deepcopy(TOTAL_DECK)
            if card
            not in dummy_hand.cards
            + player_hand.cards
            + play_record.as_unordered_one_dimension_list()
        ]

        self.init_x_play(parse_hand_f(32)(public_hand_str), self.level, self.strain_i)

        self.score_by_tricks_taken = [
            scoring.score(self.contract, self.is_decl_vuln, n_tricks)
            for n_tricks in range(14)
        ]
        self.debug = debug

    def init_x_play(self, public_hand, level, strain_i):
        self.x_play = np.zeros((1, 13, 298))
        binary.BinaryInput(self.x_play[:, 0, :]).set_player_hand(self.hand_32)
        binary.BinaryInput(self.x_play[:, 0, :]).set_public_hand(public_hand)
        self.x_play[:, 0, 292] = level
        self.x_play[:, 0, 293 + strain_i] = 1

    def set_card_played(self, trick_i, leader_i, i, card):
        played_to_the_trick_already = (i - leader_i) % 4 > (
            self.player_i - leader_i
        ) % 4

        if played_to_the_trick_already:
            return

        if self.player_i == i:
            return

        # update the public hand when the public hand played
        if self.player_i in (0, 2, 3) and i == 1 or self.player_i == 1 and i == 3:
            self.x_play[:, trick_i, 32 + card] -= 1

        # update the current trick
        offset = (self.player_i - i) % 4  # 1 = rho, 2 = partner, 3 = lho
        self.x_play[:, trick_i, 192 + (3 - offset) * 32 + card] = 1

    def set_own_card_played52(self, card52):
        self.hand52[card52] -= 1

    def set_public_card_played52(self, card52):
        self.public52[card52] -= 1

    @tracer.start_as_current_span("play_card")
    def play_card(
        self,
        trick_i,
        leader_i,
        current_trick52,
        players_states,
        probabilities_list,
        cheating_diag_pbn: Optional[str] = None,
    ):
        current_trick = [deck52.card52to32(c) for c in current_trick52]
        card52_dd = self.get_cards_dd_evaluation(
            trick_i,
            leader_i,
            current_trick52,
            players_states,
            probabilities_list,
            cheating_diag_pbn,
        )
        card_resp = self.pick_card_after_dd_eval(
            trick_i, leader_i, current_trick, players_states, card52_dd
        )

        return card_resp

    @tracer.start_as_current_span("get_cards_dd_evaluation")
    def get_cards_dd_evaluation(
        self,
        trick_i,
        leader_i,
        current_trick52,
        players_states,
        probabilities_list,
        cheating_diag_pbn: Optional[str],
    ):
        def create_diag_from_32(
            base_diag: Diag, array_of_array_32: List[np.ndarray], pips: List[Card_]
        ):
            diag = deepcopy(base_diag)
            pips_as_dict = {
                s: [card.rank for card in pips if card.suit == s] for s in Suit
            }
            for dir in not_visible_hands_directions:
                diag.hands[dir] = create_hand_from_32(
                    array_of_array_32[dir.to_player_i(self.declarer)].reshape((4, 8)),
                    pips_as_dict,
                    dir,
                )
            return diag

        def create_hand_from_32(
            array_of_8_suits: np.ndarray, pips: Dict[Suit, List[Rank]], dir: Direction
        ):
            return PlayerHand(
                {
                    suit: create_suit_from_8(array_8, pips[suit], suit, dir)
                    for array_8, suit in zip(array_of_8_suits, Suit)
                }
            )

        def create_suit_from_8(array_8, pip: List[Rank], suit: Suit, dir: Direction):
            current_trick_card = (
                None
                if dir not in self.current_trick_as_dict
                else self.current_trick_as_dict[dir]
            )
            random.shuffle(pip)
            high_ranks = [
                Rank.from_integer(int(i))
                for i in np.nonzero(array_8[:-1])[0]
                if current_trick_card is None
                or Card_(suit, Rank.from_integer(int(i))) != current_trick_card
            ]
            try:
                low_ranks = [
                    pip.pop()
                    for _ in range(
                        int(array_8[-1])
                        - (
                            1
                            if current_trick_card is not None
                            and current_trick_card.rank <= Rank.SEVEN
                            and current_trick_card.suit == suit
                            else 0
                        )
                    )
                ]
            except:
                raise Exception("Pop from empty ?")
            return high_ranks + low_ranks

        def get_base_diag() -> Diag:
            base_diag = Diag(
                {dir: PlayerHand({s: [] for s in Suit}) for dir in Direction},
                autocomplete=False,
            )
            if self.declarer.offset(2) == self.player_direction:
                base_diag.hands[self.player_direction] = self.dummy_hand
                base_diag.hands[self.declarer] = self.hand
            else:
                base_diag.hands[self.player_direction] = self.hand
                base_diag.hands[self.declarer.offset(2)] = self.dummy_hand

            return base_diag

        base_diag = get_base_diag()
        not_visible_hands_directions = [
            dir
            for dir in Direction
            if dir
            not in [
                self.player_direction,
                self.declarer.offset(2)
                if self.player_direction != self.declarer.offset(2)
                else self.declarer,
            ]
        ]
        low_hidden_cards = [c for c in self.hidden_cards if c.rank <= Rank.SEVEN]
        n_samples = players_states[0].shape[0]
        with tracer.start_as_current_span("get diags_from_np_arrays") as _:
            samples_as_diag = [
                create_diag_from_32(
                    base_diag,
                    [players_states[j][i, trick_i, :32] for j in range(4)],
                    low_hidden_cards,
                )
                for i in range(n_samples)
            ]

        # and self.player_direction not in [self.declarer,self.declarer.partner()]
        if cheating_diag_pbn is not None:
            reduced_samples = 10
            cheating_factor = (
                0.9
                if self.player_direction not in [self.declarer, self.declarer.partner()]
                and self.tricks_left <= 6
                else 0.4
            )
            step = ceil(len(samples_as_diag) / reduced_samples)
            samples_as_diag = (
                samples_as_diag[:reduced_samples]
                + samples_as_diag[reduced_samples::step]
            )
            probabilities_list = list(probabilities_list[:reduced_samples]) + list(
                probabilities_list[reduced_samples::step]
            )
            samples_as_diag.append(Diag.init_from_pbn(cheating_diag_pbn))
            probabilities_list = np.append(
                probabilities_list, (np.sum(probabilities_list) * cheating_factor)
            )
            probabilities_list = convert_to_probability(probabilities_list)

        if self.play_record.record is None:
            raise Exception("Play record should not be none")

        leader_i = (leader_i + self.declarer.offset(2).value) % 4
        start = time.time()
        dd_solved = DDS.solve(
            self.strain_i,
            leader_i,
            current_trick52,
            [
                diag.print_as_pbn(first_direction=Direction.WEST)
                for diag in samples_as_diag
            ],
        )
        with open("dds.log", "a") as f:
            f.write("DDS took {} seconds\n".format(time.time() - start))

        if any(
            [
                all([trick == self.tricks_left for trick in card_res])
                for card_res in dd_solved.values()
            ]
        ):
            self.check_claim = True

        card_tricks = ddsolver.expected_tricks(dd_solved, probabilities_list)
        if self.playing_mode is PlayingMode.MATCHPOINTS:
            card_ev = self.get_card_ev_mp(dd_solved, probabilities_list)
        else:
            card_ev = self.get_card_ev(dd_solved, probabilities_list)

        card_result = {}
        for key in dd_solved.keys():
            card_result[key] = (card_tricks[key], card_ev[key])

        if self.debug:
            for (
                i,
                (diag, p),
            ) in enumerate(zip(samples_as_diag, probabilities_list)):
                string = ""
                for card, res in dd_solved.items():
                    string += "{}:{},".format(Card_.get_from_52(card), res[i])
                print(
                    round(p, 5),
                    ":",
                    diag.print_as_pbn(first_direction=Direction.WEST),
                    string,
                )
            for key, value in card_result.items():
                print(Card_.get_from_52(key), value)
            print("   {}".format([i for i in range(len(samples_as_diag))]))
            for key, value in dd_solved.items():
                print(Card_.get_from_52(key), value)

        return card_result

    def get_card_ev(self, dd_solved, probabilities_list):
        card_ev = {}
        sign = 1 if self.player_i % 2 == 1 else -1
        for card, future_tricks in dd_solved.items():
            ev_sum = 0
            for ft, proba in zip(future_tricks, probabilities_list):
                if ft < 0:
                    continue
                tot_tricks = self.n_tricks_taken + ft
                tot_decl_tricks = (
                    tot_tricks if self.player_i % 2 == 1 else 13 - tot_tricks
                )
                ev_sum += sign * self.score_by_tricks_taken[tot_decl_tricks] * proba
            card_ev[card] = ev_sum

        return card_ev

    def get_card_ev_mp(self, dd_solved: Dict, probabilities_list):
        card_ev = {}
        for card, future_tricks in dd_solved.items():
            ev_sum = 0
            for ft, proba in zip(future_tricks, probabilities_list):
                if ft < 0:
                    continue
                ev_sum += ft * proba
            card_ev[card] = ev_sum

        return card_ev

    def reverse_dds_results(self, dd_solved: Dict[int, List[int]]):
        return {
            card: [self.tricks_left - old_res for old_res in res]
            for card, res in dd_solved.items()
        }

    def next_card_softmax(self, trick_i):
        return player.follow_suit(
            self.model.next_cards_softmax(self.x_play[:, : (trick_i + 1), :]),
            binary.BinaryInput(self.x_play[:, trick_i, :]).get_player_hand(),
            binary.BinaryInput(self.x_play[:, trick_i, :]).get_this_trick_lead_suit(),
        ).reshape(-1)

    def pick_card_after_dd_eval(
        self, trick_i, leader_i, current_trick, players_states, card_dd
    ) -> str:
        t_start = time.time()
        card_softmax = self.next_card_softmax(trick_i)

        all_cards = np.arange(32)
        s_opt = card_softmax > 0.01

        card_options, card_scores = all_cards[s_opt], card_softmax[s_opt]

        card_nn = {c: s for c, s in zip(card_options, card_scores)}

        candidate_cards: List[CandidateCard] = []

        for card52, (e_tricks, e_score) in card_dd.items():
            card32 = deck52.card52to32(card52)

            candidate_cards.append(
                CandidateCard(
                    card=Card.from_code(card52),
                    insta_score=card_nn.get(card32, 0),
                    expected_tricks=e_tricks,
                    p_make_contract=None,
                    expected_score=e_score,
                )
            )

        samples = []
        for i in range(min(20, players_states[0].shape[0])):
            samples.append(
                "%s %s %s %s"
                % (
                    hand_to_str(players_states[0][i, 0, :32].astype(int)),
                    hand_to_str(players_states[1][i, 0, :32].astype(int)),
                    hand_to_str(players_states[2][i, 0, :32].astype(int)),
                    hand_to_str(players_states[3][i, 0, :32].astype(int)),
                )
            )

        candidate_cards = sorted(
            candidate_cards,
            key=lambda c: (c.expected_score, c.insta_score + random.random() / 10000),
            reverse=True,
        )
        best_card_resp: CardResp = CardResp(
            card=candidate_cards[0].card, candidates=candidate_cards, samples=samples
        )
        # for candidate_card in candidate_cards :
        #     print(candidate_card.to_dict())

        # Max expected score difference ?
        max_expected_score = max(
            [
                float(c.expected_score)
                for c in candidate_cards
                if c.expected_score is not None
            ]
        )
        card_with_max_expected_score = {
            c: c.expected_score
            for c in candidate_cards
            if c.expected_score == max_expected_score
        }
        if len(card_with_max_expected_score) == 1:
            return best_card_resp.card.symbol()
        candidate_cards = [
            c for c in candidate_cards if c in card_with_max_expected_score.keys()
        ]

        # Don't pick a 8 or 9 when NN difference if you have a small card in the same suit
        for c in candidate_cards:
            if c.card.rank in [5, 6]:  # 8 or 9
                for compared_candidate in candidate_cards:
                    if (
                        compared_candidate.card.rank >= 7
                        and compared_candidate.card.suit == c.card.suit
                    ):
                        c.insta_score = compared_candidate.insta_score
                        break  # Below 7, they all have the same insta_score

        # NN difference ?
        max_insta_score = max(
            [float(c.insta_score) for c in candidate_cards if c.insta_score is not None]
        )
        card_with_max_insta_score = {
            c: c.insta_score
            for c in candidate_cards
            if c.insta_score == max_insta_score
            and c.expected_score == max_expected_score
        }
        if len(card_with_max_insta_score) == 1:
            return best_card_resp.card.symbol()

        # Play some human carding
        hand = PlayerHand.from_pbn(deck52.hand_to_str(self.hand52))
        valid_cards = [
            Card_.from_str(c.card.symbol()) for c in card_with_max_insta_score.keys()
        ]
        return str(
            play_real_card(
                hand,
                valid_cards,
                self.trump,
                self.play_record,
                self.player_direction,
                self.declarer,
            )
        )
