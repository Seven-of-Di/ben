import sqlite3
from sqlitedict import SqliteDict
import hashlib
from typing import Dict
# import pandas as pd
from alert_utils import BidPosition, BidExplanations
from generate_alerts import generate_alert_from_bid_explanation
import pickle5 as pickle
import numpy as np
import json
from itertools import islice

dict_of_alerts: Dict[BidPosition, BidExplanations] = {}

with open('dev_alerts', 'rb') as f:
    dict_of_alerts = pickle.load(f)

print(dict_of_alerts)

db = SqliteDict("alert_database_1.sqlite", tablename="alerts", autocommit=False)

print(db['53c1cd78ed54af61c90b49c2751784b6'])

CHUNK_SIZE = 50

def chunks(data):
   it = iter(data)
   for _ in range(0, len(data), CHUNK_SIZE):
      yield {k:data[k] for k in islice(it, CHUNK_SIZE)}

for chunk in chunks(dict_of_alerts):
    for bid_position in chunk:
        hex = hashlib.md5(json.dumps(bid_position.to_dict(), sort_keys=True).encode('utf-8')).hexdigest()
        db[hex] = generate_alert_from_bid_explanation(chunk[bid_position])

    db.commit()

# db["Hello"] = "Hello"
# db.commit()

# print(db["Hello"])
# alert_db = sqlite3.connect('dev_alert_database')
# cursor = alert_db.cursor()

# db = SqliteDict("alert_database_1.sqlite")

# alert_db = sqlite3.connect('alert_database_1.sqlite')
# cursor = alert_db.cursor()

# cursor.execute('''
#           CREATE TABLE IF NOT EXISTS alert_table
#           ([sequence] TEXT PRIMARY KEY, [alert] TEXT)
#           ''')


# cursor.executemany("insert into alert_table (sequence,alert) values (?,?)",tuples)

# alert_db.commit()

# cursor.execute('''
#           SELECT *
#           FROM alert_table
#           WHERE sequence = '1D'
#           ''')

# df = pd.DataFrame(cursor.fetchall(), columns=['sequence', 'alert'])
# print(df)
