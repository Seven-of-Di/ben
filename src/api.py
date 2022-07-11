from multiprocessing.sharedctypes import Value
from gevent import monkey
monkey.patch_all()

import bottle
from bottle import post, request, response

from game import AsyncBotBid, AsyncCardPlayer

import shelve
import json

app = Bottle()

DB_NAME = 'gamedb'

@post('/play_card')
def play_card():
  '''Handles play card'''
  
  data = request.json()

  deal = data['deal']
  bot = AsyncBotBid(vuln, hands_str[i], self.models)


@post('/place_bid')
def place_bid():
  '''Handles place bid'''
  pass

bottle.run(app, host='0.0.0.0', port=8081, server='gevent')
