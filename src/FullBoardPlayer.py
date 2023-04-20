from typing import Dict, List
import bots
from utils import Direction, BiddingSuit, Card_, Diag
from PlayRecord import Trick
from bidding import bidding
from play_card_pre_process import play_a_card
from human_carding import lead_real_card


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
            dict_result = await play_a_card(hand_str=self.diag.hands[current_player if current_player != dummy else declarer].to_pbn(), dummy_hand_str=self.diag.hands[dummy].to_pbn(), dealer_str=self.dealer.abbreviation(), vuls=self.vuls, auction=auction, contract_str=contract, declarer_str=declarer.abbreviation(), next_player_str=current_player.abbreviation(), tricks_str=tricks, models=self.models)
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
