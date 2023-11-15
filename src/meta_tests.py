from __future__ import annotations
from typing import List

from tests import run_tm_btwn_ben_versions
import glob
import os


def replay_last_match(specific_boards: List[int] | None = None):
    list_of_files = glob.glob(
        "./test_data/*.pbn"
    )  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getctime)
    print(latest_file)

    run_tm_btwn_ben_versions(
        force_same_sequence=False,
        force_same_lead=True,
        force_same_card_play=True,
        file=latest_file,
        specific_boards=specific_boards,
    )


if __name__ == "__main__":
    # replay_last_match(specific_boards = [46])
    replay_last_match()
