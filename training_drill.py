#!/usr/bin/env python3
"""
training_drill.py — Turnover Titans

Runs pitch_engine's logic through multiple PRACTICE reps, combining real
WIN-PATH and FAIL-RISK data. Labeled TRAINING throughout - nothing here
is a real send, nothing touches a real customer.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pitch_engine import load_json_dict, build_pitch


PRACTICE_LEADS = [
    ("Marcus", "Riverside Guest Suites"),
    ("Elena", "Lakefront Getaway Cabins"),
    ("DeShawn", "Downtown Loft Rentals"),
]


def run_drill(winners_path, losers_path):
    print("=" * 60)
    print("TRAINING DRILL — TURNOVER TITANS (practice only, no real sends)")
    print("=" * 60)

    winners = load_json_dict(winners_path, "winners")
    losers = load_json_dict(losers_path, "losers")

    if not winners and not losers:
        print("\nDRILL FAILED — no real data available. Nothing to train on.")
        return 1

    pass_count = 0
    fail_count = 0

    for i, (lead_name, lead_business) in enumerate(PRACTICE_LEADS, start=1):
        print(f"\n--- REP {i} of {len(PRACTICE_LEADS)} (TRAINING) ---")
        pitch = build_pitch(winners, losers, lead_name, lead_business)
        if pitch is None:
            print(f"REP {i}: FAILED — no pitch generated.")
            fail_count += 1
            continue

        print(pitch)
        print(f"\n[GRADE] Used WIN-PATH data: {bool(winners)} | Used FAIL-RISK data: {bool(losers)}")

        if winners and losers:
            print("[GRADE] PASS — combined both good data and bottleneck data, as trained.")
            pass_count += 1
        else:
            print("[GRADE] INCOMPLETE — only one data type available, not a full combined rep.")
            fail_count += 1

    print("\n" + "=" * 60)
    print(f"DRILL COMPLETE: {pass_count} passed, {fail_count} incomplete/failed, out of {len(PRACTICE_LEADS)} reps")
    print("TRAINING ONLY — no real customer was contacted.")
    print("=" * 60)
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    winners_path = sys.argv[1] if len(sys.argv) > 1 else "data/winners.json"
    losers_path = sys.argv[2] if len(sys.argv) > 2 else "data/losers.json"
    sys.exit(run_drill(winners_path, losers_path))
