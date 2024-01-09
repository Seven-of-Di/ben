import random
from typing import List
from utils import Direction, PlayerHand, VULNERABILITIES, Diag, Suit, Rank, Card_
from PlayRecord import PlayRecord, BiddingSuit


def lead_real_card(hand: PlayerHand, card_str: str, trump: BiddingSuit):
    if not card_str[1] == "x":
        return Card_.from_str(card_str)
    suit_to_play = Suit.from_str(card_str[0])
    if trump.to_suit() == suit_to_play:
        return Card_(suit_to_play, pick_random_low([c for c in hand.suits[suit_to_play]]))
    if trump == BiddingSuit.NO_TRUMP:
        return Card_(suit_to_play, fourth_best(hand, suit_to_play, partner_suit=False))
    else:
        return Card_(suit_to_play, third_fifth(hand, suit_to_play))


def play_real_card(hand: PlayerHand, valid_cards: List[Card_], trump: BiddingSuit, play_record: PlayRecord, player_direction: Direction, declarer: Direction) -> Card_:
    suit_to_play = valid_cards[0].suit
    valid_cards = [c for c in valid_cards if c.suit == suit_to_play]
    valid_ranks = [c.rank for c in valid_cards]
    if len([c for c in valid_cards if c.suit == suit_to_play]) == 1:
        return [c for c in valid_cards if c.suit == suit_to_play][0]
    if player_direction == declarer.partner():
        return Card_(suit_to_play, sorted(valid_ranks)[0])
    if trump.to_suit() == suit_to_play:
        return Card_(suit_to_play, pick_random_from_valid_ranks(valid_ranks))
    if player_direction == declarer:
        return Card_(suit_to_play, pick_random_from_valid_ranks(valid_ranks))
    if play_record.record == None:
        raise Exception("play record should not be empty")
    on_lead = len(play_record.record[-1]) % 4 == 0
    if not on_lead:
        cards_played_by_player = play_record.get_cards_played_by_direction(
            player_direction)
        if any([card.suit == suit_to_play and card.rank<=Rank.NINE for card in cards_played_by_player]):
            return Card_(suit_to_play, sorted(valid_ranks)[0])
        else:
            return Card_(suit_to_play, standard_count(hand, suit_to_play, valid_ranks))
    else:
        cards_played_by_player = play_record.get_cards_played_by_direction(
            player_direction)
        if any([card.suit == suit_to_play for card in cards_played_by_player]):
            return Card_(suit_to_play, sorted(valid_ranks)[0])
        else:
            return Card_(suit_to_play, low_encouraging(hand, suit_to_play, valid_ranks))


def pick_random_from_valid_ranks(valid_ranks: List[Rank]) -> Rank:
    return random.choice(valid_ranks)


def pick_random_low(valid_ranks: List[Rank]) -> Rank:
    return random.choice([c for c in valid_ranks])


def fourth_best(hand: PlayerHand, suit: Suit, partner_suit: bool) -> Rank:
    length = len(hand.suits[suit])
    suit_ranks = sorted(hand.suits[suit], reverse=True)
    if length == 1 or length == 2:
        return suit_ranks[0]
    if length == 3:
        if not partner_suit:
            if hand.number_of_figures(suit) == 0:
                return suit_ranks[0]
            return suit_ranks[2]
        return suit_ranks[2]
    if length >= 4:
        if not partner_suit:
            if hand.number_of_figures(suit) == 0:
                return suit_ranks[1]
            return suit_ranks[3]
        if partner_suit:
            if length % 2 == 1:
                return suit_ranks[-1]
            if hand.number_of_figures(suit) == 0:
                return suit_ranks[1]
            return suit_ranks[2]
    raise Exception("Couldn't lead 4th best in this suit - too bad")


def third_fifth(hand: PlayerHand, suit: Suit) -> Rank:
    length = len(hand.suits[suit])
    suit_ranks = sorted(hand.suits[suit], reverse=True)
    if length == 1 or length == 2:
        return suit_ranks[0]
    if length == 3:
        return suit_ranks[2]
    if length == 4:
        if hand.number_of_figures(suit) == 0:
            return suit_ranks[1]
        else:
            return suit_ranks[2]
    if length >= 5:
        return suit_ranks[4]
    raise Exception("Couldn't lead 3rd 5th best in this suit - too bad")


def low_encouraging(hand: PlayerHand, suit: Suit, valid_ranks: List[Rank]) -> Rank:
    valid_ranks = sorted(valid_ranks, reverse=True)
    if hand.number_of_figures(suit) == 0:
        return valid_ranks[0]
    else:
        return valid_ranks[-1]
    raise Exception(
        "Couldn't lead low encouraging best in this suit - too bad")


def standard_count(hand: PlayerHand, suit: Suit, valid_ranks: List[Rank]) -> Rank:
    valid_ranks = sorted(valid_ranks, reverse=True)
    length = len(hand.suits[suit])
    suit_ranks = sorted(hand.suits[suit], reverse=True)
    if length % 2 == 1:
        return valid_ranks[-1]
    if length == 2:
        return valid_ranks[0]
    for rank in suit_ranks[1:]:
        if rank in valid_ranks:
            return rank
    return valid_ranks[-1]
