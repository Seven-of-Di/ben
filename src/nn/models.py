import os
import os.path

from configparser import ConfigParser
import nn.player as player

from nn.bidder import Bidder
from nn.bid_info import BidInfo
from nn.leader import Leader
from nn.lead_singledummy import LeadSingleDummy
import conf

BIDDER_MODEL_BASE_PATH = os.path.join(os.path.dirname(os.getcwd()))


class Models:

    def __init__(self, bidder_model, wide_bidder_model,binfo, lead,sd_model, player_models):
        self.bidder_model = bidder_model
        self.wide_bidder_model = wide_bidder_model
        self.binfo = binfo
        self.lead = lead
        self.player_models = player_models
        self.sd_model = sd_model


    
    @classmethod
    def from_conf(cls, conf: ConfigParser) -> "Models":
        return cls(
            bidder_model=Bidder('bidder', os.path.join(BIDDER_MODEL_BASE_PATH, conf['bidding']['bidder'])),
            wide_bidder_model=Bidder('bidder', os.path.join(BIDDER_MODEL_BASE_PATH, conf['bidding']['wide_bidder'])),
            binfo=BidInfo(os.path.join(BIDDER_MODEL_BASE_PATH, conf['bidding']['info'])),
            sd_model=LeadSingleDummy(os.path.join(BIDDER_MODEL_BASE_PATH, conf['eval']['lead_single_dummy'])),
            lead=Leader(os.path.join(BIDDER_MODEL_BASE_PATH, conf['lead']['lead'])),
            player_models=[
                player.BatchPlayerLefty('lefty', os.path.join(BIDDER_MODEL_BASE_PATH, conf['cardplay']['lefty'])),
                player.BatchPlayer('dummy', os.path.join(BIDDER_MODEL_BASE_PATH, conf['cardplay']['dummy'])),
                player.BatchPlayer('righty', os.path.join(BIDDER_MODEL_BASE_PATH, conf['cardplay']['righty'])),
                player.BatchPlayer('decl', os.path.join(BIDDER_MODEL_BASE_PATH, conf['cardplay']['decl']))
            ],
        )



DEFAULT_MODEL_CONF = os.path.join(os.path.dirname(os.getcwd()), 'default.conf')
MODELS = Models.from_conf(conf.load(DEFAULT_MODEL_CONF))