import deck52
import pprint
import time
import json
import asyncio
import uuid
import shelve

import numpy as np

import human
import bots
import sample
import conf

from bidding import bidding
from nn.models import Models
from deck52 import decode_card
from bidding.binary import DealData
from objects import CardResp, Card


def random_deal():
    deal_str = deck52.random_deal()
    auction_str = deck52.random_dealer_vuln()

    return deal_str, auction_str


class AsyncBotBid(bots.BotBid):
    async def async_bid(self, auction):
        return self.bid(auction)

class AsyncBotLead(bots.BotLead):
    async def async_lead(self, auction):
        return self.lead(auction)

class AsyncCardPlayer(bots.CardPlayer):
    async def async_play_card(self, trick_i, leader_i, current_trick52, players_states):
        return self.play_card(trick_i, leader_i, current_trick52, players_states)
