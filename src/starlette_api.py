from copy import deepcopy
import logging
import time
from typing import Dict, List
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.requests import Request
from starlette.middleware.base import BaseHTTPMiddleware
from opentelemetry import trace
from starlette_exporter import PrometheusMiddleware, handle_metrics, CollectorRegistry, multiprocess # type: ignore
from prometheus_client import make_asgi_app
import os
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
import sentry_sdk

from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from tracing import tracing_enabled
from opentelemetry.propagate import extract
from opentelemetry.context import attach, detach
from sentry_sdk.integrations.logging import LoggingIntegration

from utils import DIRECTIONS, VULNERABILITIES, PlayerHand, BiddingSuit,PlayingMode
from nn.models import MODELS
from play_card_pre_process import play_a_card
from game import AsyncBotBid, AsyncBotLead
from alerting import find_alert
from human_carding import lead_real_card
from claim_dds import check_claim_from_api
from FullBoardPlayer import AsyncFullBoardPlayer,PlayFullBoard

logging.basicConfig(level=logging.WARNING)

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN", ""),
    environment=os.environ.get("SENTRY_ENVIRONMENT", ""),
    release=os.environ.get("SENTRY_RELEASE", ""),
    integrations= [LoggingIntegration(level=logging.WARNING, event_level=logging.WARNING)],
    max_request_body_size="always"
)


env = os.environ.get("ENVIRONMENT")
if env is None:
    raise Exception("ENVIRONMENT not set")

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

async def play_card(request: Request):
    try:
        data = await request.json()
        req = PlayCard(data)
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
        return JSONResponse(dict_result)
    except Exception as e:
        logging.exception(e)
        return JSONResponse({'error': str(e)}, 500)
    
async def place_bid(request : Request):
    try:
        data = await request.json()
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

        return JSONResponse(resp)
    except Exception as e:
        logging.exception(e)
        return JSONResponse({'error': str(e)}, 500)
    
async def make_lead(request : Request):
    try:
        data = await request.json()
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

        return JSONResponse({
            'card': lead_real_card(PlayerHand.from_pbn(req.hand), card_str, BiddingSuit.from_str(contract[1])).__str__()
        }, 200)
    except Exception as e:
        logging.exception(e)
        return JSONResponse({'error': str(e)}, 500)
    
async def check_claim(request : Request):
    try:
        data = await request.json()
        req = CheckClaim(data)
        res = await check_claim_from_api(
            req.claiming_hand,
            req.dummy_hand,
            req.claiming_direction,
            req.contract_direction,
            req.contract,
            req.tricks,
            req.claim)

        return JSONResponse({'claim_accepted': res}, 200)
    except Exception as e:
        logging.exception(e)
        return JSONResponse({'error': str(e)}, 500)

'''
{
    "hand": "N:J962.KA3.87.T983 Q7.QJ965.6.KJA54 KA84.872.TQJA2.6 T53.T4.K9543.Q72",
    "dealer": "E",
    "vuln": "None"
}
'''


async def play_full_board(request:Request) -> JSONResponse:
    try :
        data = await request.json()
        req = PlayFullBoard(data)
        bot = AsyncFullBoardPlayer(
            req.hands,
            req.vuln,
            req.dealer,
            PlayingMode.MATCHPOINTS,
            MODELS
        )
        board_data = await bot.async_full_board()

        return JSONResponse(board_data)
    except Exception as e:
        logging.exception(e)
        return JSONResponse({'error': str(e)}, 500)


'''
{
    "dealer": "N",
    "vuln": "None",
    "auction": ["1C", "PASS", "PASS"]
}
'''


async def alert_bid(request: Request):
    try:
        data = await request.json()
        req = AlertBid(data)
        alert = await find_alert(req.auction, req.vuln)

        return {"alert": alert, "artificial" : False}, 200
    except Exception as e:
        logging.exception(e)
        return {'error': str(e)},500


# async def healthz():
#     healthy = health_checker.healthy()
#     if healthy:
#         return 'ok', 200

#     return 'unhealthy', 500
    
class TracingHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        otel_token = None
        if tracing_enabled:
            extracted_context = extract(request.headers)
            span = trace.get_current_span(extracted_context)
            if span is not None:
                trace.use_span(span, end_on_exit=True)
                otel_token = attach(trace.set_span_in_context(span))

        response = await call_next(request)

        if not tracing_enabled or not otel_token:
            return response

        current_span = trace.get_current_span()
        if current_span:
            current_span.end()

        detach(otel_token)

        return response

class SlowAnswerMiddleWare(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.time()
        response = await call_next(request)
        process_time = time.time() - start
        if process_time > 3 and call_next.__name__ != "play_full_board":
            # , request: {await request.json()}
            logging.warning("Slow answer",extra= {"time":round(process_time,2)})

        return response



app = Starlette(
    routes=[
        Route('/play_card', play_card, methods=['POST']),
        Route('/place_bid', place_bid, methods=['POST']),
        Route('/make_lead', make_lead, methods=['POST']),
        Route('/check_claim', check_claim, methods=['POST']),
        Route('/play_full_board', play_full_board, methods=['POST']),
        Route('/alert_bid', alert_bid, methods=['POST']),
        # Route('/healthz', healthz, methods=['GET'])
    ],
    middleware=[
        Middleware(OpenTelemetryMiddleware),
        Middleware(PrometheusMiddleware, app_name="ben",labels={"env": env}),
        Middleware(TracingHeaderMiddleware),
        Middleware(SentryAsgiMiddleware),
    ]
)

app.add_route("/metrics", handle_metrics)

# Using multiprocess collector for registry
def make_metrics_app():
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    return make_asgi_app(registry=registry)

metrics_app = make_metrics_app()

app.mount("/metrics", metrics_app)
app = SentryAsgiMiddleware(app)