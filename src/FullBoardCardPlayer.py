import asyncio
import json
import os
from typing import Dict, List
import bots
from utils import Direction, BiddingSuit, Card_, Diag, VULNERABILITIES, DIRECTIONS
from PlayRecord import Trick
from FullBoardPlayer import FullBoardPlayer
from bidding import bidding
from play_card_pre_process import play_a_card
from human_carding import lead_real_card
from nn.models import MODELS
import boto3

import tensorflow.compat.v1 as tf  # type: ignore

tf.disable_v2_behavior()


class PlayFullCardPlay:
    def __init__(self, play_full_board_request) -> None:
        self.vuln = VULNERABILITIES[play_full_board_request["vuln"]]
        self.dealer = Direction.from_str(play_full_board_request["dealer"])
        self.hands = Diag.init_from_pbn(play_full_board_request["hands"])
        self.auction = play_full_board_request["auction"]


async def start():
    sqs_client = boto3.client(
        "sqs", endpoint_url=os.environ.get("AWS_ENDPOINT", None))

    request_queue_url = os.environ.get("ROBOT_CARDPLAYFULLBOARD_QUEUE_URL")
    response_queue_url = os.environ.get("ROBOT_FULLBOARDPLAYED_QUEUE_URL")

    while True:
        resp = sqs_client.receive_message(
            QueueUrl=request_queue_url,
            MessageAttributeNames=["BoardID"],
            WaitTimeSeconds=10,
        )

        # If nothing is returned the key Messages not exists
        if not "Messages" in resp:
            continue

        for message in resp["Messages"]:
            req = PlayFullCardPlay(json.loads(message["Body"]))
            bot = FullBoardPlayer(req.hands, req.vuln, req.dealer, MODELS)

            play = await bot.get_card_play(req.auction)
            message_body = {"auction": req.auction, "play": play}

            sqs_client.send_message(
                QueueUrl=response_queue_url,
                MessageAttributes={
                    "BoardID": message["MessageAttributes"]["BoardID"]},
                MessageBody=json.dumps(message_body),
            )

            # Mark the message as processed via deleating
            sqs_client.delete_message(
                QueueUrl=request_queue_url,
                ReceiptHandle=message["ReceiptHandle"],
            )


if __name__ == "__main__":
    asyncio.run(start())
