from sqlitedict import SqliteDict
from alert_utils import BidPosition
import os

build_directory = os.path.join(os.path.dirname(os.getcwd()), 'build')
alerts_db = SqliteDict(filename=os.path.join(build_directory, "alert_database_1.sqlite"),
                tablename="alerts",
                autocommit=False)

def find_alert(req):
    bid_position = BidPosition(req.auction, req.vuln)

    try:
        return alerts_db[bid_position.to_hex()]
    except KeyError:
        return None
