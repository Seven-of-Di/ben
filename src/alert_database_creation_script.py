import sqlite3
from typing import Dict
import pandas as pd
from alert_utils import BidPosition, BidExplanations
from generate_alerts import generate_alert_from_bid_explanation
import pickle

dict_of_alerts: Dict[BidPosition, BidExplanations] = {}

with open('dev_alerts', 'rb') as f:
    dict_of_alerts = pickle.load(f)

tuples = [("".join([str(bid) for bid in k.sequence]),generate_alert_from_bid_explanation(v)["text"]) for k,v in list(dict_of_alerts.items()) if v.n_samples>=5]
print(tuples[2])
print(len(tuples))

alert_db = sqlite3.connect('dev_alert_database')
cursor = alert_db.cursor()

cursor.execute('''
          CREATE TABLE IF NOT EXISTS alert_table
          ([sequence] TEXT PRIMARY KEY, [alert] TEXT)
          ''')


cursor.executemany("insert into alert_table (sequence,alert) values (?,?)",tuples)

alert_db.commit()

cursor.execute('''
          SELECT *
          FROM alert_table
          WHERE sequence = '1D'
          ''')

df = pd.DataFrame(cursor.fetchall(), columns=['sequence', 'alert'])
print(df)
