import os
import json
import random
from treys import Evaluator, Card

_evaluator = Evaluator()
RANK_ORDER = "23456789TJQKA"


def _rank_val(r):
    return RANK_ORDER.index(r)


def bucket_preflop(hole_cards_str):
    ranks = sorted([c[0] for c in hole_cards_str], key=_rank_val, reverse=True)
    suited = hole_cards_str[0][1] == hole_cards_str[1][1]
    pair = ranks[0] == ranks[1]
    hi, lo = _rank_val(ranks[0]), _rank_val(ranks[1])
    gap = hi - lo

    if pair:
        if hi >= _rank_val('T'):
            return 'Premium'
        if hi >= _rank_val('7'):
            return 'Strong'
        return 'Playable'

    if hi == _rank_val('A'):
        if suited or lo >= _rank_val('J'):
            return 'Premium'
        if lo >= _rank_val('9') or suited:
            return 'Strong'
        return 'Playable'

    if hi == _rank_val('K'):
        if lo >= _rank_val('T') or (suited and lo >= _rank_val('8')):
            return 'Strong'
        if suited or lo >= _rank_val('8'):
            return 'Playable'
        return 'Marginal'

    if hi >= _rank_val('T'):
        if suited and gap <= 3:
            return 'Playable'
        if lo >= _rank_val('T'):
            return 'Playable'
        return 'Marginal'

    if suited and gap <= 2 and hi >= _rank_val('6'):
        return 'Marginal'

    return 'Trash'


def _has_flush_draw(all_cards):
    suits = [c[1] for c in all_cards]
    for s in set(suits):
        if suits.count(s) == 4:
            return True
    return False


def _has_oesd(all_cards):
    vals = sorted(set(_rank_val(c[0]) for c in all_cards))
    for i in range(len(vals) - 3):
        window = vals[i:i + 4]
        if window[-1] - window[0] == 3:
            return True
    return False


def bucket_postflop(hole_cards_str, board_cards_str):
    hole = [Card.new(c) for c in hole_cards_str]
    board = [Card.new(c) for c in board_cards_str]
    score = _evaluator.evaluate(board, hole)
    rank_class = _evaluator.get_rank_class(score)
    class_name = _evaluator.class_to_string(rank_class)

    if class_name in ('Straight Flush', 'Four of a Kind', 'Full House'):
        return 'Nuts'
    if class_name in ('Flush', 'Straight', 'Three of a Kind'):
        return 'Strong'
    if class_name == 'Two Pair':
        return 'TwoPair'
    if class_name == 'Pair':
        board_ranks = [_rank_val(c[0]) for c in board_cards_str]
        hole_ranks = [_rank_val(c[0]) for c in hole_cards_str]
        top_board = max(board_ranks) if board_ranks else -1
        if max(hole_ranks) >= top_board:
            return 'TopPair'
        return 'WeakPair'

    all_cards = hole_cards_str + board_cards_str
    if _has_flush_draw(all_cards) or _has_oesd(all_cards):
        return 'Drawing'
    return 'Weak'


def street_from_board(board_cards_str):
    return {0: 0, 3: 1, 4: 2, 5: 3}[len(board_cards_str)]


def abstract_state(hole_cards_str, board_cards_str, history):
    current_round = street_from_board(board_cards_str)
    if current_round == 0:
        bucket = bucket_preflop(hole_cards_str)
    else:
        bucket = bucket_postflop(hole_cards_str, board_cards_str)
    history_str = "".join(history[:current_round + 1])
    return f"{current_round}_{bucket}_{history_str}"


class TeamAK_UltimateCFR:
    def __init__(self):
        self.name = "TeamAK_Ultimate"
        current_dir = os.path.dirname(os.path.abspath(__file__))
        strategy_path = os.path.join(current_dir, "teamak_ultimate_strategy.json")
        try:
            with open(strategy_path, 'r') as f:
                self.strategy = json.load(f)
            print(f"[{self.name}] Successfully loaded {len(self.strategy)} info sets.")
        except Exception as e:
            self.strategy = {}
            print(f"[{self.name}] ERROR: Could not load strategy file: {e}")

    def get_action(self, state) -> str:
        if len(state.valid_actions) == 1:
            return state.valid_actions[0]

        info_set = abstract_state(state.my_cards, state.board_cards, state.history)

        if info_set in self.strategy:
            action_probs = self.strategy[info_set]
            valid_probs = {a: p for a, p in action_probs.items() if a in state.valid_actions}
            if valid_probs:
                total = sum(valid_probs.values())
                actions = list(valid_probs.keys())
                probs = [p / total for p in valid_probs.values()]
                return random.choices(actions, weights=probs, k=1)[0]

        if state.amount_to_call > 0:
            return random.choice(['c', 'f'])
        return random.choice(['r', 'c'])
