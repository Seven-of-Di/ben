from sqlitedict import SqliteDict
from alert_utils import BidPosition
import os

db_path = os.environ.get("ALERTS_DB_PATH")
db_file = os.environ.get("ALERTS_DB_FILE")

alerts_db = SqliteDict(filename=os.path.join(db_path, db_file),
                       tablename="alerts",
                       autocommit=False)


def find_alert(req):
    bid_position = BidPosition(req.auction, req.vuln)

    try:
        return alerts_db[bid_position.to_hex()]
    except KeyError:
        return None
