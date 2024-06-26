from __future__ import annotations
from copy import deepcopy
import random
from tracing import tracer
from typing import Dict, List, Set, Tuple
from utils import (
    Diag,
    Direction,
    Card_,
    BiddingSuit,
    Suit,
    Rank,
    PlayerHand,
    TOTAL_DECK,
)
from PlayRecord import PlayRecord, Trick
from ddsolver import ddsolver


def convert_diag_with_new_suit_rank(
    diag: Diag, current_trick: List[Card_]
) -> Tuple[Diag, List[Card_]]:
    new_suit_rank = create_new_suit_rank(diag, current_trick)
    new_hands = {}
    for dir in Direction:
        new_hands[dir] = PlayerHand(
            {
                s: [new_suit_rank[s][rank] for rank in diag.hands[dir].suits[s]]
                for s in Suit
            }
        )
    return (
        Diag(new_hands, autocomplete=False),
        [Card_(c.suit, new_suit_rank[c.suit][c.rank]) for c in current_trick],
    )


def create_new_suit_rank(
    diag: Diag, current_trick: List[Card_]
) -> Dict[Suit, Dict[Rank, Rank]]:
    total_deck = {s: [] for s in Suit}
    for hand in diag.hands.values():
        for s in Suit:
            total_deck[s] += hand.suits[s]
    for card in current_trick:
        total_deck[card.suit].append(card.rank)

    new_suit_rank = {s: {} for s in Suit}
    for s, ranks in total_deck.items():
        new_order = sorted(ranks, reverse=True)
        for i, rank in enumerate(new_order):
            new_suit_rank[s][rank] = Rank.from_integer(i)
    return new_suit_rank


def convert_intermediate_cards_to_low(
    diag: Diag,
    claim_direction: Direction,
    shown_out_suits: Dict[Direction, Set[Suit]],
    current_trick: List[Card_],
    trick_leader: Direction,
) -> Tuple[Diag, List[Card_]]:
    lowest_max_card_from_claiming_side = {s: Rank.TWO for s in Suit}
    current_trick_dict = {
        trick_leader.offset(i): card for i, card in enumerate(current_trick)
    }
    for suit in Suit:
        if any(
            suit in shown_out_suits[opp]
            for opp in [claim_direction.offset(1), claim_direction.offset(3)]
        ):
            continue
        rank_tested = (
            max(
                diag.hands[claim_direction].suits[suit]
                + diag.hands[claim_direction.partner()].suits[suit]
            )
            if len(
                diag.hands[claim_direction].suits[suit]
                + diag.hands[claim_direction.partner()].suits[suit]
            )
            != 0
            else Rank.ACE
        )
        for _ in range(13):
            rank_in_hands = (
                rank_tested in diag.hands[claim_direction].suits[suit]
                or rank_tested in diag.hands[claim_direction.partner()].suits[suit]
            )
            rank_in_current_trick = rank_tested in [
                c.rank
                for dir, c in current_trick_dict.items()
                if dir in [claim_direction, claim_direction.partner()]
                and c.suit == suit
            ]
            if not (rank_in_hands) and not (rank_in_current_trick):
                lowest_max_card_from_claiming_side[suit] = rank_tested
                break
            rank_tested = rank_tested.offset(-1)

    # print(lowest_max_card_from_claiming_side)

    converter = {s: {} for s in Suit}
    for suit in Suit:
        claiming_side_in_hand = [
            rank
            for rank in (
                diag.hands[claim_direction].suits[suit]
                + diag.hands[claim_direction.partner()].suits[suit]
            )
            if rank < lowest_max_card_from_claiming_side[suit]
        ]
        claming_side_current_trick = [
            c.rank
            for dir, c in current_trick_dict.items()
            if c.suit == suit
            and dir in [claim_direction, claim_direction.partner()]
            and c.rank < lowest_max_card_from_claiming_side[suit]
        ]
        claming_side_intermediate_ranks = sorted(
            claiming_side_in_hand + claming_side_current_trick
        )

        other_side_small_ranks = [
            rank
            for rank in diag.hands[claim_direction.offset(1)].suits[suit]
            + diag.hands[claim_direction.offset(3)].suits[suit]
            + [
                c.rank
                for dir, c in current_trick_dict.items()
                if c.suit == suit
                and dir in [claim_direction.offset(1), claim_direction.offset(3)]
            ]
            if rank <= lowest_max_card_from_claiming_side[suit]
        ]
        other_side_small_ranks = sorted(other_side_small_ranks, reverse=True)

        for old_rank, new_rank in zip(claming_side_intermediate_ranks, Rank):
            converter[suit][old_rank] = new_rank
        for i, old_rank in enumerate(other_side_small_ranks):
            converter[suit][old_rank] = lowest_max_card_from_claiming_side[suit].offset(
                -(i)
            )

    # print(converter)

    new_hands = {}
    for dir in Direction:
        new_hands[dir] = PlayerHand(
            {
                s: [
                    converter[s][rank] if rank in converter[s] else rank
                    for rank in diag.hands[dir].suits[s]
                ]
                for s in Suit
            }
        )
    return (
        Diag(new_hands, autocomplete=False),
        [
            (
                Card_(c.suit, converter[c.suit][c.rank])
                if c.rank in converter[c.suit]
                else c
            )
            for c in current_trick
        ],
    )


def generate_diags(
    diag: Diag,
    claiming_direction: Direction,
    dummy: Direction,
    shown_out_suits_map: Dict[Direction, Set[Suit]],
    n_samples=50,
) -> List[Diag]:
    # Prepare base diagramm
    hidden_hands_dirs = [
        dir for dir in Direction if dir not in [dummy, claiming_direction]
    ]
    length_per_dir = {dir: len(diag.hands[dir]) for dir in Direction}
    hidden_cards = [card for dir in hidden_hands_dirs for card in diag.hands[dir].cards]
    new_diag_base = Diag(
        {
            dir: (
                diag.hands[dir]
                if dir not in hidden_hands_dirs
                else PlayerHand({s: [] for s in Suit})
            )
            for dir in Direction
        },
        autocomplete=False,
    )
    for dir, shown_out_suits in shown_out_suits_map.items():
        if dir not in hidden_hands_dirs:
            continue
        other_dir = [d for d in hidden_hands_dirs if d != dir][0]
        for suit in shown_out_suits:
            known_cards = [card for card in hidden_cards if card.suit == suit]
            hidden_cards = [card for card in hidden_cards if card not in known_cards]
            [new_diag_base.hands[other_dir].append(card) for card in known_cards]
    left_to_deal_per_dir = {
        dir: initial_length - len(new_diag_base.hands[dir])
        for dir, initial_length in length_per_dir.items()
    }

    ### Shuffle and deal
    def generate_sample():
        sample_diag = deepcopy(new_diag_base)
        random.shuffle(hidden_cards)
        shuffled_hidden_cards = deepcopy(hidden_cards)
        for dir, left_to_deal in left_to_deal_per_dir.items():
            random_cards, shuffled_hidden_cards = (
                shuffled_hidden_cards[:left_to_deal],
                shuffled_hidden_cards[left_to_deal:],
            )
            [sample_diag.hands[dir].append(card) for card in random_cards]
        return sample_diag

    return [generate_sample() for _ in range(n_samples)]


def dds_check(
    samples: List[Diag],
    trump: BiddingSuit,
    trick_leader: Direction,
    current_trick: List[Card_],
    claim: int,
    claim_direction: Direction,
    declarer: Direction,
):
    for sample in samples:
        sample.is_valid()
    # for sample in samples[:5]:
    #     print(sample)

    dd_solved = ddsolver.DDSolver(dds_mode=2).solve(
        trump.strain(),
        trick_leader.offset(1).value,
        [card.to_52() for card in current_trick],
        [sample.print_as_pbn() for sample in samples],
    )
    # for key, value in dict(sorted(dd_solved.items())).items():
    #     print(Card_.get_from_52(key), value)

    possible_tricks_left = len(samples[0].hands[trick_leader]) + (
        1 if len(current_trick) % 4 != 0 else 0
    )

    if claim_direction == declarer:
        return check_declarer_claim(
            dd_solved=dd_solved,
            claim_direction=claim_direction,
            trick_leader=trick_leader,
            claim=claim,
            current_trick=current_trick,
            possible_tricks_left=possible_tricks_left,
        )
    else:
        return check_defensive_claim(
            dd_solved=dd_solved,
            claim_direction=claim_direction,
            trick_leader=trick_leader,
            claim=claim,
            current_trick=current_trick,
            possible_tricks_left=possible_tricks_left,
        )


def check_declarer_claim(
    dd_solved,
    claim_direction: Direction,
    trick_leader: Direction,
    claim: int,
    current_trick: List[Card_],
    possible_tricks_left: int,
) -> bool:
    claimer_turn = claim_direction in [
        trick_leader.offset(len(current_trick)),
        trick_leader.offset(len(current_trick) + 2),
    ]
    if claimer_turn:
        return (
            True
            if any(
                all([i >= claim for i in card_res]) for card_res in dd_solved.values()
            )
            else False
        )
    else:
        return (
            True
            if all(
                all([i <= possible_tricks_left - claim for i in card_res])
                for card_res in dd_solved.values()
            )
            else False
        )


def check_defensive_claim(
    dd_solved,
    claim_direction: Direction,
    trick_leader: Direction,
    claim: int,
    current_trick: List[Card_],
    possible_tricks_left: int,
) -> bool:
    claimer_in_hand = claim_direction == trick_leader.offset(len(current_trick))
    claimer_partner_in_hand = claim_direction == trick_leader.offset(
        len(current_trick) + 2
    )
    if claimer_in_hand:
        return (
            True
            if any(
                all([i >= claim for i in card_res]) for card_res in dd_solved.values()
            )
            else False
        )
    if claimer_partner_in_hand:
        return (
            True
            if all(
                all([i >= claim for i in card_res]) for card_res in dd_solved.values()
            )
            else False
        )
    else:
        return (
            True
            if all(
                all([i <= possible_tricks_left - claim for i in card_res])
                for card_res in dd_solved.values()
            )
            else False
        )


def complete_3_card_trick(
    diag: Diag,
    current_trick: List[Card_],
    claim_direction: Direction,
    trick_leader: Direction,
    declarer: Direction,
):
    assert len(current_trick) == 3
    assert claim_direction == trick_leader.offset(3) or (
        claim_direction == declarer and trick_leader.offset(3) == declarer.offset(2)
    )


def check_claim(
    diag: Diag,
    claim: int,
    claim_direction: Direction,
    trump: BiddingSuit,
    declarer: Direction,
    shown_out_suits: Dict[Direction, Set[Suit]],
    current_trick: List[Card_],
    trick_leader: Direction,
    n_samples=10,
    real_diag: Diag | None = None,
) -> bool:
    if claim == 0:
        return True
    dummy = declarer.offset(2)
    current_trick_copy = deepcopy(current_trick)
    diag, current_trick = convert_diag_with_new_suit_rank(diag, current_trick)
    diag, current_trick = convert_intermediate_cards_to_low(
        diag, claim_direction, shown_out_suits, current_trick, trick_leader
    )
    diags = generate_diags(diag, claim_direction, dummy, shown_out_suits, n_samples)
    # for diag in diags[:5]:
    #     print(diag)
    if real_diag :
        real_diag,current_trick_copy = convert_diag_with_new_suit_rank(real_diag, current_trick_copy)
        real_diag,current_trick_copy = convert_intermediate_cards_to_low(real_diag, claim_direction, shown_out_suits, current_trick_copy, trick_leader)
    return dds_check(
        diags, trump, trick_leader, current_trick, claim, claim_direction, declarer
    ) and (dds_check([real_diag], trump, trick_leader, current_trick_copy, claim, claim_direction, declarer) if real_diag is not None else True)


@tracer.start_as_current_span("check_claim_from_api")
async def check_claim_from_api(
    claiming_hand_str: str,
    dummy_hand_str: str,
    claiming_direction_str: str,
    declarer_str: str,
    contract_str: str,
    tricks_as_str: List[List[str]],
    absolute_claim: int,
    real_diag: Diag | None,
    n_samples=30,
) -> bool:
    claiming_direction = Direction.from_str(claiming_direction_str)
    declarer = Direction.from_str(declarer_str)
    claiming_direction = (
        declarer if claiming_direction == declarer.partner() else claiming_direction
    )
    trump = BiddingSuit.from_str(contract_str[1])
    claiming_hand = PlayerHand.from_pbn(claiming_hand_str)
    dummy_hand = PlayerHand.from_pbn(dummy_hand_str)
    play_record = PlayRecord.from_tricks_as_list(trump, tricks_as_str, declarer)
    shown_out_suits = play_record.shown_out_suits
    play_length = play_record.length_wo_incomplete()
    declarer_tricks = play_record.number_of_tricks
    tricks = [[Card_.from_str(card) for card in trick] for trick in tricks_as_str]
    flat_tricks = [item for sublist in tricks for item in sublist]
    last_trick = tricks[-1] if tricks != [] and len(tricks[-1]) != 4 else []

    relative_claim = absolute_claim - (
        declarer_tricks
        if claiming_direction == declarer
        else play_length - declarer_tricks
    )

    diag = Diag(
        {dir: PlayerHand({s: [] for s in Suit}) for dir in Direction},
        autocomplete=False,
    )
    diag.hands[claiming_direction] = claiming_hand
    diag.hands[declarer.offset(2)] = dummy_hand
    hidden_cards = [
        card
        for card in TOTAL_DECK
        if card not in flat_tricks
        and card not in claiming_hand.cards
        and card not in dummy_hand.cards
    ]

    other_directions = [
        dir
        for dir in Direction
        if dir != claiming_direction and dir != declarer.offset(2)
    ]
    current_trick_leader = declarer.offset(1)
    if not play_record.record:
        current_trick_leader = declarer.offset(1)
    elif len(play_record.record[-1]) == 4:
        current_trick_leader = play_record.record[-1].winner(trump)
    elif len(play_record.record[-1]) != 4 and len(play_record) >= 2:
        current_trick_leader = play_record.record[-2].winner(trump)
    other_directions = (
        [other_directions[0], other_directions[1]]
        if current_trick_leader.farest(other_directions[0], other_directions[1])
        == other_directions[0]
        else [other_directions[1], other_directions[0]]
    )

    for i in range(len(hidden_cards) + 1):
        if len(hidden_cards) == 0:
            break
        dir = other_directions[i % 2]
        diag.hands[dir].append(hidden_cards.pop())
    assert len(hidden_cards) == 0

    return check_claim(
        diag,
        relative_claim,
        claiming_direction,
        trump,
        declarer,
        shown_out_suits,
        last_trick,
        current_trick_leader,
        n_samples,
        real_diag,
    )

    raise Exception("This should not append !")


if __name__ == "__main__":
    diag = Diag.init_from_pbn("N:..KJ6.2 2..Q37. 5..AT2 ...J863")
    print(diag)
    print(
        check_claim(
            diag=diag,
            claim=4,
            claim_direction=Direction.SOUTH,
            trump=BiddingSuit.SPADES,
            declarer=Direction.SOUTH,
            shown_out_suits={
                d: (set() if d != Direction.EAST else {Suit.DIAMONDS})
                for d in Direction
            },
            current_trick=[],
            trick_leader=Direction.SOUTH,
        )
    )
    diag = Diag.init_from_pbn("N:..KJ6.2 2..Q37. 5..AT2 ...J863")
    print(diag)
    print(
        check_claim(
            diag=diag,
            claim=4,
            claim_direction=Direction.SOUTH,
            trump=BiddingSuit.SPADES,
            declarer=Direction.SOUTH,
            shown_out_suits={d: (set()) for d in Direction},
            current_trick=[],
            trick_leader=Direction.SOUTH,
        )
    )
    diag = Diag.init_from_pbn("N:6..KJ6. ..A37.3 5..QT2 ..845.J")
    print(diag)
    print(
        check_claim(
            diag=diag,
            claim=3,
            claim_direction=Direction.SOUTH,
            trump=BiddingSuit.SPADES,
            declarer=Direction.SOUTH,
            shown_out_suits={d: set() for d in Direction},
            current_trick=[],
            trick_leader=Direction.EAST,
        )
    )
