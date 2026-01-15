"""
斗地主共享类型定义
"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List


class Suit(Enum):
    """花色"""
    SPADE = "♠"
    HEART = "♥"
    DIAMOND = "♦"
    CLUB = "♣"


class CardValue(Enum):
    """卡牌值"""
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14
    TWO = 15
    SMALL_JOKER = 16
    BIG_JOKER = 17


class PlayType(Enum):
    """出牌类型（从弱到强排序）"""
    SINGLE = 1
    PAIR = 2
    TRIO = 3
    TRIO_SINGLE = 4
    TRIO_PAIR = 5
    STRAIGHT = 6
    PAIR_STRAIGHT = 7
    PLANE = 8
    PLANE_SINGLE = 9
    PLANE_PAIR = 10
    FOUR_WITH_TWO = 11
    BOMB = 12
    ROCKET = 13


@dataclass
class Card:
    """卡牌类"""
    suit: Optional[Suit]
    value: CardValue
    
    def __str__(self):
        if self.suit is None:
            if self.value == CardValue.SMALL_JOKER:
                return "J\nO\nK\nE\nR"
            else:
                return "J\nO\nK\nE\nR"
        value_names = {
            CardValue.THREE: '3', CardValue.FOUR: '4', CardValue.FIVE: '5',
            CardValue.SIX: '6', CardValue.SEVEN: '7', CardValue.EIGHT: '8',
            CardValue.NINE: '9', CardValue.TEN: '10', CardValue.JACK: 'J',
            CardValue.QUEEN: 'Q', CardValue.KING: 'K', CardValue.ACE: 'A',
            CardValue.TWO: '2'
        }
        suit_letters = {
            Suit.SPADE: "♠",
            Suit.HEART: "♥",
            Suit.DIAMOND: "♦",
            Suit.CLUB: "♣"
        }
        return f"{suit_letters[self.suit]}\n{value_names[self.value]}"
    
    def __eq__(self, other):
        if isinstance(other, Card):
            return self.value == other.value and self.suit == other.suit
        return False
    
    def __hash__(self):
        return hash((self.suit, self.value))
