from aioflask import Flask, request

from nn.models import Models
from game import AsyncBotBid
import os
import conf
import transform_play_card
from utils import DIRECTIONS,VULNERABILITIES

app = Flask(__name__)

MODELS = Models.from_conf(conf.load("../default.conf"))

class PlaceBid:
  def __init__(self, place_bid_request):
    self.vuln = VULNERABILITIES[place_bid_request.vuln]
    self.hand = place_bid_request.hand
    self.dealer = place_bid_request.dealer
    self.auction = ['PAD_START'] * DIRECTIONS.index(self.dealer) + place_bid_request.auction

class PlayCard:
  def __init__(self, play_card_request):
    self.hand = play_card_request["hand"]
    self.dummy_hand = play_card_request["dummy_hand"]
    self.dealer = play_card_request["dealer"]
    self.vuln = play_card_request["vuln"]
    self.auction = play_card_request["auction"]
    self.contract = play_card_request["contract"]
    self.contract_direction = play_card_request["contract_direction"]
    self.next_player = play_card_request["next_player"]
    self.tricks = play_card_request["tricks"]

'''
{
  "hand": "QJ3.542.KJT7.AQ2",
  "dummy_hand": "AK2.KQT.AQ52.KJ3",
  "dealer": "E",
  "vuln": "None",
  "auction": [
    "1C",
    "PASS",
    "PASS",
    "PASS"
  ],
  "contract": "2C",
  "contract_direction: "N",
  "next_player": "E",
  "tricks": [
    ["C2", "C3", "C4", "C5"],
    ["HA"]
  ]
}
'''
@app.route('/play_card', methods=["POST"])
async def play_card():
  app.logger.info(request.get_json())
  req = PlayCard(request.get_json())

  card_to_play = transform_play_card(
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


'''
{
  "hand": "QJ3.542.KJT7.AQ2",
  "dealer": "E",
  "vuln": "None",
  "auction": [
    "1C",
    "PASS",
    "PASS"
  ]
}
'''
@app.route('/place_bid', methods=["POST"])
async def place_bid():
  try:
    app.logger.info(request.get_json())
    req = PlaceBid(request.get_json())
    bot = AsyncBotBid(
      req.vuln,
      req.hand,
      MODELS
    )

    bid_resp = await bot.async_bid(req.auction)

    return bid_resp.to_dict()
  except Exception as e:
    app.logger.exception(e)
    return {'error': 'Unexpected error'}

@app.route('/healthz', methods=["GET"])
async def healthz():
  return {'status': 'ok'}

port = os.environ.get('PORT', '8081')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=True)
