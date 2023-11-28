from typing import Dict, List
import bots


class AsyncBotBid(bots.BotBid):
    async def async_bid(self, auction):
        return self.restful_bid(auction)

    async def async_get_samples_from_auction(self, auction):
        return self.get_samples_from_auction(auction)


class AsyncBotLead(bots.BotLead):
    async def async_lead(self, auction):
        return self.lead(auction)


class AsyncCardPlayer(bots.CardPlayer):
    async def async_play_card(
        self, trick_i, leader_i, current_trick52, players_states, probabilities_list
    ):
        return self.play_card(
            trick_i, leader_i, current_trick52, players_states, probabilities_list
        )
