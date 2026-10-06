"""Shared brew optimiser for the main run and the explore buttons."""

from __future__ import annotations

import math
import warnings

from pulp import COIN_CMD, LpInteger, LpMaximize, LpProblem, lpSum, value

# Order is the order shown on "Max of each item". The button solves the first
# batch immediately and the rest on a second click.
MAX_PER_ITEM_LOOT = [
    "Currency",
    "Skill Points",
    "Wildcards",
    "Crafting Shards",
    "Raid Cards",
    "Fortune Scroll",
    "Hero Weapons",
    "Clan Scroll",
]
MAX_PER_ITEM_FIRST_BATCH = 5
FRONTIER_POINTS = 5
FRONTIER_REFINEMENTS = 10
FRONTIER_GAPS_PER_ITERATION = 2
# A second gap is only worth its own solve when its totals move this much
# compared with the biggest gap. Otherwise both solves cut the biggest gap.
FRONTIER_SECOND_GAP_RATIO = 0.4
# Once any change has been narrowed this far, leave wide untouched gaps alone.
# Those are usually a single step pressed against one end of the weights.
FRONTIER_FINE_SHARE_GAP = 0.02
FRONTIER_WIDE_SHARE_GAP = 0.08
# Narrower than this, another solve almost always repeats a mix already found.
FRONTIER_MIN_SHARE_GAP = 0.0025
FRONTIER_STALE_ROUNDS = 2


def extract_loot(cell, importance_keys):
    """Split a recipe cell into (loot name, amount)."""
    if isinstance(cell, str):
        cell = cell.strip()
        parts = cell.split()
        try:
            amount = int(parts[0])
            item_type = " ".join(parts[1:])
            for key in importance_keys:
                if key in item_type:
                    return (key, amount)
            return (item_type, amount)
        except (ValueError, IndexError):
            sorted_keys = sorted(importance_keys, key=len, reverse=True)
            for key in sorted_keys:
                if key in cell:
                    return (key, 1)
    return ("Unknown", 0)


def solve_plan(df, items, combinations, ingredient_counts, importance_scores):
    """Maximise the weighted loot score for one set of importance weights.

    Returns the same payload the results view already renders, plus the
    weights that produced it.
    """
    keys = list(importance_scores.keys())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        warnings.simplefilter("ignore", DeprecationWarning)
        prob = LpProblem("Maximize Loot Score", LpMaximize)
        combo_vars = prob.add_variable_dicts("Combo", combinations, lowBound=0, cat=LpInteger)

        def loot_of(combo):
            return extract_loot(df.loc[combo], keys)

        prob += lpSum(
            importance_scores.get(loot_of(combo)[0], 0) * loot_of(combo)[1] * combo_vars[combo]
            for combo in combinations
        )

        for item in items:
            used = lpSum(combo_vars[combo] for combo in combinations if combo[0] == item) + lpSum(
                combo_vars[combo] for combo in combinations if combo[1] == item
            )
            created = lpSum(combo_vars[combo] for combo in combinations if df.loc[combo] == item)
            prob += used <= ingredient_counts[item] + created

        prob.solve(COIN_CMD(msg=False))

    combos_used = []
    for combo, var in combo_vars.items():
        amount = value(var)
        if amount is not None and amount > 1e-6:
            combos_used.append((combo, amount, df.loc[combo]))

    combos_used = sorted(combos_used, key=lambda row: items.index(row[0][0]))
    combos_used = sorted(combos_used, key=lambda row: any(key in row[2] for key in keys))

    total_loot = {}
    formatted_combos = []
    total_score = 0
    for combo, count, product in combos_used:
        product_name, product_amount = extract_loot(product, keys)
        total_loot[product_name] = total_loot.get(product_name, 0) + product_amount * count
        total_score += importance_scores.get(product_name, 0) * product_amount * count
        formatted_combos.append(
            {
                "input1": combo[0],
                "input2": combo[1],
                "count": count,
                "result": product,
                "is_ingredient": not any(key in product for key in keys if isinstance(product, str)),
            }
        )

    return {
        "total_score": total_score,
        "combos_used": combos_used,
        "total_loot": total_loot,
        "formatted_combos": formatted_combos,
        "ingredient_counts": dict(ingredient_counts),
        "weights": {key: float(importance_scores[key]) for key in importance_scores},
    }


def weights_for_share(item_a, item_b, max_a, max_b, loot_keys, share):
    """Value-share weights: s = 0 is all A, s = 1 is all B, s = 0.5 is equal value."""
    weights = {key: 0.0 for key in loot_keys}
    weights[item_a] = (1.0 - share) * float(max_b)
    weights[item_b] = share * float(max_a)
    return weights


def frontier_weight_sets(item_a, item_b, max_a, max_b, loot_keys, n=FRONTIER_POINTS):
    """Weights for n points from all of A to all of B.

    A share s puts weight (1 - s) * max_b on A and s * max_a on B, so one full
    pile of each item is worth the same at the midpoint. Returns None when
    either maximum is zero, because there is nothing to trade off.
    """
    if max_a <= 0 or max_b <= 0 or n < 2:
        return None
    return [
        (i / (n - 1), weights_for_share(item_a, item_b, max_a, max_b, loot_keys, i / (n - 1)))
        for i in range(n)
    ]


def _outcome_gaps(points, max_a, max_b, min_width):
    """Neighboring points whose loot totals differ, widest first in share."""
    if max_a <= 0 or max_b <= 0:
        return []
    ordered = sorted(points, key=lambda point: point["share"])
    gaps = []
    for left, right in zip(ordered, ordered[1:]):
        width = right["share"] - left["share"]
        if width < min_width:
            continue
        dx = (right["qty_a"] - left["qty_a"]) / max_a
        dy = (right["qty_b"] - left["qty_b"]) / max_b
        size = math.hypot(dx, dy)
        if size <= 1e-6:
            continue
        gaps.append(
            {
                "size": size,
                "width": width,
                "left": left["share"],
                "share": (left["share"] + right["share"]) / 2,
            }
        )
    return gaps


def refinement_shares(points, max_a, max_b):
    """Up to two shares for the next refinement round.

    Both shares cut the biggest remaining change, one third and two thirds of
    the way across, so a sharp step shows up sooner than repeated midpoints.
    When another change is at least 40% as large, the round splits those two
    gaps instead. After the search has already narrowed some change, wide
    leftovers are skipped: they are usually one step sitting at the far end.
    Returns an empty list when nothing useful is left to sample.
    """
    gaps = _outcome_gaps(points, max_a, max_b, FRONTIER_MIN_SHARE_GAP)
    if any(gap["width"] < FRONTIER_FINE_SHARE_GAP for gap in _outcome_gaps(points, max_a, max_b, 1e-9)):
        gaps = [gap for gap in gaps if gap["width"] <= FRONTIER_WIDE_SHARE_GAP]
    if not gaps:
        return []
    gaps.sort(key=lambda gap: gap["size"], reverse=True)
    best = gaps[0]
    second = next((gap for gap in gaps[1:] if gap["size"] >= FRONTIER_SECOND_GAP_RATIO * best["size"]), None)
    if second is not None:
        return [best["share"], second["share"]]
    width = best["width"]
    return [best["left"] + width / 3, best["left"] + 2 * width / 3]


def refinement_should_stop(discovered_new_mix, consecutive_stale_rounds):
    """Stop once new mixes have been found and two rounds repeat them."""
    return discovered_new_mix and consecutive_stale_rounds >= FRONTIER_STALE_ROUNDS


def share_label(item_a, item_b, share):
    """Short label for a point on the trade-off chart."""
    if share <= 0:
        return f"All {item_a}"
    if share >= 1:
        return f"All {item_b}"
    if abs(share - 0.5) < 1e-9:
        return "Equal value"
    percent = share * 100
    whole = round(percent)
    if abs(percent - whole) < 0.05:
        return f"{whole}% toward {item_b}"
    return f"{percent:.1f}% toward {item_b}"
