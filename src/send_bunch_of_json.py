import concurrent
from concurrent.futures import ThreadPoolExecutor
import time
import requests
import json

def send_request(data,type_of_action):
    start = time.time()
    port = "http://localhost:8081"
    res = requests.post('{}/{}'.format(port, type_of_action), json=data)
    print(time.time()-start)
    return res.json()

json_data = [{
  "hand": "KT7.9.KT643.875",
  "dummy_hand": ".AJ754.A52.AQ94",
  "dealer": "S",
  "vuln": "E-W",
  "contract": "3NS",
  "contract_direction": "S",
  "auction": [
    "PASS",
    "PASS",
    "1H",
    "PASS",
    "1S",
    "PASS",
    "2C",
    "PASS",
    "2H",
    "PASS",
    "3H",
    "PASS",
    "3N",
    "PASS",
    "PASS",
    "PASS"
  ],
  "next_player": "W",
  "tricks": [
    [
      "SJ",
      "S3",
      "S2",
      "S4"
    ]
  ]
},{
    "hand": "QJ3.542.KJT7.AQ2",
    "dealer": "N",
    "vuln": "None",
    "auction": ["1C", "PASS", "PASS"]
},
{
    "hand": "QJ3.542.KJT7.AQ2",
    "dealer": "N",
    "vuln": "None",
    "auction": ["1C", "PASS", "PASS", "PASS"]
}
]

type_of_action_tab = ["play_card","place_bid","make_lead"]

with ThreadPoolExecutor(max_workers=20) as executor:
    future_to_url = {executor.submit(send_request, json_data[i%len(type_of_action_tab)],type_of_action_tab[i%len(type_of_action_tab)]) for i in range(20)}
    for future in concurrent.futures.as_completed(future_to_url):
        try:
            data = future.result()
            print(data)
        except Exception as e:
            print('Looks like something went wrong:', e)