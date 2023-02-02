from quart import Quart, request

from nn.models import Models
from game import AsyncBotBid, AsyncBotLead
import os
import conf
from transform_play_card import get_ben_card_play_answer, lead_real_card
from utils import DIRECTIONS, VULNERABILITIES, PlayerHand, BiddingSuit
from PlayRecord import PlayRecord, Direction
from claim_dds import check_claim_from_api

import tensorflow.compat.v1 as tf

tf.disable_v2_behavior()

app = Quart(__name__)

MODELS = Models.from_conf(conf.load("../default.conf"))


class PlaceBid:
    def __init__(self, place_bid_request):
        self.vuln = VULNERABILITIES[place_bid_request['vuln']]
        self.hand = place_bid_request['hand']
        self.dealer = place_bid_request['dealer']
        self.auction = ['PAD_START'] * \
            DIRECTIONS.index(self.dealer) + place_bid_request['auction']


class PlayCard:
    def __init__(self, play_card_request):
        self.hand = play_card_request['hand']
        self.dummy_hand = play_card_request['dummy_hand']
        self.dealer = play_card_request['dealer']
        self.vuln = play_card_request['vuln']
        self.auction = play_card_request['auction']
        self.contract = play_card_request['contract']
        self.contract_direction = play_card_request['contract_direction']
        self.next_player = play_card_request['next_player']
        self.tricks = play_card_request['tricks']


class MakeLead:
    def __init__(self, make_lead_request):
        self.hand = make_lead_request['hand']
        self.dealer = make_lead_request['dealer']

        self.vuln = VULNERABILITIES[make_lead_request['vuln']]
        self.auction = ['PAD_START'] * \
            DIRECTIONS.index(self.dealer) + make_lead_request['auction']

class CheckClaim:
    def __init__(self, check_claim_request) -> None:
        self.claiming_hand = check_claim_request["hand"]
        self.dummy_hand = check_claim_request["dummy_hand"]
        self.claiming_direction = check_claim_request["claiming_direction"]
        self.declarer = check_claim_request["declarer"]
        self.contract = check_claim_request["contract"]
        self.tricks = check_claim_request['tricks']
        self.claim = check_claim_request['claim']

'''
{
    "hand": "Q8754.2.KT8.QT92",
    "dummy_hand": ".T87543.QJ53.76",
    "dealer": "N",
    "vuln": "None",
    "auction": ["1H", "PASS", "1N", "PASS", "PASS", "PASS"],
    "contract": "1N",
    "contract_direction": "S",
    "next_player": "E",
    "tricks": [["SA", "SK"]]
}
'''


@app.route('/play_card', methods=['POST'])
async def play_card():
    try:
        data = await request.get_json()
        # app.logger.warn(data)
        req = PlayCard(data)

        card_to_play = await get_ben_card_play_answer(
            req.hand,
            req.dummy_hand,
            req.dealer,
            req.vuln,
            req.auction,
            req.contract,
            req.contract_direction,
            req.next_player,
            req.tricks,
            MODELS
        )

        return {'card': card_to_play}
    except Exception as e:
        app.logger.exception(e)
        return {'error': 'Unexpected error'}


'''
{
    "hand": "QJ3.542.KJT7.AQ2",
    "dealer": "N",
    "vuln": "None",
    "auction": ["1C", "PASS", "PASS"]
}
'''
@app.post('/place_bid')
async def place_bid():
    try:
        data = await request.get_json()
        req = PlaceBid(data)

        bot = AsyncBotBid(
            req.vuln,
            req.hand,
            MODELS
        )

        bid_resp = await bot.async_bid(req.auction)

        return {'bid': bid_resp.bid}
    except Exception as e:
        app.logger.exception(e)
        return {'error': 'Unexpected error'}

'''
{
    "hand": "QJ3.542.KJT7.AQ2",
    "dealer": "N",
    "vuln": "None",
    "auction": ["1C", "PASS", "PASS", "PASS"]
}
'''
@app.post('/make_lead')
async def make_lead():
    try:
        data = await request.get_json()
        req = MakeLead(data)

        bot = AsyncBotLead(req.vuln, req.hand, MODELS)

        lead = bot.lead(req.auction)
        card_str = lead.to_dict()['candidates'][0]['card']
        contract = next((bid for bid in reversed(req.auction) if len(bid)==2 and bid!="XX"),None)
        if contract is None :
            raise Exception("contract is None")
        return {'card': lead_real_card(PlayerHand.from_pbn(req.hand),card_str,BiddingSuit.from_str(contract[1])).__str__()}
    except Exception as e:
        app.logger.exception(e)
        return {'error': 'Unexpected error'}


@app.get('/healthz')
async def healthz():
    return {'status': 'ok'}

port = os.environ.get('PORT', '8081')
debug = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't')
use_reloader = os.environ.get('USE_RELOADER', 'False').lower() in ('true', '1', 't')

@app.post('/check_claim')
async def check_claim() :
    try:
        data = await request.get_json()
        req = CheckClaim(data)
        res = await check_claim_from_api(req.claiming_hand,req.dummy_hand,req.claiming_direction,req.declarer,req.contract,req.tricks,req.claim)
        return {'claim_accepted': res}
    except Exception as e:
        app.logger.exception(e)
        return {'error': 'Unexpected error'}

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=debug, use_reloader=use_reloader)

