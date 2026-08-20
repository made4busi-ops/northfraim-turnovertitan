#!/usr/bin/env python3
"""
pitch_engine.py — Turnover Titans

Reads BOTH winners.json (WIN-PATH) and losers.json (FAIL-RISK) and
combines them into pitch copy. Pairs each claim with its matching
guarantee instead of just listing facts.
"""

import json
import os
import sys


def load_json_dict(path, label):
    if not os.path.exists(path):
        print(f"WARNING: {label} not found at {path}.")
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"WARNING: could not read {label}: {e}")
        return {}
    return data if isinstance(data, dict) else {}


def build_pitch(winners, losers, lead_name, lead_business):
    if not winners and not losers:
        return None

    lines = [f"Hi {lead_name},", ""]

    fear = winners.get("industry_fear_pattern")
    if fear:
        lines.append(
            "Cleanliness is the #1 reason short-term rentals lose stars — "
            f"{lead_business} deserves a partner that protects against that, not just a cleaner."
        )
        lines.append("")

    scope = winners.get("maidthis")
    checklist_guard = losers.get("checklist_memory_failure")
    if scope and checklist_guard:
        lines.append(
            "Every turnover runs off a written, room-by-room checklist — linen staging, "
            "restocking, and damage documentation as named steps, never left to memory."
        )

    standard = winners.get("shine_up_chicago")
    hightouch_guard = losers.get("missed_high_touch_surfaces")
    hair_guard = losers.get("stray_hair_signal")
    if standard and (hightouch_guard or hair_guard):
        lines.append(
            "We don't do partial cleans. High-touch points (switches, handles, remotes) and "
            "a final hair/trace sweep are their own checklist steps, not folded into 'general cleaning.'"
        )

    schedule = winners.get("turno")
    restock_guard = losers.get("midstay_restock_shortage")
    if schedule or restock_guard:
        lines.append(
            "Scheduling syncs to real checkout/checkin times, and amenities are refilled from "
            "bulk stock, not mini bottles — no guest finds an empty dispenser on day two."
        )

    recovery_guard = losers.get("no_recovery_protocol")
    if recovery_guard:
        lines.append(
            "And if a guest ever does flag something, we redo it at no cost — no disputes, no excuses."
        )

    lines.append("")
    lines.append("Want a walkthrough of how this works for your property?")

    return "\n".join(lines)


def main(argv):
    if len(argv) != 5:
        print("Usage: python3 pitch_engine.py <winners_path> <losers_path> <lead_name> <lead_business>")
        return 2

    winners_path, losers_path, lead_name, lead_business = argv[1], argv[2], argv[3], argv[4]
    winners = load_json_dict(winners_path, "winners")
    losers = load_json_dict(losers_path, "losers")

    pitch = build_pitch(winners, losers, lead_name, lead_business)
    if pitch is None:
        print("NO PITCH GENERATED — no winner or loser data available.")
        return 1

    print("=== GENERATED PITCH ===")
    print(pitch)
    print("========================")
    print(f"\nWIN-PATH patterns used: {list(winners.keys())}")
    print(f"FAIL-RISK guardrails used: {list(losers.keys())}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
