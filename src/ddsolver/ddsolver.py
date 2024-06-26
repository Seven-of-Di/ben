import ctypes
from typing import Dict, List

from ddsolver import dds
from tracing import tracer



class DDSolver:

    def __init__(self, dds_mode=0):
        self.dds_mode = dds_mode
        self.bo = dds.boardsPBN()
        self.solved = dds.solvedBoards()


    @tracer.start_as_current_span("dds_solver")
    def solve(self, strain_i, leader_i, current_trick, hands_pbn):
        results = self.solve_helper(
            strain_i, leader_i, current_trick, hands_pbn[:dds.MAXNOOFBOARDS])

        if len(hands_pbn) > int(dds.MAXNOOFBOARDS):
            i = int(dds.MAXNOOFBOARDS)
            while i < len(hands_pbn):
                more_results = self.solve_helper(
                    strain_i, leader_i, current_trick, hands_pbn[i:i+int(dds.MAXNOOFBOARDS)])

                for card, values in more_results.items():
                    results[card] = results[card] + values

                i += int(dds.MAXNOOFBOARDS)

        return results

    def solve_helper(self, strain_i, leader_i, current_trick, hands_pbn):
        card_rank = [0x4000, 0x2000, 0x1000, 0x0800, 0x0400, 0x0200,
                     0x0100, 0x0080, 0x0040, 0x0020, 0x0010, 0x0008, 0x0004]

        self.bo.noOfBoards = min(int(dds.MAXNOOFBOARDS), len(hands_pbn))

        for handno in range(self.bo.noOfBoards):
            self.bo.deals[handno].trump = (strain_i - 1) % 5
            self.bo.deals[handno].first = (leader_i - 1) % 4

            for i in range(3):
                self.bo.deals[handno].currentTrickSuit[i] = 0
                self.bo.deals[handno].currentTrickRank[i] = 0
                if i < len(current_trick):
                    self.bo.deals[handno].currentTrickSuit[i] = current_trick[i] // 13
                    self.bo.deals[handno].currentTrickRank[i] = 14 - \
                        current_trick[i] % 13

            self.bo.deals[handno].remainCards = hands_pbn[handno].encode(
                'utf-8')

            self.bo.target[handno] = -1
            self.bo.solutions[handno] = 3
            self.bo.mode[handno] = self.dds_mode

        res = dds.SolveAllBoards(ctypes.pointer(
            self.bo), ctypes.pointer(self.solved))

        try:
            assert res == 1
        except:
            raise AssertionError(res)

        card_results = {}

        for handno in range(self.bo.noOfBoards):
            fut = ctypes.pointer(self.solved.solvedBoards[handno])
            for i in range(fut.contents.cards):
                suit_i = fut.contents.suit[i]
                card = suit_i * 13 + 14 - fut.contents.rank[i]
                if card not in card_results:
                    card_results[card] = []
                card_results[card].append(fut.contents.score[i])
                eq_cards_encoded = fut.contents.equals[i]
                for k, rank_code in enumerate(card_rank):
                    if rank_code & eq_cards_encoded > 0:
                        eq_card = suit_i * 13 + k
                        if eq_card not in card_results:
                            card_results[eq_card] = []
                        card_results[eq_card].append(fut.contents.score[i])

        return card_results


def expected_tricks(card_results, probabilities_list : List[float]):
    return {card: sum([p*res for p, res in zip(probabilities_list, result_list)]) for card, result_list in card_results.items()}


def expected_tricks_test(card_results, probabilities_list):
    return {card: [p*res for p, res in zip(probabilities_list, result_list)] for card, result_list in card_results.items()}


def p_made_target(target):
    def fun(card_results):
        return {card: (sum(x for x in values if x >= target)/len(values)) for card, values in card_results.items()}
    return fun

