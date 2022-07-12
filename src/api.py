from quart import Quart, request, jsonify

from nn.models import Models
from game import AsyncBotBid
import bots
import conf

app = Quart(__name__)

DEALERS = 'NESW'
VULNERABILITIES = {
    'None': [False, False],
    'N-S': [True, False],
    'E-W': [False, True],
    'Both': [True, True]
}

MODELS = Models.from_conf(conf.load("../default.conf"))


class PlaceBidRequest:
  def __init__(self, data):
    self.vuln = VULNERABILITIES[data['vuln']]
    self.hand = data['hand']
    self.dealer = data['dealer']
    self.next = data['next']
    
    auction = ['PAD_START'] * DEALERS.index(self.dealer) + data['auction']
    self.auction = auction

@app.route('/play_card', methods=['POST'])
async def play_card():
  pass

'''
{
  "hand": "QJ3J.542.KJT7.AQ2",
  "dealer": "E",
  "next: "N",
  "vuln": "None",
  "auction": [
    "1C",
    "PASS",
    "PASS"
  ]
}
'''
@app.route('/place_bid', methods=['POST'])
async def place_bid():
  try:
    json_data = await request.get_json()
    app.logger.info(json_data)
    parsed_request = PlaceBidRequest(json_data)
    bot = bots.BotBid(
      [False, False],
      "QJ3J.542.KJT7.AQ2",
      Models.from_conf(conf.load("../default.conf"))
    )

    bid_resp = bot.bid(['PAD_START', '1C', 'PASS', 'PASS'])

    return jsonify(bid_resp), 200
  except Exception as e:
    app.logger.exception(e)
    return jsonify({'error': 'Unexpected error'}), 500

@app.route('/healthz', methods=['GET'])
async def healthz():
  return 'OK', 200

app.run(host='0.0.0.0', port=8081, debug=True)
