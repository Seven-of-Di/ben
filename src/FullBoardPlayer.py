import json
import os
from typing import Dict, List
import bots
from utils import Direction, BiddingSuit, Card_, Diag,VULNERABILITIES
from PlayRecord import Trick
from bidding import bidding
from play_card_pre_process import play_a_card
from human_carding import lead_real_card
from nn.models import MODELS
import boto3

class PlayFullBoard:
    def __init__(self, play_full_board_request) -> None:
        self.vuln = VULNERABILITIES[play_full_board_request['vuln']]
        self.dealer = Direction.from_str(play_full_board_request['dealer'])
        self.hands = Diag.init_from_pbn(play_full_board_request['hands'])

class FullBoardPlayer():
    def __init__(self, diag: Diag, vuls: List[bool], dealer: Direction, models) -> None:
        diag.is_valid()
        self.diag = diag
        self.vuls = vuls
        self.dealer = dealer
        self.models = models

    def get_auction(self):
        auction: List[str] = ["PAD_START"] * \
            Direction.from_str(self.dealer.abbreviation()).value
        bidder_bots: List[bots.BotBid] = [bots.BotBid(
            self.vuls, self.diag.hands[dir].to_pbn(), self.models) for dir in Direction]
        while not bidding.auction_over(auction):
            current_direction: Direction = Direction(len(auction) % 4)
            auction.append(
                bidder_bots[current_direction.value].bid(auction).bid)
            pass
        return [bid for bid in auction if bid != "PAD_START"]

    async def get_card_play(self, auction):
        padded_auction = [
            "PAD_START"] * Direction.from_str(self.dealer.abbreviation()).value + auction

        contract = bidding.get_contract(padded_auction)
        if contract is None:
            return
        trump = BiddingSuit.from_str(contract[1])
        declarer = Direction.from_str(contract[-1])
        dummy = declarer.offset(2)
        leader = declarer.offset(1)
        raw_lead = bots.BotLead(self.vuls, self.diag.hands[leader].to_pbn(
        ), self.models).lead(auction).to_dict()['candidates'][0]['card']
        lead = lead_real_card(
            self.diag.hands[leader], raw_lead, BiddingSuit.from_str(contract[1]))
        self.diag.hands[leader].remove(lead)

        tricks = [[str(lead)]]
        current_player = leader.offset(1)

        # 12 first tricks
        for _ in range(47):
            dict_result = await play_a_card(hand_str=self.diag.hands[current_player if current_player != dummy else declarer].to_pbn(), dummy_hand_str=self.diag.hands[dummy].to_pbn(), dealer_str=self.dealer.abbreviation(), vuls=self.vuls, auction=auction, contract=contract, declarer_str=declarer.abbreviation(), next_player_str=current_player.abbreviation(), tricks_str=tricks, MODELS=self.models, cheating_diag_pbn=self.diag.print_as_pbn())
            # print(dict_result)
            tricks[-1].append(str(dict_result["card"]))
            self.diag.hands[current_player].remove(
                Card_.from_str(dict_result["card"]))
            current_player = current_player.next()
            if len(tricks[-1]) == 4:
                last_trick = Trick.from_list(leader=leader, trick_as_list=[
                                             Card_.from_str(card) for card in tricks[-1]])
                current_player = last_trick.winner(trump=trump)
                leader = current_player
                tricks.append([])

        assert all([self.diag.hands[dir].len() == 1 for dir in Direction])
        # Last trick
        for _ in range(4):
            card = self.diag.hands[current_player].cards[0]
            tricks[-1].append(str(card))
            current_player = current_player.next()

        return tricks


class AsyncFullBoardPlayer(FullBoardPlayer):
    async def async_full_board(self) -> Dict:
        auction = self.get_auction()
        if auction == ["PASS"]*4:
            return {'auction': auction, "play": []}
        play = await self.get_card_play(auction)
        return {'auction': auction, "play": play}


def run():
    sqs = boto3.resource('sqs')

    request_queue_name = os.environ.get('ROBOT_PLAYFULLBOARD_QUEUE_URL')
    response_queue_name = os.environ.get('ROBOT_FULLBOARDPLAYED_QUEUE_URL')

    request_queue = sqs.get_queue_by_name(QueueName=request_queue_name)
    response_queue = sqs.get_queue_by_name(QueueName=response_queue_name)

    while True:
        for message in request_queue.receive_messages(WaitTimeSeconds=10):
            req = PlayFullBoard(json.loads(message.body))
            bot = FullBoardPlayer(
            req.hands,
            req.vuln,
            req.dealer,
            MODELS
        )
            print(f"Message from queue {message.body}")
            print("Board ID : {}".format(message["MessageAttributes"]["BoardID"]))
            board_id = message["MessageAttributes"]["BoardID"]
            auction = bot.get_auction()
            if auction == ["PASS"]*4:
                response_queue.send_message(
                    MessageAttributes={'BoardID': board_id},
                    MessageBody={'auction': auction, "play": []})
            else :
                play = bot.get_card_play(auction)
                response_queue.send_message(
                    MessageAttributes={'BoardID': board_id},
                    MessageBody={'auction': auction, "play": play})
            
            # Mark the message as processed via deleating
            message.delete()

if __name__ == '__main__':
    run()
