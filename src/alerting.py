from sqlitedict import SqliteDict
from alert_utils import BidPosition
import os

db_file = os.environ.get("ALERTS_DB_FILE")

alerts_db = SqliteDict(filename=db_file,
                       tablename="alerts",
                       autocommit=False)


async def find_alert(auction, vuln):
    bid_position = BidPosition(auction, vuln)

    try:
        return alerts_db[bid_position.to_hex()]
    except KeyError:
        return None
