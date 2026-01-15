"""
斗地主AI玩家决策模块
基于ruru.txt策略文档实现
"""
import random
from typing import List, Optional, Dict, Set
from collections import Counter
from itertools import combinations

from shared_types import Card, CardValue, Suit, PlayType


class DoudizhuAI:
    """斗地主AI决策类"""
    
    _seen_cards: Set[CardValue] = set()
    
    @staticmethod
    def reset_seen_cards():
        """重置已记录已出之牌"""
        DoudizhuAI._seen_cards.clear()
    
    @staticmethod
    def record_played_cards(cards: List[Card]):
        """记录已出的牌"""
        for card in cards:
            DoudizhuAI._seen_cards.add(card.value)
    
    @staticmethod
    def get_remaining_count(card_value: CardValue, player_cards: List[Card]) -> int:
        """估算某牌值的剩余数量"""
        total_in_deck = 4
        if card_value in [CardValue.SMALL_JOKER, CardValue.BIG_JOKER]:
            total_in_deck = 1
        seen = DoudizhuAI._seen_cards.count(card_value)
        in_hand = sum(1 for c in player_cards if c.value == card_value)
        return total_in_deck - seen - in_hand
    
    @staticmethod
    def get_best_move(player_cards: List[Card], table_cards: List[Card], 
                      is_landlord: bool, opponent_count: int,
                      landlord_id: Optional[int] = None, 
                      player_id: Optional[int] = None,
                      player_positions: Optional[Dict[int, int]] = None) -> List[Card]:
        """
        获取AI的最佳出牌决策（完整版）
        
        整合ruru.txt的所有策略：
        - 主动出牌策略：基础牌型权重(W₁)、手牌优化权重(W₂)、威胁度权重(W₃)、
                        控场能力权重(W₄)、位置策略权重(W₅)、主动出牌优先级
        - 跟牌响应策略：跟牌质量因子(Q₁)、手牌破坏因子(Q₂)、控场因子(Q₃)
        - 特殊局面处理：残局策略(≤5张)、炸弹使用策略、记牌与推测策略
        
        Args:
            player_cards: AI玩家的手牌
            table_cards: 桌面上的牌（当前需要跟牌的牌）
            is_landlord: AI是否是地主
            opponent_count: 对手数量
            landlord_id: 地主玩家ID
            player_id: 当前玩家ID
            player_positions: 玩家位置映射 {玩家ID: 位置} 0=上家, 1=对家, 2=下家
        """
        if not player_cards:
            return []
        
        position = DoudizhuAI._get_position_info(landlord_id, player_id, player_positions)
        
        all_moves = DoudizhuAI.get_all_playable_moves(player_cards)
        
        if not table_cards:
            return DoudizhuAI._choose_initiative_move(
                all_moves, player_cards, is_landlord, position
            )
        
        valid_moves = [m for m in all_moves if DoudizhuAI.is_valid_play(m, table_cards)]
        
        if not valid_moves:
            return []
        
        result = DoudizhuAI._choose_follow_move(
            valid_moves, table_cards, player_cards, 
            is_landlord, opponent_count,
            landlord_id, player_id, player_positions
        )
        
        if result and DoudizhuAI.is_valid_play(result, table_cards):
            return result
        return []
    
    @staticmethod
    def _get_position_info(landlord_id: Optional[int], player_id: Optional[int],
                          player_positions: Optional[Dict[int, int]]) -> str:
        """获取位置信息"""
        if landlord_id is None or player_id is None or player_positions is None:
            return "unknown"
        
        if player_id == landlord_id:
            return "landlord"
        
        if player_positions.get(player_id) == 0:
            return "landlord_up"  # 地主上家
        elif player_positions.get(player_id) == 2:
            return "landlord_down"  # 地主下家
        return "partner"
    
    @staticmethod
    def _calculate_base_weight(play_type: PlayType, cards: List[Card]) -> float:
        """计算基础牌型权重 W₁"""
        values = [c.value for c in cards]
        max_value = max(values, key=lambda v: v.value)
        max_point = max_value.value
        
        weights = {
            PlayType.SINGLE: 0.5 + (max_point - 3) * 0.1,
            PlayType.PAIR: 1.0 + (max_point - 3) * 0.15,
            PlayType.TRIO: 2.0,
            PlayType.TRIO_SINGLE: 1.5 + (max_point - 3) * 0.15,
            PlayType.TRIO_PAIR: 2.0 + (max_point - 3) * 0.15,
            PlayType.STRAIGHT: 3.0 + (len(cards) - 5) * 0.5,
            PlayType.PAIR_STRAIGHT: 3.5 + (len(cards) // 2 - 3) * 1.0,
            PlayType.PLANE: 4.0 + (len(cards) // 3 - 2) * 1.5,
            PlayType.PLANE_SINGLE: 3.5 + (len(cards) // 4 - 2) * 1.2,
            PlayType.PLANE_PAIR: 4.0 + (len(cards) // 5 - 2) * 1.3,
            PlayType.FOUR_WITH_TWO: 4.5,
            PlayType.BOMB: 8.0,
            PlayType.ROCKET: 10.0,
        }
        return weights.get(play_type, 1.0)
    
    @staticmethod
    def _calculate_follow_quality_factor(move: List[Card], table_cards: List[Card]) -> float:
        """计算跟牌质量因子 Q₁
        
        Q₁ = 2.0 - min(跟牌点数 - 上家点数, 5) × 0.4
        刚好大1-2点：1.6-2.0
        大很多：0-1.2
        """
        _, table_value = DoudizhuAI._analyze_play(table_cards)
        _, move_value = DoudizhuAI._analyze_play(move)
        
        diff = move_value.value - table_value.value
        if diff <= 0:
            return 0.0
        if diff <= 2:
            return 2.0 - diff * 0.2
        return max(0.0, 2.0 - (diff - 2) * 0.4)
    
    @staticmethod
    def _count_combinations(cards: List[Card]) -> int:
        """计算手牌的组合数（分解为最小出牌单元）"""
        if not cards:
            return 0
        
        counts = Counter(c.value for c in cards)
        combinations = 0
        
        for value, count in counts.items():
            if value in [CardValue.SMALL_JOKER, CardValue.BIG_JOKER]:
                combinations += count
            elif count == 4:
                combinations += 1
            elif count == 3:
                combinations += 1
            elif count == 2:
                combinations += 1
            elif count == 1:
                combinations += 1
        
        pair_count = sum(1 for c in counts.values() if c >= 2)
        single_count = sum(1 for c in counts.values() if c == 1)
        
        trio_count = sum(1 for c in counts.values() if c >= 3)
        for _ in range(trio_count):
            remaining = [c for c in cards if c.value not in 
                        [v for v, cnt in counts.items() if cnt >= 3]]
            pair_vals = [v for v, cnt in Counter(c.value for c in remaining).items() if cnt >= 2]
            single_vals = [v for v, cnt in Counter(c.value for c in remaining).items() if cnt == 1]
            
            has_plane = False
            if len(pair_vals) >= 2:
                sorted_pairs = sorted(pair_vals, key=lambda v: v.value)
                for i in range(len(sorted_pairs) - 1):
                    if sorted_pairs[i+1].value == sorted_pairs[i].value + 1:
                        has_plane = True
                        break
            
            if has_plane:
                continue
            break
        
        straight_possible = True
        if len(cards) >= 5:
            valid_vals = [v for v in counts.keys() 
                         if v.value < CardValue.TWO.value 
                         and v not in [CardValue.SMALL_JOKER, CardValue.BIG_JOKER]]
            sorted_vals = sorted(valid_vals, key=lambda v: v.value)
            for i in range(len(sorted_vals) - 1):
                if sorted_vals[i+1].value != sorted_vals[i].value + 1:
                    straight_possible = False
                    break
            if straight_possible and len(sorted_vals) >= 5:
                return 1
        
        pair_straight_possible = True
        pair_vals = [v for v, cnt in counts.items() if cnt >= 2 
                    and v.value < CardValue.TWO.value]
        if len(pair_vals) >= 3:
            sorted_pairs = sorted(pair_vals, key=lambda v: v.value)
            for i in range(len(sorted_pairs) - 1):
                if sorted_pairs[i+1].value != sorted_pairs[i].value + 1:
                    pair_straight_possible = False
                    break
            if pair_straight_possible:
                return len(sorted_pairs)
        
        return len([c for c in counts.values() if c > 0])
    
    @staticmethod
    def _calculate_hand_optimization_weight(cards: List[Card], move: List[Card], 
                                            current_combinations: int) -> float:
        """计算手牌优化权重 W₂"""
        remaining = [c for c in cards if c not in move]
        new_combinations = DoudizhuAI._count_combinations(remaining)
        return (current_combinations - new_combinations) * 2.0
    
    @staticmethod
    def _calculate_threat_weight(remaining_cards: int, is_landlord: bool) -> float:
        """计算威胁度权重 W₃"""
        role_coef = 1.2 if is_landlord else 0.8
        return 10.0 / (remaining_cards + 1) * role_coef
    
    @staticmethod
    def _calculate_control_weight(move: List[Card], table_cards: List[Card],
                                   opponent_count: int) -> float:
        """计算控场能力权重 W₄"""
        if not table_cards:
            return 0.0
        
        weight = 0.0
        play_type, _ = DoudizhuAI._analyze_play(move)
        
        if play_type in [PlayType.STRAIGHT, PlayType.PAIR_STRAIGHT]:
            if len(move) >= 6:
                weight += 3.0
        
        if play_type == PlayType.BOMB:
            if opponent_count >= 2:
                weight += 2.0
        
        return weight
    
    @staticmethod
    def _calculate_position_weight(move: List[Card], is_landlord: bool, 
                                   position: str) -> float:
        """计算位置策略权重 W₅"""
        if is_landlord:
            values = [c.value for c in move]
            max_value = max(values, key=lambda v: v.value)
            max_point = max_value.value
            
            if len(move) == 1 and max_point <= 10:
                return 1.5
            elif len(move) == 2 and values[0] == values[1] and max_point <= 8:
                return 1.0
            if max_value in [CardValue.TWO, CardValue.SMALL_JOKER, CardValue.BIG_JOKER]:
                return 0.5
        else:
            values = [c.value for c in move]
            max_value = max(values, key=lambda v: v.value)
            max_point = max_value.value
            
            if position == "landlord_up":
                if max_point >= 11:
                    return 2.0
            elif position == "landlord_down":
                if max_point <= 10:
                    return 1.5
        
        return 0.0
    
    @staticmethod
    def _calculate_endgame_weight(move: List[Card], player_cards: List[Card],
                                   is_landlord: bool) -> float:
        """计算残局权重（手牌≤5张）
        
        公式：残局权重 = 基础权重 × 2 + 出完概率 × 5
        """
        if len(player_cards) > 5:
            return 0.0
        
        base_type, base_value = DoudizhuAI._analyze_play(move)
        base_weight = DoudizhuAI._calculate_base_weight(base_type, move) * 2.0
        
        remaining = [c for c in player_cards if c not in move]
        
        if len(remaining) == 0:
            finish_prob = 1.0
        elif len(remaining) <= 2:
            max_card = max(remaining, key=lambda c: c.value.value)
            if max_card.value in [CardValue.TWO, CardValue.SMALL_JOKER, CardValue.BIG_JOKER]:
                finish_prob = 0.9
            elif max_card.value.value >= 11:
                finish_prob = 0.7
            else:
                finish_prob = 0.5
        else:
            max_card = max(remaining, key=lambda c: c.value.value)
            if max_card.value in [CardValue.TWO, CardValue.SMALL_JOKER, CardValue.BIG_JOKER]:
                finish_prob = 0.6
            elif max_card.value.value >= 11:
                finish_prob = 0.4
            else:
                finish_prob = 0.2
        
        if not is_landlord:
            finish_prob *= 0.8
        
        return base_weight + finish_prob * 5.0
    
    @staticmethod
    def _should_use_bomb(move: List[Card], player_cards: List[Card],
                         is_landlord: bool, opponent_count: int,
                         game_state: Optional[Dict] = None) -> bool:
        """判断是否应该使用炸弹
        
        使用炸弹的触发条件（满足任一）：
        1. 能直接获胜时
        2. 阻止地主走完且农民有获胜可能时
        3. 对手出炸弹后，自己有更大炸弹且能收回控制权时
        4. 手牌很好，用炸弹获得出牌权后能走完时
        """
        if not move:
            return False
        
        play_type, _ = DoudizhuAI._analyze_play(move)
        if play_type != PlayType.BOMB and play_type != PlayType.ROCKET:
            return False
        
        remaining = [c for c in player_cards if c not in move]
        
        if len(remaining) == 0:
            return True
        
        if is_landlord:
            if len(remaining) <= 3:
                return True
            bomb_count = sum(1 for c in remaining if DoudizhuAI._analyze_play([c])[0] == PlayType.BOMB)
            if bomb_count >= 1 and len(remaining) <= 5:
                return True
        else:
            if len(remaining) <= 2:
                return True
        
        if game_state:
            last_played = game_state.get('last_player_id')
            opponent_played_bomb = game_state.get('opponent_played_bomb', False)
            if opponent_played_bomb and play_type == PlayType.BOMB:
                if play_type == PlayType.ROCKET:
                    return True
                my_other_bombs = [c for c in remaining 
                                 if DoudizhuAI._analyze_play([c])[0] == PlayType.BOMB]
                if my_other_bombs:
                    my_bomb_value = DoudizhuAI._analyze_play(move)[1]
                    other_bomb_value = DoudizhuAI._analyze_play(my_other_bombs[0])[1]
                    if other_bomb_value.value > my_bomb_value.value:
                        return True
        
        return False
    
    @staticmethod
    def _get_bomb_retention_weight(card_value: CardValue) -> float:
        """获取炸弹保留权重
        
        王炸：保留权重+4.0
        2炸：保留权重+3.0
        A炸：保留权重+2.5
        其他炸：保留权重+2.0
        """
        if card_value in [CardValue.SMALL_JOKER, CardValue.BIG_JOKER]:
            return 4.0
        elif card_value == CardValue.TWO:
            return 3.0
        elif card_value.value >= 14:
            return 2.5
        return 2.0
    
    @staticmethod
    def _calculate_danger_level(seen_cards: Set[CardValue], player_cards: List[Card]) -> float:
        """计算危险等级
        
        危险等级 = (对手可能炸弹数) × 3 + (对手可能大牌数) × 1
        """
        danger = 0.0
        
        card_counts = Counter(c.value for c in player_cards)
        
        potential_bomb_count = 0
        for value, count in card_counts.items():
            if value not in [CardValue.SMALL_JOKER, CardValue.BIG_JOKER]:
                if value not in seen_cards:
                    if count == 4:
                        potential_bomb_count += 1
                    elif count == 3:
                        potential_bomb_count += 0.5
        
        big_cards = [CardValue.TWO, CardValue.ACE, CardValue.KING, 
                    CardValue.QUEEN, CardValue.JACK]
        potential_big_count = sum(1 for v in big_cards if v not in seen_cards)
        
        danger = potential_bomb_count * 3 + potential_big_count * 1
        
        return danger
    
    @staticmethod
    def _can_finish_in_one_round(player_cards: List[Card]) -> bool:
        """判断能否一手走完"""
        if not player_cards:
            return False
        
        if len(player_cards) == 1:
            return True
        
        all_moves = DoudizhuAI.get_all_playable_moves(player_cards)
        for move in all_moves:
            if len(move) == len(player_cards):
                return True
        
        return False
    
    @staticmethod
    def _calculate_control_weight_v2(move: List[Card], table_cards: List[Card],
                                     opponent_count: int, seen_cards: Set[CardValue]) -> float:
        """计算控场能力权重 W₄（增强版）
        
        情况	权重	说明
        出牌后对手可能无同牌型	+3.0	出长顺子、连对等
        出牌能逼出对手大牌	+2.0	出中等偏大牌
        出牌会暴露手牌结构	-1.5	避免过早暴露
        """
        if not table_cards:
            return 0.0
        
        weight = 0.0
        play_type, play_value = DoudizhuAI._analyze_play(move)
        
        if play_type in [PlayType.STRAIGHT, PlayType.PAIR_STRAIGHT]:
            if len(move) >= 6:
                weight += 3.0
        
        if play_type == PlayType.BOMB:
            if opponent_count >= 2:
                weight += 2.0
        
        if play_type == PlayType.TRIO and len(move) == 3:
            potential_opponent_counter = 0
            for seen in seen_cards:
                if play_value.value - seen.value <= 2 and play_value.value - seen.value > 0:
                    potential_opponent_counter += 1
            if potential_opponent_counter >= 2:
                weight += 2.0
        
        if play_type in [PlayType.STRAIGHT, PlayType.PLANE]:
            if len(move) >= 6:
                remaining_after_move = [c for c in move 
                                       if c.value not in [c.value for c in move]]
                weight += 1.0
        
        return weight
    
    @staticmethod
    def _get_initiative_priority_weight(move: List[Card], player_cards: List[Card],
                                        is_landlord: bool) -> float:
        """计算主动出牌优先级权重
        
        优先级规则：
        - 必胜出牌：能直接走完的手牌（权重+∞）
        - 清理小牌：最小单牌/对子（权重：单牌1.2，对子1.5）
        - 试探出牌：中等牌力牌型（权重：1.8-2.5）
        - 组合出牌：减少手牌组合数（权重：2.0-4.0）
        - 控场出牌：根据角色定位调整
        """
        priority_weight = 0.0
        
        if DoudizhuAI._can_finish_in_one_round(player_cards):
            return float('inf')
        
        play_type, play_value = DoudizhuAI._analyze_play(move)
        remaining = [c for c in player_cards if c not in move]
        
        if play_type == PlayType.SINGLE:
            if play_value.value <= 10:
                priority_weight += 1.2
        
        if play_type == PlayType.PAIR:
            if play_value.value <= 8:
                priority_weight += 1.5
        
        if play_type == PlayType.TRIO:
            priority_weight += 1.8
        
        if play_type in [PlayType.TRIO_SINGLE, PlayType.TRIO_PAIR]:
            priority_weight += 2.0
        
        if play_type in [PlayType.STRAIGHT, PlayType.PAIR_STRAIGHT, PlayType.PLANE]:
            priority_weight += 3.0
        
        if play_type == PlayType.BOMB:
            priority_weight += 4.0
        
        if play_type == PlayType.ROCKET:
            priority_weight += 5.0
        
        if len(remaining) <= 5:
            priority_weight += 2.0
        
        return priority_weight
    
    @staticmethod
    def _choose_initiative_move(moves: List[List[Card]], player_cards: List[Card],
                                is_landlord: bool,
                                position: str = "landlord") -> List[Card]:
        """主动出牌策略（增强版）
        
        整合ruru.txt的所有策略：
        1. 基础牌型权重（W₁）
        2. 手牌优化权重（W₂）
        3. 威胁度权重（W₃）
        4. 控场能力权重（W₄）
        5. 位置策略权重（W₅）
        6. 主动出牌优先级权重
        """
        if not moves:
            return []
        
        if len(player_cards) == 1:
            return DoudizhuAI._play_smallest_card(player_cards)
        
        for move in moves:
            play_type, _ = DoudizhuAI._analyze_play(move)
            if play_type == PlayType.ROCKET:
                return move
        
        for move in moves:
            play_type, _ = DoudizhuAI._analyze_play(move)
            if play_type == PlayType.BOMB:
                if DoudizhuAI._should_use_bomb(move, player_cards, is_landlord, 2):
                    return move
        
        current_combinations = DoudizhuAI._count_combinations(player_cards)
        best_move = []
        best_weight = float('-inf')
        
        for move in moves:
            if not move:
                continue
            
            play_type, _ = DoudizhuAI._analyze_play(move)
            
            w1 = DoudizhuAI._calculate_base_weight(play_type, move)
            w2 = DoudizhuAI._calculate_hand_optimization_weight(player_cards, move, current_combinations)
            w3 = DoudizhuAI._calculate_threat_weight(len(player_cards) - len(move), is_landlord)
            w4 = DoudizhuAI._calculate_control_weight_v2(move, [], 2, DoudizhuAI._seen_cards)
            w5 = DoudizhuAI._calculate_position_weight(move, is_landlord, position)
            priority = DoudizhuAI._get_initiative_priority_weight(move, player_cards, is_landlord)
            
            total_weight = w1 + w2 + w3 + w4 + w5 + priority
            
            if total_weight > best_weight:
                best_weight = total_weight
                best_move = move
        
        if not best_move:
            return DoudizhuAI._play_smallest_card(player_cards)
        
        # 确保返回的牌是有效的，否则返回空列表（不出牌）
        if best_move and DoudizhuAI.is_valid_play(best_move, []):
            return best_move
        return []
    
    @staticmethod
    def _calculate_skip_weight(is_landlord: bool, position: str,
                                table_type: Optional[PlayType], 
                                partner_card_count: Optional[int],
                                my_card_count: int,
                                has_big_cards: bool) -> float:
        """计算不出牌的权重 W_pass
        
        公式：W_pass = 基础值 + 角色调整 + 局势调整
        基础值：同伴出牌+3.0，地主出牌+1.0
        角色调整：地主下家对地主出牌+1.5，地主上家对地主出牌-1.0
        局势调整：同伴牌少+2.0，自己牌多+1.0，有大牌可留+1.5
        """
        weight = 0.0
        
        if is_landlord:
            weight += 1.0
        else:
            weight += 3.0
        
        if position == "landlord_down":
            weight += 1.5
        elif position == "landlord_up":
            weight -= 1.0
        
        if partner_card_count is not None and partner_card_count <= 3:
            weight += 2.0
        
        if my_card_count >= 10:
            weight += 1.0
        
        if has_big_cards:
            weight += 1.5
        
        return weight
    
    @staticmethod
    def _calculate_destruction_factor(move: List[Card], player_cards: List[Card]) -> float:
        """计算手牌破坏因子 Q₂
        
        Q₂ = (破坏重要组合数) × (-1.5)
        重要组合：炸弹、三张、顺子组件
        """
        move_values = set(c.value for c in move)
        remaining = [c for c in player_cards if c.value not in move_values]
        remaining_counts = Counter(c.value for c in remaining)
        
        destruction = 0
        for value, count in remaining_counts.items():
            if count >= 4:
                destruction += 1
            elif count == 3:
                destruction += 0.5
        
        return destruction * (-1.5)
    
    @staticmethod
    def _calculate_follow_control_factor(move: List[Card], player_cards: List[Card],
                                          opponent_count: int) -> float:
        """计算控场因子 Q₃
        
        情况	权重
        跟牌后获得出牌权	+2.0
        逼出对手炸弹	+1.5
        阻止对手报单	+3.0
        """
        weight = 0.0
        remaining = len(player_cards) - len(move)
        
        if remaining == 0:
            weight += 5.0
        elif remaining <= 2:
            weight += 2.0
        
        return weight
    
    @staticmethod
    def _choose_follow_move(valid_moves: List[List[Card]], table_cards: List[Card],
                            player_cards: List[Card], is_landlord: bool,
                            opponent_count: int,
                            landlord_id: Optional[int], 
                            player_id: Optional[int],
                            player_positions: Optional[Dict[int, int]]) -> List[Card]:
        """跟牌响应策略（增强版）
        
        整合ruru.txt的跟牌策略：
        1. 优先火箭和炸弹
        2. 残局特殊处理
        3. 跟牌质量因子 Q₁
        4. 手牌破坏因子 Q₂
        5. 控场因子 Q₃
        """
        position = DoudizhuAI._get_position_info(landlord_id, player_id, player_positions)
        
        for move in valid_moves:
            play_type, _ = DoudizhuAI._analyze_play(move)
            if play_type == PlayType.ROCKET:
                return move
        
        for move in valid_moves:
            play_type, _ = DoudizhuAI._analyze_play(move)
            if play_type == PlayType.BOMB:
                if DoudizhuAI._should_use_bomb(move, player_cards, is_landlord, opponent_count):
                    return move
        
        if len(player_cards) <= 5:
            return DoudizhuAI._choose_endgame_move(valid_moves, player_cards, is_landlord)
        
        has_big_cards = any(c.value in [CardValue.TWO, CardValue.SMALL_JOKER, CardValue.BIG_JOKER]
                           for c in player_cards)
        
        partner_count = None
        
        q1_scores = []
        for move in valid_moves:
            q1 = DoudizhuAI._calculate_follow_quality_factor(move, table_cards)
            q2 = DoudizhuAI._calculate_destruction_factor(move, player_cards)
            q3 = DoudizhuAI._calculate_follow_control_factor(move, player_cards, opponent_count)
            
            total_q = q1 + q2 + q3
            q1_scores.append((move, total_q, q1))
        
        q1_scores.sort(key=lambda x: x[1], reverse=True)
        
        if q1_scores:
            best = q1_scores[0]
            if best[1] > 0:
                return best[0]
        
        # 确保返回的牌是有效的，否则返回空列表（不出牌）
        smallest = DoudizhuAI._play_smallest_card(player_cards)
        if smallest and DoudizhuAI.is_valid_play(smallest, table_cards):
            return smallest
        return []
    
    @staticmethod
    def _choose_endgame_move(moves: List[List[Card]], player_cards: List[Card],
                             is_landlord: bool) -> List[Card]:
        """残局策略（手牌≤5张）- 增强版
        
        使用残局权重公式：残局权重 = 基础权重 × 2 + 出完概率 × 5
        """
        if not moves:
            return []
        
        for move in moves:
            play_type, _ = DoudizhuAI._analyze_play(move)
            if play_type == PlayType.ROCKET:
                return move
        
        for move in moves:
            play_type, _ = DoudizhuAI._analyze_play(move)
            if play_type == PlayType.BOMB:
                if DoudizhuAI._should_use_bomb(move, player_cards, is_landlord, 2):
                    return move
        
        best_move = []
        best_weight = float('-inf')
        
        for move in moves:
            if not move:
                continue
            
            weight = DoudizhuAI._calculate_endgame_weight(move, player_cards, is_landlord)
            
            if weight > best_weight:
                best_weight = weight
                best_move = move
        
        if not best_move:
            return DoudizhuAI._play_smallest_card(player_cards)
        
        return best_move
    
    @staticmethod
    def get_all_playable_moves(cards: List[Card]) -> List[List[Card]]:
        """获取所有可能的出牌方式"""
        moves = []
        
        if not cards:
            return [[]]
        
        moves.append([])
        
        for card in cards:
            moves.append([card])
        
        for value in DoudizhuAI._get_repeated_values(cards, 2):
            card_list = [c for c in cards if c.value == value]
            if len(card_list) >= 2:
                moves.append(card_list[:2])
        
        for value in DoudizhuAI._get_repeated_values(cards, 3):
            card_list = [c for c in cards if c.value == value]
            if len(card_list) >= 3:
                moves.append(card_list[:3])
        
        for value in DoudizhuAI._get_repeated_values(cards, 4):
            card_list = [c for c in cards if c.value == value]
            if len(card_list) == 4:
                moves.append(card_list)
        
        trio_values = list(DoudizhuAI._get_repeated_values(cards, 3))
        
        for value in trio_values:
            trio_cards = [c for c in cards if c.value == value]
            if len(trio_cards) >= 3:
                remaining = [c for c in cards if c.value != value]
                for single in remaining:
                    moves.append(trio_cards[:3] + [single])
                
                pair_values = {v for v in DoudizhuAI._get_repeated_values(cards, 2) if v != value}
                for pair_val in pair_values:
                    pair_cards = [c for c in cards if c.value == pair_val]
                    moves.append(trio_cards[:3] + pair_cards[:2])
        
        moves.extend(DoudizhuAI._get_straights(cards))
        moves.extend(DoudizhuAI._get_pair_straights(cards))
        moves.extend(DoudizhuAI._get_planes(cards))
        moves.extend(DoudizhuAI._get_plane_with_wings(cards))
        
        has_small = any(c.value == CardValue.SMALL_JOKER for c in cards)
        has_big = any(c.value == CardValue.BIG_JOKER for c in cards)
        if has_small and has_big:
            small = next(c for c in cards if c.value == CardValue.SMALL_JOKER)
            big = next(c for c in cards if c.value == CardValue.BIG_JOKER)
            moves.append([small, big])
        
        return moves
    
    @staticmethod
    def _get_repeated_values(cards: List[Card], count: int) -> set:
        """获取重复的卡牌值"""
        value_counts = Counter(card.value for card in cards)
        return {value for value, cnt in value_counts.items() if cnt >= count}
    
    @staticmethod
    def _get_straights(cards: List[Card], min_length: int = 5) -> List[List[Card]]:
        """获取所有可能的单顺"""
        sequences = []
        valid_values = [v for v in CardValue 
                       if v.value < CardValue.TWO.value 
                       and v != CardValue.SMALL_JOKER 
                       and v != CardValue.BIG_JOKER]
        
        sorted_cards = sorted([c for c in cards if c.value in valid_values], 
                             key=lambda c: c.value.value)
        
        if len(sorted_cards) < min_length:
            return sequences
        
        value_list = [c.value for c in sorted_cards]
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
                    card_list = []
                    for v in straight_values:
                        card = next(c for c in cards if c.value == v)
                        card_list.append(card)
                    sequences.append(card_list)
        
        return sequences
    
    @staticmethod
    def _get_pair_straights(cards: List[Card], min_pairs: int = 3) -> List[List[Card]]:
        """获取所有可能的双顺"""
        sequences = []
        pair_values = sorted(list(DoudizhuAI._get_repeated_values(cards, 2)), key=lambda v: v.value)
        
        if len(pair_values) < min_pairs:
            return sequences
        
        n = len(pair_values)
        for length in range(min_pairs, n + 1):
            for start in range(0, n - length + 1):
                straight_values = pair_values[start:start + length]
                if all(pair_values[start + i].value == pair_values[start].value + i 
                      for i in range(length)):
                    card_list = []
                    for v in straight_values:
                        card = [c for c in cards if c.value == v][:2]
                        card_list.extend(card)
                    sequences.append(card_list)
        
        return sequences
    
    @staticmethod
    def _get_planes(cards: List[Card], min_groups: int = 2) -> List[List[Card]]:
        """获取所有可能的飞机（纯飞机）"""
        planes = []
        trio_values = sorted(list(DoudizhuAI._get_repeated_values(cards, 3)), key=lambda v: v.value)
        
        if len(trio_values) < min_groups:
            return planes
        
        n = len(trio_values)
        for length in range(min_groups, n + 1):
            for start in range(0, n - length + 1):
                plane_values = trio_values[start:start + length]
                if all(trio_values[start + i].value == trio_values[start].value + i 
                      for i in range(length)):
                    card_list = []
                    for v in plane_values:
                        card = [c for c in cards if c.value == v][:3]
                        card_list.extend(card)
                    planes.append(card_list)
        
        return planes
    
    @staticmethod
    def _get_plane_with_wings(cards: List[Card]) -> List[List[Card]]:
        """获取所有可能的飞机带翅膀"""
        planes = []
        trio_values = sorted(list(DoudizhuAI._get_repeated_values(cards, 3)), key=lambda v: v.value)
        
        for trio_count in range(2, len(trio_values) + 1):
            for start in range(0, len(trio_values) - trio_count + 1):
                plane_values = trio_values[start:start + trio_count]
                if all(trio_values[start + i].value == trio_values[start].value + i 
                      for i in range(trio_count)):
                    trio_cards = []
                    for v in plane_values:
                        card = [c for c in cards if c.value == v][:3]
                        trio_cards.extend(card)
                    
                    remaining = [c for c in cards if c.value not in plane_values]
                    
                    single_count = trio_count
                    if len(remaining) >= single_count:
                        for singles in combinations(remaining, single_count):
                            planes.append(list(trio_cards) + list(singles))
                    
                    pair_values = sorted([v for v in DoudizhuAI._get_repeated_values(cards, 2) 
                                         if v not in plane_values], key=lambda v: v.value)
                    if len(pair_values) >= trio_count and len(remaining) >= trio_count * 2:
                        for i in range(len(pair_values) - trio_count + 1):
                            selected_pairs = pair_values[i:i + trio_count]
                            pair_cards = []
                            for v in selected_pairs:
                                pair_cards.extend([c for c in cards if c.value == v][:2])
                            planes.append(list(trio_cards) + pair_cards)
        
        return planes
    
    @staticmethod
    def is_valid_play(cards: List[Card], table_cards: List[Card]) -> bool:
        """检查出牌是否合法"""
        if not cards:
            return True
        
        if not table_cards:
            return True
        
        play_type, play_value = DoudizhuAI._analyze_play(cards)
        table_type, table_value = DoudizhuAI._analyze_play(table_cards)
        
        if play_type == PlayType.ROCKET:
            return True
        
        if table_type == PlayType.ROCKET:
            return False
        
        if play_type == PlayType.BOMB:
            if table_type == PlayType.BOMB:
                return play_value.value > table_value.value
            return True
        
        if play_type != table_type:
            return False
        
        if len(cards) != len(table_cards):
            return False
        
        return play_value.value > table_value.value
    
    @staticmethod
    def _analyze_play(cards: List[Card]) -> tuple:
        """分析牌型并返回(牌型, 牌型值)"""
        if not cards:
            return PlayType.SINGLE, CardValue.THREE
        
        if len(cards) == 1:
            return PlayType.SINGLE, cards[0].value
        
        if len(cards) == 2:
            if cards[0].value == cards[1].value:
                return PlayType.PAIR, cards[0].value
            
            has_small = any(c.value == CardValue.SMALL_JOKER for c in cards)
            has_big = any(c.value == CardValue.BIG_JOKER for c in cards)
            if has_small and has_big:
                return PlayType.ROCKET, CardValue.BIG_JOKER
        
        values = [c.value for c in cards]
        value_counts = Counter(values)
        
        if len(cards) == 4 and 4 in value_counts.values():
            return PlayType.BOMB, max(values, key=lambda v: v.value)
        
        if 3 in value_counts.values():
            trio_value = [v for v, cnt in value_counts.items() if cnt >= 3][0]
            trio_count = value_counts[trio_value]
            
            if len(cards) == 3:
                return PlayType.TRIO, trio_value
            
            if len(cards) == 4 and trio_count + 1 == len(cards):
                return PlayType.TRIO_SINGLE, trio_value
            
            if len(cards) == 5:
                others = [cnt for k, cnt in value_counts.items() if k != trio_value]
                if sorted(others) == [2]:
                    return PlayType.TRIO_PAIR, trio_value
                if sorted(others) == [1, 1]:
                    return PlayType.TRIO_SINGLE, trio_value
        
        if 2 in value_counts.values() and len(cards) >= 6:
            pair_values = sorted([v for v, cnt in value_counts.items() if cnt >= 2], 
                                key=lambda v: v.value)
            is_straight = all(pair_values[i].value == pair_values[0].value + i 
                            for i in range(len(pair_values)))
            if is_straight and len(pair_values) >= 3:
                if len(pair_values) * 2 == len(cards):
                    return PlayType.PAIR_STRAIGHT, pair_values[-1]
        
        single_vals = sorted([v for v in values if value_counts[v] == 1], 
                            key=lambda v: v.value)
        if len(single_vals) >= 5 and len(single_vals) == len(cards):
            is_straight = all(single_vals[i].value == single_vals[0].value + i 
                            for i in range(len(single_vals)))
            if is_straight:
                return PlayType.STRAIGHT, single_vals[-1]
        
        if 3 in value_counts.values():
            trio_values = sorted([v for v, cnt in value_counts.items() if cnt >= 3], 
                                key=lambda v: v.value)
            is_plane = all(trio_values[i].value == trio_values[0].value + i 
                          for i in range(len(trio_values)))
            
            if is_plane:
                wing_count = len(cards) - len(trio_values) * 3
                if wing_count == 0:
                    return PlayType.PLANE, trio_values[-1]
                
                if wing_count == len(trio_values):
                    wing_values = sorted([v for v in values if value_counts[v] == 1], 
                                        key=lambda v: v.value)
                    if len(wing_values) == wing_count:
                        return PlayType.PLANE_SINGLE, trio_values[-1]
                
                if wing_count == len(trio_values) * 2:
                    pair_wing_values = sorted([v for v in value_counts.items() if v[1] >= 2], 
                                             key=lambda x: x[0].value)
                    if len(pair_wing_values) == len(trio_values):
                        return PlayType.PLANE_PAIR, trio_values[-1]
        
        if len(cards) == 6 and 4 in value_counts.values():
            return PlayType.FOUR_WITH_TWO, max(values, key=lambda v: v.value)
        
        return PlayType.SINGLE, max(values, key=lambda v: v.value)
    
    @staticmethod
    def _play_smallest_card(cards: List[Card]) -> List[Card]:
        """出最小的牌"""
        if not cards:
            return []
        sorted_cards = sorted(cards, key=lambda c: (c.value.value, c.suit.value if c.suit else 0))
        return [sorted_cards[0]]
