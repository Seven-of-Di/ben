from aioflask import Flask, request

from nn.models import Models
from game import AsyncBotBid
import binary
import conf
import sample

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

class PlayCard:
  def __init__(self, play_card_request):
    self.direction = play_card_request["direction"]
    self.hand = play_card_request["hand"]
    self.hand_52 = binary.parse_hand_f(52)(self.hand)
    self.dummy_hand = play_card_request["dummy_hand"]
    self.contract = play_card_request["contract"]
    self.contract_direction = play_card_request["contract_direction"]
    self.next_player = play_card_request["next_player"]
    self.dealer = play_card_request["dealer"]
    self.vuln = VULNERABILITIES[play_card_request.vuln]
    self.tricks = play_card_request["tricks"]

  def player_index(self):
    decl_index = DIRECTIONS.index(self.contract_direction)
    ordered_directions = DIRECTIONS[decl_index:] + DIRECTIONS[:decl_index]

    return ordered_directions.index(self.next_player) - 1
    

  def rollout_states(self):
    sample.init_rollout_states(
      len(self.tricks),
      player_i, card_players, player_cards_played, shown_out_suits, current_trick, 200, self.padded_auction, card_players[player_i].hand.reshape((-1, 32)), self.vuln, self.models)

# def build_shown_out_suit():

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
  "current_trick_leader": "N",
  "next_player": "E",
  "tricks": [
    ["C2", "C3", "C4", "C5"],
    ["HA"]
  ]
}
'''
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

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8081, debug=True, use_reloader=True)
