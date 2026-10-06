"""Weight math and a smoke solve for the explore buttons."""

from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from src.alchemy_cleaner import load_reward_keys
from src.optimizer import (
    FRONTIER_POINTS,
    MAX_PER_ITEM_FIRST_BATCH,
    MAX_PER_ITEM_LOOT,
    frontier_weight_sets,
    refinement_shares,
    refinement_should_stop,
    share_label,
    solve_plan,
)

ROOT = Path(__file__).resolve().parents[1]
KEYS = load_reward_keys(ROOT / "streamlit_app.py")


class FrontierWeightTests(unittest.TestCase):
    def test_max_list_matches_optimiser_keys_and_first_batch(self):
        for name in MAX_PER_ITEM_LOOT:
            self.assertIn(name, KEYS)
        self.assertEqual(MAX_PER_ITEM_FIRST_BATCH, 5)
        self.assertGreater(len(MAX_PER_ITEM_LOOT), 5)

    def test_ends_are_single_item_and_middle_is_equal_value(self):
        sets = frontier_weight_sets("Currency", "Skill Points", 8000, 100, KEYS)
        self.assertEqual(len(sets), FRONTIER_POINTS)

        share_start, start = sets[0]
        share_end, end = sets[-1]
        self.assertEqual(share_start, 0)
        self.assertEqual(start["Currency"], 100)
        self.assertEqual(start["Skill Points"], 0)
        self.assertEqual(share_end, 1)
        self.assertEqual(end["Currency"], 0)
        self.assertEqual(end["Skill Points"], 8000)
        self.assertAlmostEqual(sets[1][0] - sets[0][0], sets[2][0] - sets[1][0])

        # Three points lands exactly on the equal-value share.
        _, mid = frontier_weight_sets("Currency", "Skill Points", 8000, 100, KEYS, n=3)[1]
        self.assertEqual(8000 * mid["Currency"], 100 * mid["Skill Points"])
        for key in KEYS:
            if key not in ("Currency", "Skill Points"):
                self.assertEqual(mid[key], 0)

    def test_zero_maximum_is_rejected(self):
        self.assertIsNone(frontier_weight_sets("Currency", "Skill Points", 0, 100, KEYS))
        self.assertIsNone(frontier_weight_sets("Currency", "Skill Points", 8000, 0, KEYS))

    def test_refinement_cuts_the_biggest_gap_and_stops_when_stale(self):
        points = [
            {"share": 0.0, "qty_a": 1000, "qty_b": 0},
            {"share": 0.4, "qty_a": 500, "qty_b": 0},
            {"share": 0.6, "qty_a": 0, "qty_b": 100},
            {"share": 1.0, "qty_a": 0, "qty_b": 100},
        ]
        # The combined swing and the earlier currency drop are close in size,
        # so the round splits both instead of cutting one of them twice.
        self.assertEqual(refinement_shares(points, 1000, 100), [0.5, 0.2])

        flat = [
            {"share": 0.0, "qty_a": 10, "qty_b": 5},
            {"share": 1.0, "qty_a": 10, "qty_b": 5},
        ]
        self.assertEqual(refinement_shares(flat, 10, 5), [])

        # A much smaller second gap does not get a solve; both samples trisect
        # the gap where the totals actually change.
        dominated = [
            {"share": 0.0, "qty_a": 1000, "qty_b": 0},
            {"share": 0.4, "qty_a": 0, "qty_b": 100},
            {"share": 0.8, "qty_a": 0, "qty_b": 100},
            {"share": 1.0, "qty_a": 0, "qty_b": 90},
        ]
        self.assertEqual(refinement_shares(dominated, 1000, 100), [0.4 / 3, 0.8 / 3])

        # Once a change is already narrow, a wide leftover step is left alone.
        narrowed = [
            {"share": 0.0, "qty_a": 0, "qty_b": 0},
            {"share": 0.01, "qty_a": 1000, "qty_b": 0},
            {"share": 0.5, "qty_a": 1000, "qty_b": 0},
            {"share": 1.0, "qty_a": 1000, "qty_b": 100},
        ]
        shares = refinement_shares(narrowed, 1000, 100)
        self.assertTrue(all(share < 0.01 for share in shares))
        self.assertEqual(len(shares), 2)

        self.assertFalse(refinement_should_stop(False, 2))
        self.assertFalse(refinement_should_stop(True, 1))
        self.assertTrue(refinement_should_stop(True, 2))

    def test_labels(self):
        self.assertEqual(share_label("Currency", "Skill Points", 0), "All Currency")
        self.assertEqual(share_label("Currency", "Skill Points", 1), "All Skill Points")
        self.assertEqual(share_label("Currency", "Skill Points", 0.5), "Equal value")
        self.assertEqual(share_label("Currency", "Skill Points", 0.3), "30% toward Skill Points")


class SolvePlanTests(unittest.TestCase):
    def test_currency_only_beats_a_zero_weight(self):
        df = pd.read_csv(ROOT / "TT2 Alchemy Event.csv", index_col=0)
        items = list(df.index)
        combinations = [(i, j) for i in items for j in items if i <= j]
        counts = {name: 2 for name in items}
        weights = {key: 0.0 for key in KEYS}
        weights["Currency"] = 100.0
        plan = solve_plan(df, items, combinations, counts, weights)
        self.assertGreater(plan["total_loot"].get("Currency", 0), 0)
        self.assertEqual(plan["weights"]["Skill Points"], 0)
