import os
import os.path

from configparser import ConfigParser
import nn.player as player

from nn.bidder import Bidder
from nn.player import BatchPlayer, BatchPlayerLefty
from nn.bid_info import BidInfo
from nn.leader import Leader
from nn.lead_singledummy import LeadSingleDummy
import conf

BIDDER_MODEL_BASE_PATH = os.path.join(os.path.dirname(os.getcwd()))


class Models:

    def __init__(self, bidder_model, wide_bidder_model,binfo, lead_suit_model, lead_nt_model,sd_model, player_models):
        self.bidder_model = bidder_model
        self.wide_bidder_model = wide_bidder_model
        self.binfo = binfo
        self.lead_suit_model = lead_suit_model
        self.lead_nt_model = lead_nt_model
        self.player_models = player_models
        self.sd_model = sd_model


    
    @classmethod
    def from_conf(cls, conf: ConfigParser,base_path=None) -> "Models":
        if base_path is None:
            base_path = os.getenv('BEN_HOME') or '..'
        include_opening_lead = False
        player_names = ['lefty_nt', 'dummy_nt', 'righty_nt', 'decl_nt', 'lefty_suit', 'dummy_suit', 'righty_suit', 'decl_suit']
        return cls(
            bidder_model=Bidder('bidder', os.path.join(BIDDER_MODEL_BASE_PATH, conf['bidding']['bidder'])),
            wide_bidder_model=Bidder('bidder', os.path.join(BIDDER_MODEL_BASE_PATH, conf['bidding']['wide_bidder'])),
            binfo=BidInfo(os.path.join(BIDDER_MODEL_BASE_PATH, conf['bidding']['info'])),
            sd_model=LeadSingleDummy(os.path.join(BIDDER_MODEL_BASE_PATH, conf['eval']['lead_single_dummy'])),
            lead_suit_model=Leader(os.path.join(BIDDER_MODEL_BASE_PATH, conf['lead']['lead_suit'])),
            lead_nt_model=Leader(os.path.join(BIDDER_MODEL_BASE_PATH, conf['lead']['lead_nt'])),
            player_models = [
                BatchPlayerLefty(name, os.path.join(BIDDER_MODEL_BASE_PATH, conf['cardplay'][name])) if 'lefty' in name and include_opening_lead == False else
                BatchPlayer(name, os.path.join(BIDDER_MODEL_BASE_PATH, conf['cardplay'][name]))
                for name in player_names
            ],
        )



DEFAULT_MODEL_CONF = os.path.join(os.path.dirname(os.getcwd()), 'default.conf')
MODELS = Models.from_conf(conf.load(DEFAULT_MODEL_CONF))