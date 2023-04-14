import concurrent
from concurrent.futures import ThreadPoolExecutor
import time
import requests
import json

class PlayCardTest:
    def __init__(self, threads, count, url) -> None:
        self.threads = threads
        self.count = count
        self.url = url

    def execute(self):
        completion_times = []

        with ThreadPoolExecutor(max_workers=self.threads) as executor:
          futures = [executor.submit(send_request, self.url, json_data) for i in range(self.count)]
          print(len(futures))

          for future in concurrent.futures.as_completed(futures):
            data = future.result()
            completion_times.append(data)

          executor.shutdown()

        average_request_time = round(sum(completion_times) / len(completion_times), 2)

        print('Took {} seconds in average per request to complete'.format(average_request_time))


def send_request(url, json_data) -> float:
    start = time.time()
    res = requests.post('{}/play_card'.format(url), json=json_data)

    return time.time()-start

json_data = {
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
}
