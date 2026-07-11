"""HULHE tournament agent: v3.1 CFR blueprint (canonical169 + texture-aware MC).

Shipped configuration:
- preflop abstraction: canonical 169 starting-hand classes
- postflop abstraction: MC equity + potential + board texture adjustment (K=16)
- strategy source: Allin_FTW_strategy.json (8M iters, 30% burn-in)
"""

import os
import json
import random
import bisect

from treys import Card, Evaluator

# =====================================================================
#  CARD ABSTRACTION  (must stay identical to training/abstraction.py)
# =====================================================================
PREFLOP_K = 169
POSTFLOP_K = 16
PREFLOP_MODE = "canonical169"
USE_BOARD_TEXTURE = True
MC_ROLLOUTS = 80
MC_SEED_SALT = 0xA1101

RANKS = "23456789TJQKA"
RANK_VAL = {r: i + 2 for i, r in enumerate(RANKS)}

_EVALUATOR = Evaluator()
_FULL_DECK = [Card.new(r + s) for r in RANKS for s in "shdc"]
_postflop_cache = {}


def _chen_base(rank_val):
    table = {14: 10.0, 13: 8.0, 12: 7.0, 11: 6.0}
    return table.get(rank_val, rank_val / 2.0)


def chen_score(hi, lo, suited):
    if hi == lo:
        return max(5.0, _chen_base(hi) * 2.0)
    score = _chen_base(hi)
    if suited:
        score += 2.0
    gap = hi - lo - 1
    if gap == 1:
        score -= 1.0
    elif gap == 2:
        score -= 2.0
    elif gap == 3:
        score -= 4.0
    elif gap >= 4:
        score -= 5.0
    if gap <= 1 and hi < 12:
        score += 1.0
    return score


def _all_canonical_scores():
    scores = []
    vals = list(range(2, 15))
    for i in range(len(vals)):
        for j in range(i, len(vals)):
            lo, hi = vals[i], vals[j]
            if hi == lo:
                scores.append(chen_score(hi, lo, False))
            else:
                scores.append(chen_score(hi, lo, True))
                scores.append(chen_score(hi, lo, False))
    return sorted(scores)


_CANON_SORTED = _all_canonical_scores()


def _build_canonical169_lookup():
    lookup = {}
    idx = 0
    for i in range(13):
        hi = i + 2
        lookup[(hi, hi, False)] = idx
        idx += 1
    for i in range(13):
        for j in range(i):
            hi, lo = i + 2, j + 2
            lookup[(hi, lo, True)] = idx
            idx += 1
            lookup[(hi, lo, False)] = idx
            idx += 1
    return lookup


_CANONICAL169 = _build_canonical169_lookup()


def _percentile_bucket(score, sorted_scores, k):
    rank = bisect.bisect_right(sorted_scores, score)
    frac = (rank - 0.5) / len(sorted_scores)
    return max(0, min(k - 1, int(frac * k)))


def canonical169_bucket(my_cards):
    v1, v2 = RANK_VAL[my_cards[0][0]], RANK_VAL[my_cards[1][0]]
    suited = my_cards[0][1] == my_cards[1][1]
    hi, lo = max(v1, v2), min(v1, v2)
    return _CANONICAL169[(hi, lo, suited)]


def preflop_bucket(my_cards, k=PREFLOP_K):
    if PREFLOP_MODE == "canonical169":
        return canonical169_bucket(my_cards)
    v1, v2 = RANK_VAL[my_cards[0][0]], RANK_VAL[my_cards[1][0]]
    suited = my_cards[0][1] == my_cards[1][1]
    hi, lo = max(v1, v2), min(v1, v2)
    return _percentile_bucket(chen_score(hi, lo, suited), _CANON_SORTED, k)


def _board_texture_adjust(board_cards, my_cards):
    if not USE_BOARD_TEXTURE or len(board_cards) < 3:
        return 0.0
    adj = 0.0
    suits = [c[1] for c in board_cards]
    ranks = [RANK_VAL[c[0]] for c in board_cards]
    if len(set(suits)) == 1:
        adj += 0.05
    if len(set(ranks)) < len(ranks):
        adj -= 0.04
    if max(ranks) >= 13:
        adj += 0.02
    my_suits = {c[1] for c in my_cards}
    if len(set(suits)) == 1 and my_suits & set(suits):
        adj += 0.03
    return adj


def _mc_equity(my_cards, board_cards, rollouts=MC_ROLLOUTS):
    hole = [Card.new(c) for c in my_cards]
    board = [Card.new(c) for c in board_cards]
    used = set(hole + board)
    remaining = [c for c in _FULL_DECK if c not in used]
    cards_needed = 5 - len(board)
    need_opp = 2

    seed = hash((my_cards[0], my_cards[1], tuple(board_cards), MC_SEED_SALT)) & 0xFFFFFFFF
    rng = random.Random(seed)

    wins = 0.0
    sq_sum = 0.0
    for _ in range(rollouts):
        sample = rng.sample(remaining, need_opp + cards_needed)
        opp = sample[:need_opp]
        runout = board + sample[need_opp:]
        my_rank = _EVALUATOR.evaluate(runout, hole)
        opp_rank = _EVALUATOR.evaluate(runout, opp)
        if my_rank < opp_rank:
            hs = 1.0
        elif my_rank == opp_rank:
            hs = 0.5
        else:
            hs = 0.0
        wins += hs
        sq_sum += hs * hs

    return wins / rollouts, sq_sum / rollouts


def postflop_bucket(my_cards, board_cards, k=POSTFLOP_K):
    cache_key = (my_cards[0], my_cards[1], tuple(board_cards), k, PREFLOP_MODE, USE_BOARD_TEXTURE)
    cached = _postflop_cache.get(cache_key)
    if cached is not None:
        return cached

    if len(board_cards) == 5:
        hole = [Card.new(c) for c in my_cards]
        board = [Card.new(c) for c in board_cards]
        rank = _EVALUATOR.evaluate(board, hole)
        strength = 1.0 - (rank - 1) / 7461.0
    else:
        eq, eq2 = _mc_equity(my_cards, board_cards)
        potential = max(0.0, eq2 - eq * eq)
        strength = min(1.0, eq + 0.35 * potential)
        strength = max(0.0, min(1.0, strength + _board_texture_adjust(board_cards, my_cards)))

    b = max(0, min(k - 1, int(strength * k)))
    if len(_postflop_cache) > 200_000:
        _postflop_cache.clear()
    _postflop_cache[cache_key] = b
    return b


def street_of(board_cards):
    return {0: 0, 3: 1, 4: 2, 5: 3}[len(board_cards)]


def bucket(my_cards, board_cards, preflop_k=PREFLOP_K, postflop_k=POSTFLOP_K):
    if len(board_cards) == 0:
        return preflop_bucket(my_cards, preflop_k)
    return postflop_bucket(my_cards, board_cards, postflop_k)


def info_key(my_cards, board_cards, history, preflop_k=PREFLOP_K, postflop_k=POSTFLOP_K):
    st = street_of(board_cards)
    b = bucket(my_cards, board_cards, preflop_k, postflop_k)
    return f"{st}|{b}|{'/'.join(history)}"


# =====================================================================
#  TOURNAMENT AGENT
# =====================================================================
class Allin_FTW:
    def __init__(self):
        self.name = "Allin_FTW"
        self.strategy = {}

        current_dir = os.path.dirname(os.path.abspath(__file__))
        strategy_path = os.path.join(current_dir, "Allin_FTW_strategy.json")
        try:
            with open(strategy_path, "r") as f:
                self.strategy = json.load(f)
        except Exception:
            self.strategy = {}

    def _blueprint(self, state):
        key = info_key(state.my_cards, state.board_cards, state.history)
        probs = self.strategy.get(key)
        if not probs:
            return None
        filtered = {a: p for a, p in probs.items() if a in state.valid_actions}
        total = sum(filtered.values())
        if total <= 0:
            return None
        return {a: p / total for a, p in filtered.items()}

    def _fallback_probs(self, state):
        b = bucket(state.my_cards, state.board_cards)
        k = PREFLOP_K if len(state.board_cards) == 0 else POSTFLOP_K
        if b >= k - 2:
            raw = {'r': 0.8, 'c': 0.2}
        elif b >= k // 2:
            raw = {'c': 0.8, 'r': 0.2}
        elif state.amount_to_call > 0:
            raw = {'f': 1.0}
        else:
            raw = {'c': 1.0}
        filtered = {a: p for a, p in raw.items() if a in state.valid_actions}
        total = sum(filtered.values())
        if total <= 0:
            return {a: 1.0 / len(state.valid_actions) for a in state.valid_actions}
        return {a: p / total for a, p in filtered.items()}

    def get_action(self, state):
        if len(state.valid_actions) == 1:
            return state.valid_actions[0]

        probs = self._blueprint(state)
        if probs is None:
            probs = self._fallback_probs(state)

        actions = list(probs.keys())
        weights = list(probs.values())
        return random.choices(actions, weights=weights, k=1)[0]
