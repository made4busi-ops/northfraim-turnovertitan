#!/usr/bin/env python3
"""
tier_media_bridge.py -- Turnover Titans
Bridges signup tiers to Commercial Genie free-commercial fulfillment.
All tiers (1-5) are eligible for one free startup commercial.
Guards against double-fire per signup_id.
"""

import json
import sys
import os
from datetime import datetime, timezone

ELIGIBLE_TIERS = {"1", "2", "3", "4", "5"}


def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def log_event(log_path, message):
    timestamp = datetime.now(timezone.utc).isoformat()
    with open(log_path, "a") as f:
        f.write(f"[{timestamp}] {message}\n")


def get_signup(tollbooth_path, signup_id):
    data = load_json(tollbooth_path)
    signups = data.get("signups", data) if isinstance(data, dict) else {}
    return signups.get(signup_id)


def is_eligible(signup):
    if signup is None:
        return False, "signup not found"
    tier = str(signup.get("tier", ""))
    if tier not in ELIGIBLE_TIERS:
        return False, f"tier {tier} not eligible"
    if signup.get("free_commercial_sent") is True:
        return False, "free commercial already sent for this signup"
    return True, "eligible"


def mark_sent(tollbooth_path, signup_id):
    data = load_json(tollbooth_path)
    signups = data.get("signups", data) if isinstance(data, dict) else {}
    if signup_id in signups:
        signups[signup_id]["free_commercial_sent"] = True
        signups[signup_id]["free_commercial_sent_at"] = datetime.now(timezone.utc).isoformat()
        if "signups" in data:
            data["signups"] = signups
        else:
            data = signups
        save_json(tollbooth_path, data)
        return True
    return False


def record_order(properties_path, signup_id, genie_url):
    orders = load_json(properties_path)
    if not isinstance(orders, dict):
        orders = {}
    order_list = orders.get("orders", [])
    order_list.append({
        "signup_id": signup_id,
        "genie_url": genie_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    orders["orders"] = order_list
    save_json(properties_path, orders)


def trigger(tollbooth_path, properties_path, log_path, signup_id, genie_url):
    signup = get_signup(tollbooth_path, signup_id)
    eligible, reason = is_eligible(signup)
    if not eligible:
        log_event(log_path, f"BLOCKED signup_id={signup_id} reason={reason}")
        print(f"BLOCKED: {reason}")
        return False
    record_order(properties_path, signup_id, genie_url)
    mark_sent(tollbooth_path, signup_id)
    log_event(log_path, f"SENT signup_id={signup_id} genie_url={genie_url}")
    print(f"SENT: free commercial triggered for {signup_id}")
    return True


def show_orders(properties_path):
    orders = load_json(properties_path)
    order_list = orders.get("orders", []) if isinstance(orders, dict) else []
    if not order_list:
        print("No orders recorded.")
        return
    for o in order_list:
        print(f"{o['created_at']}  signup_id={o['signup_id']}  genie_url={o['genie_url']}")


def main():
    if len(sys.argv) < 5:
        print("Usage:")
        print("  python3 tier_media_bridge.py <tollbooth_path> <properties_path> <log_path> trigger <signup_id> <genie_url>")
        print("  python3 tier_media_bridge.py <tollbooth_path> <properties_path> <log_path> orders")
        sys.exit(1)

    tollbooth_path, properties_path, log_path, command = sys.argv[1:5]

    if command == "trigger":
        if len(sys.argv) < 7:
            print("trigger requires <signup_id> <genie_url>")
            sys.exit(1)
        signup_id, genie_url = sys.argv[5], sys.argv[6]
        trigger(tollbooth_path, properties_path, log_path, signup_id, genie_url)
    elif command == "orders":
        show_orders(properties_path)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
