import os
from sqlitedict import SqliteDict
import hashlib
from typing import Dict
from alert_utils import BidPosition, BidExplanations
from generate_alerts import generate_alert_from_bid_explanation
import pickle5 as pickle
import numpy as np
import json
from itertools import islice

dict_of_alerts: Dict[BidPosition, BidExplanations] = {}
build_directory = os.path.join(os.path.dirname(os.getcwd()), 'build')

with open(os.path.join(build_directory, 'dev_alerts'), 'rb') as f:
    dict_of_alerts = pickle.load(f)

db = SqliteDict(filename=os.path.join(build_directory, "alert_database_1.sqlite"),
                tablename="alerts",
                autocommit=False)

CHUNK_SIZE = 50

def chunks(data):
   it = iter(data)
   for _ in range(0, len(data), CHUNK_SIZE):
      yield {k:data[k] for k in islice(it, CHUNK_SIZE)}

for chunk in chunks(dict_of_alerts):
    for bid_position in chunk:
        alert = generate_alert_from_bid_explanation(chunk[bid_position])

        if alert != None:
            db[bid_position.to_hex()] = alert

    db.commit()

# cursor = alert_db.cursor()

# db = SqliteDict("alert_database_1.sqlite")

# alert_db = sqlite3.connect('alert_database_1.sqlite')
# cursor = alert_db.cursor()

# cursor.execute('''
#           CREATE TABLE IF NOT EXISTS alert_table
#           ([sequence] TEXT PRIMARY KEY, [alert] TEXT)
#           ''')


# cursor.executemany("INSERT INTO ALERT_TABLE (sequence,alert) VALUES (?,?)", tuples)

# alert_db.commit()

# cursor.execute('''
#           SELECT *
#           FROM alert_table
#           WHERE sequence = '1D'
#           ''')

# df = pd.DataFrame(cursor.fetchall(), columns=['sequence', 'alert'])
# print(df)
