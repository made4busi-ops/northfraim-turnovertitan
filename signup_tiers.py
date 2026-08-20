#!/usr/bin/env python3
"""
signup_tiers.py -- Turnover Titans

The Tollbooth. Real signup + tier system.
5 tiers, 2-month test-drive pricing, real dates, real store.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

TIERS = {
    "1": {"name": "Free Smart Page", "test_drive_fee": 1, "monthly_rate": "Free"},
    "2": {"name": "AI Guest Agent", "test_drive_fee": 3, "monthly_rate": "$9-12"},
    "3": {"name": "Operations & Turnover", "test_drive_fee": 5, "monthly_rate": "$39-49"},
    "4": {"name": "TikTok & Social Growth", "test_drive_fee": 10, "monthly_rate": "$79-99"},
    "5": {"name": "NorthFRAIM Empire Suite", "test_drive_fee": 25, "monthly_rate": "$297-300"},
}

TRIAL_DAYS = 60


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat()


def _load(store_path):
    if not os.path.exists(store_path):
        return {"signups": {}}
    try:
        with open(store_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print("WARNING: could not read " + store_path + ": " + str(e))
        return {"signups": {}}
    if not isinstance(data, dict) or not isinstance(data.get("signups"), dict):
        return {"signups": {}}
    return data


def _save(store_path, data):
    directory = os.path.dirname(os.path.abspath(store_path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = store_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, store_path)


def signup(store_path, signup_id, host_name, business, tier):
    if tier not in TIERS:
        print("ERROR: invalid tier '" + tier + "'. Valid tiers: " + ", ".join(TIERS.keys()))
        return False
    data = _load(store_path)
    if signup_id in data["signups"]:
        print("WARNING: signup '" + signup_id + "' already exists. Not overwritten.")
        return False
    now = _now()
    trial_end = now + timedelta(days=TRIAL_DAYS)
    tier_info = TIERS[tier]
    data["signups"][signup_id] = {
        "host_name": host_name,
        "business": business,
        "tier": tier,
        "tier_name": tier_info["name"],
        "test_drive_fee": tier_info["test_drive_fee"],
        "monthly_rate": tier_info["monthly_rate"],
        "signed_up_at": _iso(now),
        "trial_ends_at": _iso(trial_end),
        "status": "trial_active",
    }
    _save(store_path, data)
    print("[TOLLBOOTH] Signed up '" + signup_id + "': " + host_name + " (" + business + ") -- Tier " + tier + " (" + tier_info["name"] + "), $" + str(tier_info["test_drive_fee"]) + " test drive, trial ends " + trial_end.strftime("%Y-%m-%d"))
    return True


def get_signup(store_path, signup_id):
    data = _load(store_path)
    s = data["signups"].get(signup_id)
    if s is None:
        print("WARNING: signup '" + signup_id + "' not found.")
        return None
    print("=== " + signup_id + " ===")
    print("Host: " + s["host_name"])
    print("Business: " + s["business"])
    print("Tier: " + s["tier"] + " (" + s["tier_name"] + ")")
    print("Test drive fee: $" + str(s["test_drive_fee"]))
    print("Monthly rate after trial: " + s["monthly_rate"])
    print("Signed up: " + s["signed_up_at"])
    print("Trial ends: " + s["trial_ends_at"])
    print("Status: " + s["status"])
    return s


def check_expired(store_path):
    data = _load(store_path)
    now = _now()
    flipped = []
    for sid, s in data["signups"].items():
        if s["status"] == "trial_active":
            trial_end = datetime.fromisoformat(s["trial_ends_at"])
            if now >= trial_end:
                s["status"] = "trial_expired"
                flipped.append(sid)
    if flipped:
        _save(store_path, data)
        for sid in flipped:
            print("[TOLLBOOTH] '" + sid + "' trial expired -- flagged for escalator decision.")
    else:
        print("[TOLLBOOTH] No trials expired.")
    return flipped


def board(store_path):
    data = _load(store_path)
    signups = data["signups"]
    if not signups:
        print("NO SIGNUPS YET.")
        return
    by_tier = {}
    for sid, s in signups.items():
        by_tier.setdefault(s["tier"], []).append((sid, s))
    print("=== TOLLBOOTH BOARD (" + str(len(signups)) + ") ===")
    for tier in sorted(by_tier.keys()):
        tier_info = TIERS.get(tier, {"name": "Unknown"})
        print("\n[TIER " + tier + " -- " + tier_info["name"] + "] (" + str(len(by_tier[tier])) + ")")
        for sid, s in by_tier[tier]:
            print("  - " + sid + ": " + s["host_name"] + " (" + s["business"] + ") -- " + s["status"])


def _usage():
    print("Usage:")
    print("  python3 signup_tiers.py <store_path> signup <signup_id> <host_name> <business> <tier 1-5>")
    print("  python3 signup_tiers.py <store_path> get <signup_id>")
    print("  python3 signup_tiers.py <store_path> check-expired")
    print("  python3 signup_tiers.py <store_path> board")


def main(argv):
    if len(argv) < 3:
        _usage()
        return 2

    store_path, command = argv[1], argv[2]
    rest = argv[3:]

    if command == "signup":
        if len(rest) != 4:
            _usage()
            return 2
        return 0 if signup(store_path, rest[0], rest[1], rest[2], rest[3]) else 1

    if command == "get":
        if len(rest) != 1:
            _usage()
            return 2
        return 0 if get_signup(store_path, rest[0]) is not None else 1

    if command == "check-expired":
        check_expired(store_path)
        return 0

    if command == "board":
        board(store_path)
        return 0

    print("Unknown command '" + command + "'.")
    _usage()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
