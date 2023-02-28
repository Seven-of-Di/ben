from typing import List
import bots
from .utils import Diag,Direction
from bidding import bidding


class AsyncBotBid(bots.BotBid):
    async def async_bid(self, auction):
        return self.restful_bid(auction)

    async def async_get_samples_from_auction(self,auction) :
        return self.get_samples_from_auction(auction)

class AsyncBotLead(bots.BotLead):
    async def async_lead(self, auction):
        return self.lead(auction)

class AsyncCardPlayer(bots.CardPlayer):
    async def async_play_card(self, trick_i, leader_i, current_trick52, players_states,probabilities_list):
        return self.play_card(trick_i, leader_i, current_trick52, players_states,probabilities_list)

class FullBoardPlayer() :
    def __init__(self,diag : Diag,vuls : List[bool],dealer : Direction,models) -> None:
        self.diag = diag
        self.vuls = vuls
        self.dealer = dealer
        self.models = models

    def get_auction(self) :
        auction = []
        self.vuls = [True, False]
        while not bidding.auction_over(auction):
            auction.append(bots.BotBid(self.vuls, self.diag.hands[Direction(
                len(auction) % 4)].to_pbn(), self.models).restful_bid(auction).bid)

    def get_card_play(self,auction) :
        pass