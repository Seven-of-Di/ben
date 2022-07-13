from flask import Flask, request

from nn.models import Models
from game import AsyncBotBid
import conf

app = Flask(__name__)

DIRECTIONS = 'NESW'
VULNERABILITIES = {
    'None': [False, False],
    'N-S': [True, False],
    'E-W': [False, True],
    'Both': [True, True]
}

MODELS = Models.from_conf(conf.load("../default.conf"))

class PlaceBid:
  def __init__(self, place_bid_request):
    self.vuln = VULNERABILITIES[place_bid_request.vuln]
    self.hand = place_bid_request.hand
    self.dealer = place_bid_request.dealer
    self.auction = ['PAD_START'] * DIRECTIONS.index(self.dealer) + place_bid_request.auction

@app.route('/play_card', methods=["POST"])
async def play_card():
  pass

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
    bot = AsyncBotBid(
      [False, False],
      "QJ3J.542.KJT7.AQ2",
      Models.from_conf(conf.load("../default.conf"))
    )

    bid_resp = await bot.async_bid(['PAD_START', '1C', 'PASS', 'PASS'])

    return vars(bid_resp)
  except Exception as e:
    app.logger.exception(e)
    return {'error': 'Unexpected error'}

@app.route('/healthz', methods=["GET"])
async def healthz():
  return {'status': 'ok'}

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8081, use_reloader=True)
