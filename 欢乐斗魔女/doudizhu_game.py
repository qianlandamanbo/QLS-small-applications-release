"""
斗地主游戏 - 使用Pygame实现
完整版本，包含AI玩家、卡牌系统、游戏逻辑、鼠标选牌
"""
import ctypes
import pygame
import sys
import random
import os
from enum import Enum
from typing import List, Tuple, Optional, Set, Dict
from dataclasses import dataclass
from collections import Counter

from shared_types import Card, CardValue, Suit, PlayType
from ai_player import DoudizhuAI

# 初始化Pygame
pygame.init()

try:
    ctypes.windll.user32.SetProcessDPIAware()
except AttributeError:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass

# 常量定义
WINDOW_WIDTH = 2000
WINDOW_HEIGHT = 1400
FPS = 60
CARD_WIDTH = 200  # 增大卡牌宽度以显示更清晰的图片
CARD_HEIGHT = 300  # 增大卡牌高度
CARD_OVERLAP = int(CARD_WIDTH * 2/5)  # 叠放的重叠距离（1/3宽度，使每张牌露出2/3）
BG_COLOR = (135, 206, 236)  # 蓝色背景
TEXT_COLOR = (255, 255, 255)  # 白色文字
BUTTON_COLOR = (70, 70, 70)
BUTTON_HOVER_COLOR = (100, 100, 100)
BUTTON_PRESS_COLOR = (50, 50, 50)

class Deck:
    """牌堆类"""
    def __init__(self):
        self.cards = []
        self._initialize_deck()
    def _initialize_deck(self):
        """初始化牌堆（54张牌）"""
        self.cards = []
        # 添加普通牌（3-A，4种花色）
        for suit in Suit:
            for value in [CardValue.THREE, CardValue.FOUR, CardValue.FIVE,
                         CardValue.SIX, CardValue.SEVEN, CardValue.EIGHT,
                         CardValue.NINE, CardValue.TEN, CardValue.JACK,
                         CardValue.QUEEN, CardValue.KING, CardValue.ACE, CardValue.TWO]:
                self.cards.append(Card(suit, value))
        # 添加王牌
        self.cards.append(Card(None, CardValue.SMALL_JOKER))
        self.cards.append(Card(None, CardValue.BIG_JOKER))
    
    def shuffle(self):
        """洗牌"""
        random.shuffle(self.cards)
    
    def deal(self, num: int) -> List[Card]:
        """发牌"""
        return [self.cards.pop() for _ in range(num)]

class GamePhase(Enum):
    """游戏阶段"""
    DEALING = 1          # 发牌阶段
    PLAYING = 2          # 出牌阶段
    GAME_OVER = 3        # 游戏结束

class Player:
    """玩家类"""
    def __init__(self, player_id: int, name: str, is_ai: bool = False):
        self.id = player_id
        self.name = name
        self.is_ai = is_ai
        self.cards: List[Card] = []
        self.is_landlord = False
        self.is_active = True  # 是否还在游戏中
        self.last_played_cards: List[Card] = []  # 最后出的牌
    
    def add_cards(self, cards: List[Card]):
        """添加卡牌"""
        self.cards.extend(cards)
        self.sort_cards()
    
    def sort_cards(self):
        """对卡牌进行排序"""
        self.cards.sort(key=lambda c: (c.value.value, c.suit.value if c.suit else 0))
    
    def remove_cards(self, cards: List[Card]) -> bool:
        """移除卡牌"""
        for card in cards:
            if card in self.cards:
                self.cards.remove(card)
            else:
                return False
        return True
    
    def can_play(self, cards: List[Card]) -> bool:
        """检查是否能出牌"""
        if not cards:
            return True  # 不出牌总是可以的
        return all(card in self.cards for card in cards)
    
    def get_all_playable_moves(self) -> List[List[Card]]:
        """获取所有可能的出牌方式"""
        moves = []
        
        if not self.cards:
            return [[]]
        
        moves.append([])
        
        for card in self.cards:
            moves.append([card])
        
        for value in self._get_repeated_values(2):
            cards = [c for c in self.cards if c.value == value]
            if len(cards) >= 2:
                moves.append(cards[:2])
        
        for value in self._get_repeated_values(3):
            cards = [c for c in self.cards if c.value == value]
            if len(cards) >= 3:
                moves.append(cards[:3])
        
        for value in self._get_repeated_values(4):
            cards = [c for c in self.cards if c.value == value]
            if len(cards) == 4:
                moves.append(cards)
        
        trio_values = list(self._get_repeated_values(3))
        
        for value in trio_values:
            trio_cards = [c for c in self.cards if c.value == value]
            if len(trio_cards) >= 3:
                remaining = [c for c in self.cards if c.value != value]
                for single in remaining:
                    moves.append(trio_cards[:3] + [single])
                
                pair_values = {v for v in self._get_repeated_values(2) if v != value}
                for pair_val in pair_values:
                    pair_cards = [c for c in self.cards if c.value == pair_val]
                    moves.append(trio_cards[:3] + pair_cards[:2])
        
        moves.extend(self._get_straights())
        moves.extend(self._get_pair_straights())
        moves.extend(self._get_planes())
        moves.extend(self._get_plane_with_wings())
        
        has_small = any(c.value == CardValue.SMALL_JOKER for c in self.cards)
        has_big = any(c.value == CardValue.BIG_JOKER for c in self.cards)
        if has_small and has_big:
            small = next(c for c in self.cards if c.value == CardValue.SMALL_JOKER)
            big = next(c for c in self.cards if c.value == CardValue.BIG_JOKER)
            moves.append([small, big])
        
        return moves
    
    def _get_repeated_values(self, count: int) -> Set[CardValue]:
        """获取重复的卡牌值"""
        value_counts = Counter(card.value for card in self.cards)
        return {value for value, cnt in value_counts.items() if cnt >= count}
    
    def _get_straights(self, min_length: int = 5) -> List[List[Card]]:
        """获取所有可能的单顺"""
        sequences = []
        value_counts = Counter(card.value for card in self.cards)
        
        valid_values = [v for v in CardValue 
                       if v.value < CardValue.TWO.value 
                       and v != CardValue.SMALL_JOKER 
                       and v != CardValue.BIG_JOKER]
        
        sorted_values = sorted([v for v in self.cards if v.value in valid_values], 
                              key=lambda c: c.value.value)
        
        if len(sorted_values) < min_length:
            return sequences
        
        value_list = [c.value for c in sorted_values]
        unique_values = []
        seen = set()
        for v in value_list:
            if v not in seen:
                unique_values.append(v)
                seen.add(v)
        
        n = len(unique_values)
        for length in range(min_length, n + 1):
            for start in range(0, n - length + 1):
                straight_values = unique_values[start:start + length]
                if all(unique_values[start + i].value == unique_values[start].value + i 
                      for i in range(length)):
                    cards = []
                    for v in straight_values:
                        card = next(c for c in self.cards if c.value == v)
                        cards.append(card)
                    sequences.append(cards)
        
        return sequences
    
    def _get_pair_straights(self, min_pairs: int = 3) -> List[List[Card]]:
        """获取所有可能的双顺"""
        sequences = []
        pair_values = sorted(list(self._get_repeated_values(2)), key=lambda v: v.value)
        
        if len(pair_values) < min_pairs:
            return sequences
        
        n = len(pair_values)
        for length in range(min_pairs, n + 1):
            for start in range(0, n - length + 1):
                straight_values = pair_values[start:start + length]
                if all(pair_values[start + i].value == pair_values[start].value + i 
                      for i in range(length)):
                    cards = []
                    for v in straight_values:
                        card = [c for c in self.cards if c.value == v][:2]
                        cards.extend(card)
                    sequences.append(cards)
        
        return sequences
    
    def _get_planes(self, min_groups: int = 2) -> List[List[Card]]:
        """获取所有可能的飞机（纯飞机）"""
        planes = []
        trio_values = sorted(list(self._get_repeated_values(3)), key=lambda v: v.value)
        
        if len(trio_values) < min_groups:
            return planes
        
        n = len(trio_values)
        for length in range(min_groups, n + 1):
            for start in range(0, n - length + 1):
                plane_values = trio_values[start:start + length]
                if all(trio_values[start + i].value == trio_values[start].value + i 
                      for i in range(length)):
                    cards = []
                    for v in plane_values:
                        card = [c for c in self.cards if c.value == v][:3]
                        cards.extend(card)
                    planes.append(cards)
        
        return planes
    
    def _get_plane_with_wings(self) -> List[List[Card]]:
        """获取所有可能的飞机带翅膀"""
        planes = []
        trio_values = sorted(list(self._get_repeated_values(3)), key=lambda v: v.value)
        
        for trio_count in range(2, len(trio_values) + 1):
            for start in range(0, len(trio_values) - trio_count + 1):
                plane_values = trio_values[start:start + trio_count]
                if all(trio_values[start + i].value == trio_values[start].value + i 
                      for i in range(trio_count)):
                    trio_cards = []
                    for v in plane_values:
                        card = [c for c in self.cards if c.value == v][:3]
                        trio_cards.extend(card)
                    
                    remaining = [c for c in self.cards if c.value not in plane_values]
                    
                    single_count = trio_count
                    if len(remaining) >= single_count:
                        from itertools import combinations
                        for singles in combinations(remaining, single_count):
                            planes.append(list(trio_cards) + list(singles))
                    
                    pair_values = sorted([v for v in self._get_repeated_values(2) 
                                         if v not in plane_values], key=lambda v: v.value)
                    if len(pair_values) >= trio_count and len(remaining) >= trio_count * 2:
                        for i in range(len(pair_values) - trio_count + 1):
                            selected_pairs = pair_values[i:i + trio_count]
                            pair_cards = []
                            for v in selected_pairs:
                                pair_cards.extend([c for c in self.cards if c.value == v][:2])
                            planes.append(list(trio_cards) + pair_cards)
        
        return planes

class DoudizhuGame:
    """斗地主游戏主类"""
    def __init__(self):
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("斗地主 - Pygame")
        self.clock = pygame.time.Clock()
        
        # 加载本地字体文件 SourceHanSerifSC.otf
        font_path = os.path.join(os.path.dirname(__file__), "SourceHanSerifSC.otf")
        self.font_large = None
        self.font_medium = None
        self.font_small = None
        
        try:
            if os.path.exists(font_path):
                self.font_large = pygame.font.Font(font_path, 48)
                self.font_medium = pygame.font.Font(font_path, 32)
                self.font_small = pygame.font.Font(font_path, 24)
                print(f"✓ 已加载字体: {font_path}")
            else:
                print(f"⚠ 字体文件不存在: {font_path}")
                raise FileNotFoundError(f"Font file not found: {font_path}")
        except Exception as e:
            print(f"⚠ 字体加载失败: {e}")
            # 降级到系统字体
            font_names = ['SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei', 'DejaVu Sans']
            for font_name in font_names:
                try:
                    self.font_large = pygame.font.SysFont(font_name, 48)
                    self.font_medium = pygame.font.SysFont(font_name, 32)
                    self.font_small = pygame.font.SysFont(font_name, 24)
                    print(f"✓ 已加载系统字体: {font_name}")
                    break
                except:
                    continue
        
        # 如果都失败，使用默认字体
        if self.font_large is None:
            self.font_large = pygame.font.Font(None, 48)
            self.font_medium = pygame.font.Font(None, 32)
            self.font_small = pygame.font.Font(None, 24)
            print("✓ 已加载默认字体")
        
        self.players: List[Player] = []
        self.deck = None
        self.phase = GamePhase.DEALING
        self.current_player_id = 0
        self.last_player_id = -1
        self.trump_cards: List[Card] = []
        self.table_cards: List[Card] = []  # 桌面上的牌（保留用于兼容性）
        self.player_table_cards: Dict[int, List[Card]] = {}  # 每个玩家出的牌 {玩家ID: [牌列表]}
        self.player_passed: Dict[int, bool] = {}  # 记录每个玩家是否跳过 {玩家ID: 是否跳过}
        self.table_origin_center = True  # 本次桌面牌是否应居中显示（新一轮或清空时）
        self.pass_count = 0  # 连续不出牌的玩家数
        self.selected_cards: Set[int] = set()  # 选中的卡牌索引
        self.game_message = ""  # 游戏信息提示
        self.message_timer = 0  # 信息显示计时器
        
        # 按钮
        self.play_button = pygame.Rect(WINDOW_WIDTH - 200, WINDOW_HEIGHT - 100, 90, 50)
        self.skip_button = pygame.Rect(WINDOW_WIDTH - 100, WINDOW_HEIGHT - 100, 90, 50)
        self.restart_button = pygame.Rect(WINDOW_WIDTH // 2 - 160, WINDOW_HEIGHT // 2 + 120, 160, 70)
        self.button_hover = None  # 鼠标悬停的按钮
        
        # 加载自定义卡牌图片
        self.card_images: Dict[str, pygame.Surface] = {}
        self._load_card_images()
        # 玩家头像字典
        self.avatar_images: Dict[int, pygame.Surface] = {}
        self._load_avatars()

        # 加载背景图片
        self.bg_image = None
        self._load_bg_image()
        
        self._init_game()
    
    def _init_game(self):
        """初始化游戏"""
        # 桌面状态清空
        self.table_cards = []
        self.player_table_cards = {}
        self.player_passed = {}
        self.pass_count = 0
        self.last_player_id = -1
        self.selected_cards = set()
        self.game_message = ""
        self.message_timer = 0
        
        # 创建玩家
        self.players = [
            Player(0, "月代ユキ", is_ai=False),
            Player(1, "二階堂ヒロ", is_ai=True),
            Player(2, "桜羽エマ", is_ai=True),
        ]
        
        # 发牌
        self.deck = Deck()
        self.deck.shuffle()
        
        # 每个玩家发17张牌
        for player in self.players:
            player.add_cards(self.deck.deal(17))
        
        # 剩余的3张牌作为地主的底牌
        self.trump_cards = self.deck.deal(3)
        
        # 随机分配地主
        landlord_id = random.randint(0, 2)
        self.players[landlord_id].is_landlord = True
        self.players[landlord_id].add_cards(self.trump_cards)
        self.current_player_id = landlord_id
        self.show_message(f"{self.players[landlord_id].name}是地主！", 120)
        self.phase = GamePhase.PLAYING
    
    def _load_card_images(self):
        """加载自定义卡牌图片"""
        card_images_dir = os.path.join(os.path.dirname(__file__), "card_images")
        
        if not os.path.exists(card_images_dir):
            print(f"警告: {card_images_dir} 文件夹不存在")
            return
        
        # 定义卡牌值与文件名的映射
        value_names = {
            CardValue.THREE: '3',
            CardValue.FOUR: '4',
            CardValue.FIVE: '5',
            CardValue.SIX: '6',
            CardValue.SEVEN: '7',
            CardValue.EIGHT: '8',
            CardValue.NINE: '9',
            CardValue.TEN: '10',
            CardValue.JACK: 'J',
            CardValue.QUEEN: 'Q',
            CardValue.KING: 'K',
            CardValue.ACE: 'A',
            CardValue.TWO: '2',
            CardValue.SMALL_JOKER: 'small_joker',
            CardValue.BIG_JOKER: 'big_joker',
        }
        
        # 尝试加载所有卡牌图片
        for value, value_name in value_names.items():
            for ext in ['.png', '.jpg', '.jpeg']:
                file_path = os.path.join(card_images_dir, f"{value_name}{ext}")
                if os.path.exists(file_path):
                    try:
                        img = pygame.image.load(file_path)
                        # 等比例缩放，只限制宽度填充牌面宽度
                        img = self._scale_image_proportionally(img, CARD_WIDTH, None)
                        self.card_images[value.name] = img
                        print(f"加载卡牌图片: {value_name}")
                    except Exception as e:
                        print(f"加载图片失败 {file_path}: {e}")
                    break
    
    def _load_avatars(self):
        """加载玩家头像"""
        avatar_dir = os.path.join(os.path.dirname(__file__), "avatar")
        
        if not os.path.exists(avatar_dir):
            print(f"警告: {avatar_dir} 文件夹不存在")
            # 创建默认头像
            self._create_default_avatars()
            return
        
        # 尝试加载三个玩家的头像
        for i in range(1, 4):
            avatar_id = i - 1  # 玩家ID从0开始
            for ext in ['.png', '.jpg', '.jpeg', '.bmp']:
                file_path = os.path.join(avatar_dir, f"avatar{i}{ext}")
                if os.path.exists(file_path):
                    try:
                        img = pygame.image.load(file_path)
                        # 将头像缩放为圆形，大小为200x200
                        img = self._crop_to_circle(img, 200)
                        self.avatar_images[avatar_id] = img
                        print(f"加载头像: avatar{i}")
                        break
                    except Exception as e:
                        print(f"加载头像失败 {file_path}: {e}")
        
        # 如果没有加载到头像，创建默认头像
        if len(self.avatar_images) < 3:
            self._create_default_avatars()

    def _crop_to_circle(self, surface: pygame.Surface, diameter: int) -> pygame.Surface:
        """将图片裁剪为圆形"""
        # 先将图片缩放为正方形
        surface = pygame.transform.scale(surface, (diameter, diameter))
        
        # 创建一个带透明通道的表面
        circle_surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        
        # 在circle_surface上绘制圆形
        center = diameter // 2
        radius = diameter // 2
        
        # 绘制圆形遮罩
        for x in range(diameter):
            for y in range(diameter):
                if (x - center) ** 2 + (y - center) ** 2 <= radius ** 2:
                    color = surface.get_at((x, y))
                    circle_surface.set_at((x, y), color)
        
        return circle_surface

    def _create_default_avatars(self):
        """创建默认头像"""
        colors = [(255, 100, 100), (100, 100, 255), (100, 255, 100)]  # 红、蓝、绿
        names = ["月代ユキ", "二階堂ヒロ", "桜羽エマ"]
        
        for i in range(3):
            # 创建圆形表面
            surface = pygame.Surface((200, 200), pygame.SRCALPHA)
            center = (100, 100)
            
            # 绘制圆形背景
            pygame.draw.circle(surface, colors[i], center, 100)
            
            # 绘制玩家名字的第一个字符
            font = pygame.font.Font(None, 80)
            text = font.render(names[i][0], True, (255, 255, 255))
            text_rect = text.get_rect(center=center)
            surface.blit(text, text_rect)
            
            self.avatar_images[i] = surface
            print(f"创建默认头像: 玩家{i}")

    def _load_bg_image(self):
        """加载背景图片"""
        bg_path = os.path.join(os.path.dirname(__file__), "bg.png")
        
        if not os.path.exists(bg_path):
            print(f"警告: {bg_path} 不存在")
            return
        
        try:
            bg_image = pygame.image.load(bg_path)
            self.bg_image = pygame.transform.scale(bg_image, (WINDOW_WIDTH, WINDOW_HEIGHT))
            print(f"✓ 已加载背景图片: {bg_path}")
        except Exception as e:
            print(f"加载背景图片失败: {e}")
            self.bg_image = None

    def _render_name_fit(self, name: str, max_width: int) -> pygame.Surface:
        """渲染名字并在超出宽度时添加省略号以适配头像宽度"""
        # 使用 self.font_small 渲染，超出宽度时裁剪并添加省略号
        font = self.font_small
        text = name
        surface = font.render(text, True, TEXT_COLOR)
        if surface.get_width() <= max_width:
            return surface

        # 逐步缩短并添加省略号
        ellipsis = '…'
        # 保证至少留一个字符
        while len(text) > 1:
            text = text[:-1]
            cand = text + ellipsis
            surface = font.render(cand, True, TEXT_COLOR)
            if surface.get_width() <= max_width:
                return surface

        # 回退到单字符的省略形式
        return font.render(ellipsis, True, TEXT_COLOR)
    
    def _scale_image_proportionally(self, image: pygame.Surface, target_width: int, max_height: Optional[int]) -> pygame.Surface:
        """等比例缩放图片，使其填充指定宽度"""
        original_width = image.get_width()
        original_height = image.get_height()
        
        # 计算宽高比
        aspect_ratio = original_height / original_width  # 高/宽
        
        # 根据目标宽度计算新的高度
        new_width = target_width
        new_height = int(target_width * aspect_ratio)
        
        # 如果指定了最大高度，则限制不超过最大高度
        if max_height is not None and new_height > max_height:
            new_height = max_height
            new_width = int(max_height / aspect_ratio)
        
        return pygame.transform.scale(image, (new_width, new_height))
    
    def _convert_to_grayscale(self, surface: pygame.Surface) -> pygame.Surface:
        """将图片转换为灰度（黑白）"""
        return pygame.transform.grayscale(surface)
    
    def _get_card_image(self, card: Card, for_grayscale: bool = False) -> Optional[pygame.Surface]:
        """获取卡牌的图片"""
        value_name = card.value.name
        
        if value_name in self.card_images:
            img = self.card_images[value_name]
            # 如果需要灰度转换（方片和梅花）
            if for_grayscale:
                return self._convert_to_grayscale(img)
            return img
        return None
    
    def show_message(self, msg: str, duration: int = 120):
        """显示游戏信息"""
        self.game_message = msg
        self.message_timer = duration
    
    def _format_cards_short(self, cards: List[Card]) -> str:
        """格式化卡牌信息为简短字符串"""
        if not cards:
            return ""
        
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
        
        card_strs = []
        for card in cards:
            if card.suit is None:
                if card.value == CardValue.SMALL_JOKER:
                    card_strs.append("小王")
                else:
                    card_strs.append("大王")
            else:
                suit = suit_letters[card.suit]
                value = value_names[card.value]
                card_strs.append(f"{suit}{value}")
        
        return " ".join(card_strs)

    def is_valid_play(self, cards: List[Card], last_cards: List[Card]) -> bool:
        """检查是否是有效的出牌"""
        if not cards:  # 不出牌总是有效的
            return True
        
        if not last_cards:  # 第一个出牌的总是有效
            return True
        # 必须是合法的牌型
        t1, k1 = self.classify_cards(cards)
        if t1 is None:
            return False
        # 如果没有上手牌（轮空）则合法
        if not last_cards:
            return True
        # 比较两手牌大小
        return self._compare_play(cards, last_cards) > 0

    def classify_cards(self, cards: List[Card]) -> Tuple[PlayType, any]:
        """识别牌型，返回 (牌型, 比较值)"""
        if not cards:
            return None, None

        values = [c.value for c in cards]
        counts = Counter(values)
        unique_values = sorted(set(values), key=lambda v: v.value)
        length = len(cards)

        # Rocket
        if length == 2 and CardValue.SMALL_JOKER in counts and CardValue.BIG_JOKER in counts:
            return PlayType.ROCKET, CardValue.BIG_JOKER.value

        # Single
        if length == 1:
            return PlayType.SINGLE, values[0].value

        # Pair
        if length == 2 and len(counts) == 1:
            v = next(iter(counts))
            return PlayType.PAIR, v.value

        # Trio
        if length == 3 and 3 in counts.values():
            v = [k for k, cnt in counts.items() if cnt == 3][0]
            return PlayType.TRIO, v.value

        # Bomb (strictly four of a kind and exactly 4 cards)
        if length == 4 and 4 in counts.values():
            v = [k for k, cnt in counts.items() if cnt == 4][0]
            return PlayType.BOMB, v.value

        # Four with two (四带二)：6张（4+1+1）或8张（4+2+2）
        if any(cnt == 4 for cnt in counts.values()):
            four_val = [k for k, cnt in counts.items() if cnt == 4][0]
            if length == 6:
                # 4 + 1 + 1
                others = [k for k, cnt in counts.items() if k != four_val]
                if len(others) == 2 and all(counts[k] == 1 for k in others):
                    return PlayType.FOUR_WITH_TWO, four_val.value
            if length == 8:
                # 4 + 2 + 2
                others = [k for k, cnt in counts.items() if k != four_val]
                if len(others) == 2 and all(counts[k] == 2 for k in others):
                    return PlayType.FOUR_WITH_TWO, four_val.value

        # 三带一 / 三带一对
        if 3 in counts.values():
            trio_val = [k for k, cnt in counts.items() if cnt == 3][0]
            if length == 4:
                return PlayType.TRIO_SINGLE, trio_val.value
            if length == 5:
                # 3 + 1 + 1 (invalid) or 3 + 2
                others = [cnt for k, cnt in counts.items() if k != trio_val]
                if sorted(others) == [2]:
                    return PlayType.TRIO_PAIR, trio_val.value
                if sorted(others) == [1, 1]:
                    return PlayType.TRIO_SINGLE, trio_val.value

        # Pair straight (双顺): 3对或以上连续对子，不能包含2或王
        pair_vals = [v for v, cnt in counts.items() if cnt >= 2 and v.value < CardValue.TWO.value]
        pair_vals_sorted = sorted(pair_vals, key=lambda v: v.value)
        if len(pair_vals_sorted) >= 3:
            # check consecutive
            n = len(pair_vals_sorted)
            # try all possible consecutive runs with exact card length
            for run_len in range(3, n + 1):
                for start in range(0, n - run_len + 1):
                    run = pair_vals_sorted[start:start + run_len]
                    if all(run[i].value == run[0].value + i for i in range(run_len)):
                        if length == run_len * 2:
                            return PlayType.PAIR_STRAIGHT, run[-1].value

        # Single straight (顺子): 5张或以上连续单张，不能包含2或王
        single_vals = [v for v in unique_values if v.value < CardValue.TWO.value]
        if len(single_vals) >= 5 and length == len(single_vals):
            if all(single_vals[i].value == single_vals[0].value + i for i in range(len(single_vals))):
                return PlayType.STRAIGHT, single_vals[-1].value

        # Plane and plane with wings
        trio_vals = [v for v, cnt in counts.items() if cnt >= 3 and v.value < CardValue.TWO.value]
        trio_vals_sorted = sorted(trio_vals, key=lambda v: v.value)
        if len(trio_vals_sorted) >= 2:
            n = len(trio_vals_sorted)
            for run_len in range(2, n + 1):
                for start in range(0, n - run_len + 1):
                    run = trio_vals_sorted[start:start + run_len]
                    if all(run[i].value == run[0].value + i for i in range(run_len)):
                        base_cards = run_len * 3
                        # pure plane
                        if length == base_cards:
                            return PlayType.PLANE, run[-1].value
                        # plane + singles (each wing single)
                        if length == base_cards + run_len:
                            return PlayType.PLANE_SINGLE, run[-1].value
                        # plane + pairs (each wing a pair)
                        if length == base_cards + run_len * 2:
                            # ensure there are run_len pairs in the rest
                            rest_counts = {k: cnt for k, cnt in counts.items() if k not in run}
                            if sum(1 for cnt in rest_counts.values() if cnt >= 2) >= run_len:
                                return PlayType.PLANE_PAIR, run[-1].value

        return None, None

    def _compare_play(self, cards: List[Card], last_cards: List[Card]) -> int:
        """比较两手牌的强弱，返回 1=赢, -1=输, 0=无效比较"""
        if not cards:
            return -1
        if not last_cards:
            return 1
        type1, key1 = self.classify_cards(cards)
        type2, key2 = self.classify_cards(last_cards)

        # 如果任一手牌不是合法牌型
        if type1 is None or type2 is None:
            return 0

        len1 = len(cards)
        len2 = len(last_cards)

        # same type must also have compatible lengths
        if type1 == type2:
            # 对于顺子/连对/飞机类，长度必须相等
            if type1 in (PlayType.STRAIGHT, PlayType.PAIR_STRAIGHT, PlayType.PLANE, PlayType.PLANE_PAIR, PlayType.PLANE_SINGLE):
                if len1 != len2:
                    return 0
                # 比较主段最高点
                return 1 if key1 > key2 else (-1 if key1 < key2 else 0)

            # 四带二按四张部分比较，长度也需相等
            if type1 == PlayType.FOUR_WITH_TWO:
                if len1 != len2:
                    return 0
                return 1 if key1 > key2 else (-1 if key1 < key2 else 0)

            # 其他普通牌型：长度相等并比较点数
            if len1 != len2:
                return 0
            return 1 if key1 > key2 else (-1 if key1 < key2 else 0)

        # 不同牌型的比较：rocket最大
        if type1 == PlayType.ROCKET:
            return 1
        if type2 == PlayType.ROCKET:
            return -1

        # 炸弹可以压制除火箭外的任何牌型
        if type1 == PlayType.BOMB and type2 != PlayType.ROCKET:
            return 1
        if type2 == PlayType.BOMB and type1 != PlayType.ROCKET:
            return -1

        # 其他不同牌型不能相互比较
        return 0
    
    def get_ai_move(self, player: Player) -> List[Card]:
        """AI玩家出牌逻辑"""
        opponent_count = sum(1 for p in self.players if len(p.cards) > 0 and p.id != player.id)
        return DoudizhuAI.get_best_move(
            player.cards, 
            self.table_cards,
            player.is_landlord,
            opponent_count
        )
    
    def play_card(self, player_id: int, cards: List[Card]) -> bool:
        """出牌"""
        player = self.players[player_id]
        print(f"play_card调用: 玩家={player.name}, 牌={[str(c) for c in cards]}")
        print(f"  玩家手牌数: {len(player.cards)}")
        print(f"  table_cards: {[str(c) for c in self.table_cards]}")

        if not cards:
            print(f"  玩家选择不出牌")
            self.player_passed[player_id] = True
            self.pass_count += 1
            print(f"  pass_count: {self.pass_count}")
            
            if self.pass_count >= 3:
                print(f"  所有玩家都跳过，清除桌面牌")
                self.table_cards = []
                self.player_table_cards = {}
                self.player_passed = {0: False, 1: False, 2: False}
                self.pass_count = 0
            
            self.current_player_id = (self.current_player_id + 1) % 3
            return True

        if not player.can_play(cards):
            print(f"  can_play失败")
            return False
        
        is_valid = self.is_valid_play(cards, self.table_cards)
        print(f"  is_valid_play结果: {is_valid}")
        if not is_valid:
            return False
        
        if player.remove_cards(cards):
            print(f"  移除牌成功，剩余手牌数: {len(player.cards)}")
            self.table_cards = cards
            self.player_table_cards[player_id] = cards.copy()
            player.last_played_cards = cards
            self.player_passed[player_id] = False
            self.pass_count = 0
            self.last_player_id = player_id
            print(f"  桌面牌已更新: {[str(c) for c in self.table_cards]}")

            self.current_player_id = (self.current_player_id + 1) % 3

            if len(player.cards) == 0:
                self.phase = GamePhase.GAME_OVER
                self._determine_winner()
                return True

            return True
        print(f"  remove_cards失败")
        return False
    
    def skip_turn(self):
        """跳过回合"""
        self.player_passed[self.current_player_id] = True
        self.pass_count += 1
        self.current_player_id = (self.current_player_id + 1) % 3
        
        # 如果其他两个玩家都跳过，清空所有玩家的桌面牌和跳过状态
        if self.pass_count >= 2:
            self.table_cards = []
            self.player_table_cards = {}
            self.player_passed = {}
            self.pass_count = 0
            self.last_player_id = -1
    
    def _determine_winner(self):
        """确定赢家"""
        landlord = None
        for player in self.players:
            if player.is_landlord:
                landlord = player
                break
        
        if len(landlord.cards) == 0:
            self.show_message(f"{landlord.name}（地主）赢了！", 99999)
        else:
            self.show_message("农民赢了！", 99999)
    
    def draw(self):
        """绘制游戏画面"""
        self.screen.fill(BG_COLOR)
        
        # 绘制半透明背景图片
        if self.bg_image:
            bg_surface = self.bg_image.copy()
            bg_surface.set_alpha(128)  # 50%透明度
            self.screen.blit(bg_surface, (0, 0))

         # 绘制玩家头像和名字
        self._draw_player_avatars()
        
        # 绘制桌面卡牌
        self._draw_table_cards()
        
        # 绘制玩家卡牌
        self._draw_player_cards()
        
        # 绘制玩家信息
        self._draw_player_info()
        
        # 绘制游戏阶段信息
        self._draw_phase_info()
        
        # 绘制按钮
        self._draw_buttons()
        
        pygame.display.flip()
    
    def _draw_player_cards(self):
        """绘制玩家卡牌（叠放样式，最右边的牌在最上面）"""
        player = self.players[0]  # 当前人类玩家
        
        card_y = WINDOW_HEIGHT - CARD_HEIGHT - 70
        num_cards = len(player.cards)
        
        if num_cards == 0:
            return
        
        # 计算总宽度：最右边的牌完整显示 + 前面的牌被覆盖2/3
        # 每张牌露出CARD_OVERLAP距离
        total_width = CARD_WIDTH + (num_cards - 1) * CARD_OVERLAP
        start_x = (WINDOW_WIDTH - total_width) // 2
        
        # 正序绘制（从索引0到num_cards-1），这样最后绘制的牌在最上面
        for i in range(num_cards):
            card_x = start_x + i * CARD_OVERLAP
            card = player.cards[i]
            
            # 选中的卡牌上移
            offset_y = -20 if i in self.selected_cards else 0
            self._draw_card(card_x, card_y + offset_y, card, i in self.selected_cards)
    
    def _get_card_rect(self, index: int) -> pygame.Rect:
        """获取卡牌在屏幕上的矩形区域（用于鼠标碰撞检测）"""
        player = self.players[0]
        card_y = WINDOW_HEIGHT - CARD_HEIGHT - 70
        num_cards = len(player.cards)
        
        # 计算总宽度：最后一张卡牌的完整宽度 + 前面卡牌的重叠宽度
        total_width = CARD_WIDTH + (num_cards - 1) * CARD_OVERLAP
        start_x = (WINDOW_WIDTH - total_width) // 2
        
        card_x = start_x + index * CARD_OVERLAP
        offset_y = -20 if index in self.selected_cards else 0
        return pygame.Rect(card_x, card_y + offset_y, CARD_WIDTH, CARD_HEIGHT)
    
    def _draw_card(self, x: int, y: int, card: Card, highlighted: bool = False):
        """绘制单张卡牌
        布局：图片填充整个牌面，文字在左上角竖向排版
        文字使用投射阴影效果，尽可能充满CARD_OVERLAP宽度
        """
        # 绘制卡牌背景
        color = (200, 200, 100) if highlighted else (255, 255, 255)
        pygame.draw.rect(self.screen, color, (x, y, CARD_WIDTH, CARD_HEIGHT))
        
        # 绘制背景图片（填充整个牌面）
        card_image = self._get_card_image(card, for_grayscale=False)
        
        if card_image is not None:
            # 图片填充整个牌面宽度，垂直居中
            img_width = card_image.get_width()
            img_height = card_image.get_height()
            
            # 计算图片位置（水平填充，垂直居中）
            img_x = x + (CARD_WIDTH - img_width) // 2
            img_y = y + (CARD_HEIGHT - img_height) // 2
            
            self.screen.blit(card_image, (img_x, img_y))
        
        # 在左上角绘制文字（竖向排版，尽可能充满CARD_OVERLAP宽度）
        text_str = str(card)  # "S\n3" 或 "小\n王" 之类
        lines = text_str.split('\n')
        
        # 根据花色确定文字颜色
        # 红心为红色，方片和黑桃为黑色，小王为黑色，大王为红色
        if card.suit in [Suit.SPADE, Suit.CLUB]:
            text_color = (0, 0, 0)  
        elif card.suit in [Suit.DIAMOND, Suit.HEART]:
            text_color = (255, 0, 0)  
        elif card.value == CardValue.SMALL_JOKER:
            text_color = (0, 0, 0)  # 小王黑色
        else:
            text_color = (255, 0, 0)  # 大王红色  
        
        # 投射阴影颜色（深灰色）
        shadow_color = (100, 100, 100)
        shadow_offset = 2  # 阴影偏移量
        
        # 计算文字的最适字体大小，使其尽可能充满CARD_OVERLAP宽度
        # CARD_OVERLAP是每张牌露出的宽度
        available_width = CARD_OVERLAP - 8  # 留出一点边距
        
        # 尝试不同的字体大小，找到最大的能够填充宽度的
        best_font = self.font_small
        for test_size in [40, 36, 32, 28, 24, 20, 16]:
            test_font = pygame.font.Font(
                os.path.join(os.path.dirname(__file__), "SourceHanSerifSC.otf"),
                test_size
            ) if os.path.exists(os.path.join(os.path.dirname(__file__), "SourceHanSerifSC.otf")) else pygame.font.Font(None, test_size)
            
            # 检查每一行的宽度
            max_line_width = 0
            for line in lines:
                line_surface = test_font.render(line, True, text_color)
                max_line_width = max(max_line_width, line_surface.get_width())
            
            if max_line_width <= available_width:
                best_font = test_font
                break
        
        # 绘制文字（带投射阴影）
        text_x = x + 4  # 左上角位置
        text_y = y + 4
        
        # 根据是否是王牌调整行距
        line_spacing = 40 if card.suit is None else 40
        
        for line_idx, line in enumerate(lines):
            # 绘制阴影文字
            shadow_surface = best_font.render(line, True, shadow_color)
            self.screen.blit(shadow_surface, (text_x + shadow_offset, text_y + shadow_offset + line_idx * line_spacing))
            
            # 绘制正常文字
            text_surface = best_font.render(line, True, text_color)
            self.screen.blit(text_surface, (text_x, text_y + line_idx * line_spacing))
        
        # 绘制卡牌边框
        pygame.draw.rect(self.screen, (0, 0, 0), (x, y, CARD_WIDTH, CARD_HEIGHT), 2)
    
    def _draw_table_cards(self):
        """绘制桌面卡牌（每个玩家的牌显示在靠近该玩家的位置）"""
        print(f"DEBUG _draw_table_cards: player_table_cards={self.player_table_cards}")
        
        if not self.player_table_cards and not self.player_passed:
            return
        
        font = pygame.font.SysFont('SimHei', 28, bold=True)
        
        # 绘制每个玩家的出牌或跳过状态
        for player_id in range(3):
            cards = self.player_table_cards.get(player_id, [])
            passed = self.player_passed.get(player_id, False)
            
            # 根据玩家ID确定绘制位置（靠近玩家头像）
            if player_id == 0:
                table_y = WINDOW_HEIGHT - CARD_HEIGHT - 400
                center_x = WINDOW_WIDTH // 2
            elif player_id == 1:
                table_y = 210
                center_x = 250 + CARD_WIDTH // 2
            elif player_id == 2:
                table_y = 210
                center_x = WINDOW_WIDTH - 250 - CARD_WIDTH // 2
            else:
                continue
            
            print(f"  玩家{player_id}: cards={len(cards)}, y={table_y}")
            
            if passed:
                text_surf = font.render("跳过", True, (150, 150, 150))
                text_rect = text_surf.get_rect(center=(center_x, table_y + CARD_HEIGHT // 2))
                self.screen.blit(text_surf, text_rect)
            elif cards:
                num_cards = len(cards)
                total_width = CARD_WIDTH + (num_cards - 1) * CARD_OVERLAP
                start_x = center_x - total_width // 2
                
                for i in range(num_cards):
                    card_x = start_x + i * CARD_OVERLAP
                    card = cards[i]
                    self._draw_card(card_x, table_y, card)
    
    def _draw_player_avatars(self):
        """绘制玩家头像和名字"""
        avatar_size = 200  # 头像直径
        
        # 玩家0（你） - 左下角
        player0_x = 20
        player0_y = WINDOW_HEIGHT - avatar_size - 20
        if 0 in self.avatar_images:
            self.screen.blit(self.avatar_images[0], (player0_x, player0_y))
        
        # 绘制边框（如果是当前玩家）
        if self.current_player_id == 0:
            pygame.draw.circle(self.screen, (255, 255, 0), 
                            (player0_x + avatar_size//2, player0_y + avatar_size//2), 
                            avatar_size//2 + 3, 3)
        
        # 绘制玩家0名字（头像上方）
        name_surf = self._render_name_fit(self.players[0].name, avatar_size + 40)
        name_rect = name_surf.get_rect(midbottom=(player0_x + avatar_size//2, player0_y - 5))
        self.screen.blit(name_surf, name_rect)
        
        # 玩家1（电脑1） - 左上角
        player1_x = 20
        player1_y = 20
        if 1 in self.avatar_images:
            self.screen.blit(self.avatar_images[1], (player1_x, player1_y))
        
        # 绘制边框（如果是当前玩家）
        if self.current_player_id == 1:
            pygame.draw.circle(self.screen, (255, 255, 0), 
                            (player1_x + avatar_size//2, player1_y + avatar_size//2), 
                            avatar_size//2 + 3, 3)
        
        # 绘制玩家1名字（头像下方）
        name_surf = self._render_name_fit(self.players[1].name, avatar_size + 40)
        name_rect = name_surf.get_rect(midtop=(player1_x + avatar_size//2, player1_y + avatar_size + 5))
        self.screen.blit(name_surf, name_rect)
        
        # 玩家2（电脑2） - 右上角
        player2_x = WINDOW_WIDTH - avatar_size - 20
        player2_y = 20
        if 2 in self.avatar_images:
            self.screen.blit(self.avatar_images[2], (player2_x, player2_y))
        
        # 绘制边框（如果是当前玩家）
        if self.current_player_id == 2:
            pygame.draw.circle(self.screen, (255, 255, 0), 
                            (player2_x + avatar_size//2, player2_y + avatar_size//2), 
                            avatar_size//2 + 3, 3)
        
        # 绘制玩家2名字（头像下方）
        name_surf = self._render_name_fit(self.players[2].name, avatar_size + 40)
        name_rect = name_surf.get_rect(midtop=(player2_x + avatar_size//2, player2_y + avatar_size + 5))
        self.screen.blit(name_surf, name_rect)
    
    def _draw_phase_info(self):
        """绘制游戏阶段信息"""
        pass

    def _draw_player_info(self):
        """绘制玩家的简要信息（手牌数和是否为地主）"""
        # 在右上角显示每个玩家的手牌数量与身份
        x = WINDOW_WIDTH - 450
        y = 20
        for p in self.players:
            label = f"{p.name}: {len(p.cards)}张"
            if p.is_landlord:
                label += " (地主)"
            surf = self.font_small.render(label, True, (0, 0, 0))
            self.screen.blit(surf, (x, y))
            y += 28
    
    def _draw_buttons(self):
        """绘制操作按钮"""
        if self.phase == GamePhase.GAME_OVER:
            overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 128))
            self.screen.blit(overlay, (0, 0))
            
            button_color = BUTTON_HOVER_COLOR if self.button_hover == "restart" else BUTTON_COLOR
            pygame.draw.rect(self.screen, button_color, self.restart_button)
            pygame.draw.rect(self.screen, (255, 255, 255), self.restart_button, 3)
            restart_text = self.font_large.render("重开一局", True, TEXT_COLOR)
            restart_text_rect = restart_text.get_rect(center=self.restart_button.center)
            self.screen.blit(restart_text, restart_text_rect)
            return
        
        if self.phase != GamePhase.PLAYING:
            return
        
        button_color = BUTTON_HOVER_COLOR if self.button_hover == "play" else BUTTON_COLOR
        pygame.draw.rect(self.screen, button_color, self.play_button)
        pygame.draw.rect(self.screen, (255, 255, 255), self.play_button, 2)
        play_text = self.font_small.render("出牌", True, TEXT_COLOR)
        play_text_rect = play_text.get_rect(center=self.play_button.center)
        self.screen.blit(play_text, play_text_rect)
        
        button_color = BUTTON_HOVER_COLOR if self.button_hover == "skip" else BUTTON_COLOR
        pygame.draw.rect(self.screen, button_color, self.skip_button)
        pygame.draw.rect(self.screen, (255, 255, 255), self.skip_button, 2)
        skip_text = self.font_small.render("跳过", True, TEXT_COLOR)
        skip_text_rect = skip_text.get_rect(center=self.skip_button.center)
        self.screen.blit(skip_text, skip_text_rect)
        
        # 显示游戏信息
        if self.message_timer > 0:
            msg_surface = self.font_medium.render(self.game_message, True, (255, 255, 100))
            msg_rect = msg_surface.get_rect(center=(WINDOW_WIDTH // 2, 50))
            self.screen.blit(msg_surface, msg_rect)
            self.message_timer -= 1
    
    def handle_mouse_click(self, pos: Tuple[int, int]):
        """处理鼠标点击"""
        if self.phase == GamePhase.GAME_OVER:
            if self.restart_button.collidepoint(pos):
                self._init_game()
                return
            return
        
        if self.phase == GamePhase.PLAYING and self.players[0].id == self.current_player_id:
            if self.play_button.collidepoint(pos):
                self._try_play_cards()
                return
            elif self.skip_button.collidepoint(pos):
                self.skip_turn()
                return
        
        if self.phase == GamePhase.PLAYING and self.players[0].id == self.current_player_id:
            for i in range(len(self.players[0].cards) - 1, -1, -1):
                card_rect = self._get_card_rect(i)
                if card_rect.collidepoint(pos):
                    if i in self.selected_cards:
                        self.selected_cards.remove(i)
                    else:
                        self.selected_cards.add(i)
                    return
    
    def handle_mouse_motion(self, pos: Tuple[int, int]):
        """处理鼠标移动"""
        if self.phase == GamePhase.GAME_OVER:
            if self.restart_button.collidepoint(pos):
                self.button_hover = "restart"
            else:
                self.button_hover = None
            return
        
        if self.play_button.collidepoint(pos):
            self.button_hover = "play"
        elif self.skip_button.collidepoint(pos):
            self.button_hover = "skip"
        else:
            self.button_hover = None
    
    def _try_play_cards(self):
        """尝试出牌"""
        if not self.selected_cards:
            self.show_message("请先选择卡牌！", 60)
            return
        
        player = self.players[0]
        cards_to_play = [player.cards[i] for i in sorted(self.selected_cards)]
        
        if self.is_valid_play(cards_to_play, self.table_cards):
            if self.play_card(0, cards_to_play):
                self.selected_cards.clear()
                self.show_message("出牌成功！", 60)
        else:
            self.show_message("出牌无效！请检查卡牌组合", 60)
    
    def run(self):
        """运行游戏"""
        running = True
        
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # 左键
                        self.handle_mouse_click(event.pos)
                
                if event.type == pygame.MOUSEMOTION:
                    self.handle_mouse_motion(event.pos)
            
            # AI玩家自动出牌
            if self.phase == GamePhase.PLAYING:
                player = self.players[self.current_player_id]
                if player.is_ai:
                    pygame.time.delay(2000)  # 延迟800ms让游戏看起来更自然
                    cards = self.get_ai_move(player)
                    print(f"AI {player.name} 出牌: {[str(c) for c in cards]}")
                    if cards:
                        result = self.play_card(player.id, cards)
                        print(f"play_card结果: {result}")
                        cards_str = self._format_cards_short(cards)
                        self.show_message(f"{player.name}出了{len(cards)}张牌: {cards_str}", 60)
                    else:
                        self.skip_turn()
                        self.show_message(f"{player.name}跳过了", 60)
            
            self.draw()
            self.clock.tick(FPS)
        
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    game = DoudizhuGame()
    game.run()
