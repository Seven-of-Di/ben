from copy import deepcopy
from typing import Dict, List
from quart import Quart, request, g
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware

from nn.models import MODELS
from game import AsyncBotBid, AsyncBotLead
from FullBoardPlayer import AsyncFullBoardPlayer,PlayFullBoard
from health_checker import HealthChecker
from alerting import find_alert

from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.context import attach, detach
from tracing import tracing_enabled
import numpy as np

import os
import sentry_sdk

from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

from play_card_pre_process import play_a_card
from human_carding import lead_real_card
from utils import DIRECTIONS, VULNERABILITIES, PlayerHand, BiddingSuit, Diag, Direction,PlayingMode
from claim_dds import check_claim_from_api

import tensorflow.compat.v1 as tf  # type: ignore

tf.disable_v2_behavior()

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN", ""),
    environment=os.environ.get("SENTRY_ENVIRONMENT", ""), 
    release=os.environ.get("SENTRY_RELEASE", ""),
)

app = Quart(__name__)
app.asgi_app = SentryAsgiMiddleware(app.asgi_app)._run_asgi3
app.asgi_app = OpenTelemetryMiddleware(app.asgi_app)

health_checker = HealthChecker()
health_checker.start()

@app.before_request
async def before_request():
    if not tracing_enabled:
        pass

    extracted_context = extract(request.headers)
    span = trace.get_current_span(extracted_context)
    if span is not None:
        trace.use_span(span, end_on_exit=True)
        g.otel_token = attach(trace.set_span_in_context(span))

@app.after_request
async def after_request(response):
    if not tracing_enabled:
        return response

    token = getattr(g, 'otel_token', None)
    if token:
        current_span = trace.get_current_span()
        if current_span:
            current_span.end()

        detach(token)

    return response


class PlaceBid:
    def __init__(self, place_bid_request):
        place_bid_request = dict(place_bid_request)
        self.vuln = VULNERABILITIES[place_bid_request['vuln']]
        self.hand = place_bid_request['hand']
        self.dealer = place_bid_request['dealer']
        self.auction = ['PAD_START'] * \
            DIRECTIONS.index(self.dealer) + place_bid_request['auction']


class AlertBid:
    def __init__(self, alert_bid_request) -> None:
        self.vuln = VULNERABILITIES[alert_bid_request['vuln']]
        self.dealer = alert_bid_request["dealer"]
        self.auction = alert_bid_request['auction']


class PlayCard:
    def __init__(self, play_card_request):
        self.hand = play_card_request['hand']
        self.dummy_hand = play_card_request['dummy_hand']
        self.dealer = play_card_request['dealer']
        self.vuln = VULNERABILITIES[play_card_request['vuln']]
        self.auction = play_card_request['auction']
        self.contract = play_card_request['contract']
        self.contract_direction = play_card_request['contract_direction']
        self.next_player = play_card_request['next_player']
        self.tricks = play_card_request['tricks']
        self.cheating_diag_pbn = play_card_request[
            "cheating_diag_pbn"] if "cheating_diag_pbn" in play_card_request else None
        self.playing_mode = PlayingMode.from_str(play_card_request[
            "playing_mode"]) if "playing_mode" in play_card_request else PlayingMode.MATCHPOINTS


class MakeLead:
    def __init__(self, make_lead_request):
        self.hand = make_lead_request['hand']
        self.dealer = make_lead_request['dealer']

        self.vuln = VULNERABILITIES[make_lead_request['vuln']]
        self.auction = ['PAD_START'] * \
            DIRECTIONS.index(self.dealer) + make_lead_request['auction']


class CheckClaim:
    def __init__(self, check_claim_request) -> None:
        self.claiming_hand = check_claim_request["claiming_hand"]
        self.dummy_hand = check_claim_request["dummy_hand"]
        self.claiming_direction = check_claim_request["claiming_direction"]
        self.contract_direction = check_claim_request["contract_direction"]
        self.contract = check_claim_request["contract"]
        self.tricks = check_claim_request['tricks']
        self.claim = check_claim_request['claim']
        self.real_diag = Diag.init_from_pbn(check_claim_request['real_diag']) if 'real_diag' in check_claim_request else None



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

'''
{
    "dealer": "N",
    "vuln": "None",
    "hands : "N:.J8.A9653.A98752 K9J236.2.28.64JK 85.AT754.KJ74.3Q AQT74.KQ963.QT.T"
}
'''


@app.post('/play_card')
async def play_card():
    try:
        data = await request.get_json()
        req = PlayCard(data)

        if tracing_enabled:
            current_span = trace.get_current_span()
            current_span.set_attributes({
                "game.next_player": req.next_player,
                "game.hand": req.hand,
                "game.dummy_hand": req.dummy_hand,
                "game.contract": req.contract,
                "game.contract_direction": req.contract_direction,
                "game.tricks": ",".join(np.concatenate(req.tricks).tolist()),
            })

        dict_result = await play_a_card(
            req.hand,
            req.dummy_hand,
            req.dealer,
            req.vuln,
            req.auction,
            req.contract,
            req.contract_direction,
            req.next_player,
            req.tricks,
            MODELS,
            req.cheating_diag_pbn,
            req.playing_mode
        )
    except Exception as e:
        app.logger.exception(e)

        return {'error': str(e)}, 500

    """
    dict_result = {
        "card": "H4",
        "claim_the_rest": false
    }
    """

    return dict_result, 200


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

        if tracing_enabled:
            current_span = trace.get_current_span()
            current_span.set_attributes({
                "game.hand": req.hand,
                "game.dealer": req.dealer,
                "game.auction": ",".join(req.auction),
            })

        # 1NT - (P)
        bot = AsyncBotBid(
            req.vuln,
            req.hand,
            MODELS
        )

        bid_resp = await bot.async_bid(req.auction)

        new_auction: List[str] = deepcopy(req.auction)
        new_auction.append(bid_resp.bid)

        alert = await find_alert(new_auction, req.vuln)

        if alert == None:
            bot = AsyncBotBid(
                req.vuln,
                req.hand,
                MODELS,
                human_model=True
            )
            bid_resp = await bot.async_bid(req.auction)

        resp = {'bid': bid_resp.bid}
        if alert != None:
            resp['alert'] = { 'text': alert, 'artificial': False }

        return resp, 200
    except Exception as e:
        app.logger.exception(e)
        return {'error': str(e)}, 500

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

        if tracing_enabled:
            current_span = trace.get_current_span()
            current_span.set_attributes({
                "game.hand": req.hand,
                "game.dealer": req.dealer,
                "game.auction": ",".join(req.auction),
            })

        bot = AsyncBotLead(req.vuln, req.hand, MODELS)

        lead = bot.lead(req.auction)
        card_str = lead.to_dict()['candidates'][0]['card']
        contract = next((bid for bid in reversed(req.auction)
                        if len(bid) == 2 and bid != "XX"), None)
        if contract is None:
            raise Exception("contract is None")

        return {
            'card': lead_real_card(PlayerHand.from_pbn(req.hand), card_str, BiddingSuit.from_str(contract[1])).__str__()
        }, 200
    except Exception as e:
        app.logger.exception(e)

        return {'error': str(e)}, 500

'''
{
    "claiming_hand": "Q8754.2.KT8.QT92",
    "dummy_hand": ".T87543.QJ53.76",
    "claiming_direction": "N",
    "contract": "1N",
    "contract_direction": "S",
    "tricks": [["SA", "SK"]],
    "claim": 12
}
'''


@app.post('/check_claim')
async def check_claim():
    try:
        data = await request.get_json()
        req = CheckClaim(data)
        res = await check_claim_from_api(
            req.claiming_hand,
            req.dummy_hand,
            req.claiming_direction,
            req.contract_direction,
            req.contract,
            req.tricks,
            req.claim,
            real_diag=req.real_diag
            
            )

        return {'claim_accepted': res}, 200
    except Exception as e:
        app.logger.exception(e)

        return {'error': str(e)}, 500

'''
{
    "hand": "N:J962.KA3.87.T983 Q7.QJ965.6.KJA54 KA84.872.TQJA2.6 T53.T4.K9543.Q72",
    "dealer": "E",
    "vuln": "None"
}
'''


@app.post('/play_full_board')
async def play_full_board() -> Dict:
    data = await request.get_json()
    req = PlayFullBoard(data)
    bot = AsyncFullBoardPlayer(
        req.hands,
        req.vuln,
        req.dealer,
        PlayingMode.MATCHPOINTS,
        MODELS
    )
    board_data = await bot.async_full_board()

    return board_data


'''
{
    "dealer": "N",
    "vuln": "None",
    "auction": ["1C", "PASS", "PASS"]
}
'''


@app.post('/alert_bid')
async def alert_bid():
    try:
        data = await request.get_json()
        req = AlertBid(data)
        alert = await find_alert(req.auction, req.vuln)

        return {"alert": alert, "artificial" : False}, 200
    except Exception as e:
        app.logger.exception(e)
        return {'error': 'Unexpected error'},500


@app.get('/healthz')
async def healthz():
    healthy = health_checker.healthy()
    if healthy:
        return 'ok', 200

    return 'unhealthy', 500


def start_dev():
    port = os.environ.get('PORT', '8081')
    debug = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't')
    use_reloader = os.environ.get(
        'USE_RELOADER', 'False').lower() in ('true', '1', 't')

    app.logger.warning("Starting the server")
    app.run(host='0.0.0.0',
            port=int(port),
            debug=debug,
            use_reloader=use_reloader)

    app.logger.warning("Server started")


if __name__ == "__main__":
    start_dev()
