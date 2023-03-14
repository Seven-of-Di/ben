from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from utils import Direction
import re

from utils import Card_, Rank, Suit


class Pbn:
    @staticmethod
    def get_tag_content(string: str, tag: str) -> str:
        tag = "["+tag+" "
        tag_pos = string.find(tag)
        if tag_pos == -1:
            return ""
        end_of_content = string[tag_pos:].find("]")
        return string[tag_pos:end_of_content+tag_pos].split('"')[1]

    @staticmethod
    def get_score(string: str) -> Optional[int]:
        score_txt = Pbn.get_tag_content(string, "Score")
        if score_txt=='' :
            return None
        score = int(score_txt.split()[1])
        if score_txt.split()[0] == "EW":
            return -score
        return score

    @staticmethod
    def get_all_alerts(string: str) -> List[str]:
        list = []
        for alert in re.finditer("[Note ", string):
            list.append((Pbn.get_tag_content(
                string[alert.start():], "Note")).split(":")[1])
        return list

    @staticmethod
    def get_content_under_tag(string: str, tag : str) -> Optional[str]:
        auction_tag = string.find(f"[{tag} ")
        if auction_tag==-1 :
            return None
        string = string[auction_tag+1:]
        start = string.find("\n")
        end = min(i for i in [string.find(
            "["), string.find("*"), string.find("\n\n")] if i > 0)
        return string[start+1:end-1]

    @staticmethod
    def vul_from_string(string: str) -> Tuple[bool, bool]:
        """Return NS and EW vul from string : NS-> (True,False) """
        if string == "None":
            return (False, False)
        if string == "NS":
            return (True, False)
        if string == "EW":
            return (False, True)
        if string == "All":
            return (True, True)
        raise Exception("Vulnérabilité incorrecte")

    @staticmethod
    def vul_to_string(ns_vulnerable: bool, ew_vulnerable: bool) -> str:
        """Return NS and EW vul from string : NS-> (True,False) """
        if ns_vulnerable and ew_vulnerable:
            return "All"
        if ns_vulnerable:
            return "NS"
        if ew_vulnerable:
            return "EW"
        return "None"

    @staticmethod
    def direction_to_tag(dir: Direction) -> str:
        return dir.name.title()

    @staticmethod
    def print_tag(tag: str, content: str):
        return '[{} \"{}\"]\n'.format(tag,content)


class Lin:
    @staticmethod
    def get_tag_content(string: str, tag: str) -> str:
        tag = "|"+tag+"|"
        tag_pos = string.find(tag)+len(tag)
        end_of_content = string[tag_pos:].find("|")
        return string[tag_pos:end_of_content+tag_pos]

    @staticmethod
    def vul_from_string(string: str) -> Tuple[bool, bool]:
        if string == "o":
            return (False, False)
        if string == "n":
            return (True, False)
        if string == "e":
            return (False, True)
        if string == "b":
            return (True, True)
        raise Exception("Vulnérabilité incorrecte")

    @staticmethod
    def vul_to_string(ns_vulnerable: bool, ew_vulnerable: bool) -> str:
        """Return NS and EW vul from string : NS-> (True,False) """
        if ns_vulnerable and ew_vulnerable:
            return "b"
        if ns_vulnerable:
            return "n"
        if ew_vulnerable:
            return "e"
        return "o"

    @staticmethod
    def dealer_from_string(string: str) -> Direction:
        LIN_TO_PBN_DEALER = {"1": "S", "2": "W", "3": "N", "4": "E"}
        return Direction.from_str(LIN_TO_PBN_DEALER[string])

    @staticmethod
    def dealer_to_string(dir: Direction) -> str:
        LIN_TO_PBN_DEALER = {Direction.SOUTH: "1", Direction.WEST: "2",
                             Direction.NORTH: "3", Direction.EAST: "4"}
        return LIN_TO_PBN_DEALER[dir]


class FFB_PDF:
    @staticmethod
    # return cursor and hand
    def get_hand(pdftext: str, begining: int = 0) -> Tuple[List[Card_], int]:
        symbole_pique = pdftext.find('♠', begining)
        symbole_coeur = pdftext.find('♥', begining)
        symbole_carreau = pdftext.find('♦', begining)
        symbole_trèfle = pdftext.find('♣', begining)
        fin_de_la_main = pdftext.find('\n', symbole_trèfle)

        pique = [Card_(Suit.SPADES, Rank.from_str(card_str))
                 for card_str in FFB_PDF.angliciser(pdftext[symbole_pique+2:symbole_coeur])]
        coeur = [Card_(Suit.HEARTS, Rank.from_str(card_str))
                 for card_str in FFB_PDF.angliciser(pdftext[symbole_coeur+2:symbole_carreau])]
        carreau = [Card_(Suit.DIAMONDS, Rank.from_str(card_str)) for card_str in FFB_PDF.angliciser(
            pdftext[symbole_carreau+2:symbole_trèfle])]
        trèfle = [Card_(Suit.CLUBS, Rank.from_str(card_str))
                  for card_str in FFB_PDF.angliciser(pdftext[symbole_trèfle+2:fin_de_la_main])]
        return pique+coeur+carreau+trèfle, fin_de_la_main

    @staticmethod
    def get_hands(pdftext: str) -> Dict[Direction, List[Card_]]:
        cursor = 0
        dict: Dict[Direction, List[Card_]] = {}
        dict[Direction.WEST], cursor = FFB_PDF.get_hand(pdftext, cursor)
        dict[Direction.EAST], cursor = FFB_PDF.get_hand(pdftext, cursor)
        dict[Direction.NORTH], cursor = FFB_PDF.get_hand(pdftext, cursor)
        dict[Direction.SOUTH], cursor = FFB_PDF.get_hand(pdftext, cursor)

        return dict

    @staticmethod
    def angliciser(string: str) -> str:
        string = string.replace('R', 'K')
        string = string.replace('O', 'W')
        string = string.replace('D', 'Q')
        string = string.replace('V', 'J')
        string = string.replace('10', 'T')
        string = string.replace(' ', '')
        string = string.replace('\n', '')
        return string

    @staticmethod
    def get_vul(pdftext: str) -> Tuple[bool, bool]:
        VUL_TRAD = {'Personne': "None", "NS": "NS", "EO": "EW", "Tous": "All"}
        string = VUL_TRAD[pdftext[pdftext.find('Vulnérabilité : ')+len('Vulnérabilité : '): pdftext.find(
            '\n', pdftext.find('Vulnérabilité : ')+len('Vulnérabilité : '))]]
        if string == "None":
            return (False, False)
        if string == "NS":
            return (True, False)
        if string == "EW":
            return (False, True)
        if string == "All":
            return (True, True)
        raise Exception("Vulnérabilité incorrecte")

    @staticmethod
    def get_dealer(pdftext: str) -> Direction :
        PDF_TO_PBN_DEALER = {'O' : 'W','S' : 'S', 'N' : 'N','E':'E'}
        return Direction.from_str(PDF_TO_PBN_DEALER[pdftext[pdftext.find('Donneur : ')+len('Donneur : ')]])

    @staticmethod
    def get_board_number(pdftext: str) -> int :
        return int(pdftext[pdftext.find('DONNE N°')+len('DONNE N°') : pdftext.find('\n',pdftext.find('DONNE N°')+len('DONNE N°'))])