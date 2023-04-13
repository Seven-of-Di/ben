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
    "hand": "Q8754.2.KT8.QT92",
    "dummy_hand": ".T87543.QJ53.76",
    "dealer": "N",
    "vuln": "None",
    "auction": ["1H", "PASS", "1N", "PASS", "PASS", "PASS"],
    "contract": "1N",
    "contract_direction": "S",
    "next_player": "E",
    "tricks": [["SA", "SK"]]
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

with ThreadPoolExecutor(max_workers=30) as executor:
    future_to_url = {executor.submit(send_request, json_data[i%3],type_of_action_tab[i%3]) for i in range(30)}
    for future in concurrent.futures.as_completed(future_to_url):
        try:
            data = future.result()
            print(data)
        except Exception as e:
            print('Looks like something went wrong:', e)