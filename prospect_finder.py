#!/usr/bin/env python3
"""
prospect_finder.py -- Turnover Titans

The prospecting piece: NOT a scraper, NOT a rented database like
Apollo. Real intake of hosts you find yourself (Facebook groups,
Airbnb's own host directory, word of mouth), plus a REAL qualifier
that actually fetches the host's website and checks it for weak
web-presence signals: no mobile viewport tag, no chat/agent widget
script detected. This is the sharpened pitch from tonight -- lead
with "your site could use this" instead of a cold pitch.

Uses only the standard library (urllib) -- no new dependency.
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

CHAT_WIDGET_SIGNATURES = [
    "intercom", "drift.com", "tidio", "livechat", "crisp.chat",
    "tawk.to", "zendesk", "hubspot", "chatbot",
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return default
    return data if isinstance(data, dict) else default


def _save_json(path, data):
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def add_prospect(store_path, prospect_id, host_name, business, website_url, source):
    data = _load_json(store_path, {"prospects": {}})
    data.setdefault("prospects", {})
    if prospect_id in data["prospects"]:
        print("WARNING: prospect '" + prospect_id + "' already exists. Not overwritten.")
        return False
    data["prospects"][prospect_id] = {
        "host_name": host_name,
        "business": business,
        "website_url": website_url,
        "source": source,
        "added_at": _now(),
        "qualified": False,
        "weak_presence": None,
        "qualification_notes": None,
    }
    _save_json(store_path, data)
    print("[PROSPECT] Added '" + prospect_id + "': " + host_name + " (" + business + ") via " + source)
    return True


def qualify(store_path, prospect_id, timeout=10):
    data = _load_json(store_path, {"prospects": {}})
    prospect = data.get("prospects", {}).get(prospect_id)
    if prospect is None:
        print("ERROR: prospect '" + prospect_id + "' not found.")
        return None

    url = prospect["website_url"]
    if not url:
        prospect["qualified"] = True
        prospect["weak_presence"] = True
        prospect["qualification_notes"] = "No website on file at all -- strongest possible lead."
        _save_json(store_path, data)
        print("[QUALIFY] '" + prospect_id + "': NO WEBSITE ON FILE -- weak_presence=True")
        return prospect

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        reachable = True
    except (urllib.error.URLError, TimeoutError) as e:
        reachable = False
        html = ""
        error_msg = str(e)

    if not reachable:
        prospect["qualified"] = True
        prospect["weak_presence"] = True
        prospect["qualification_notes"] = "Site unreachable: " + error_msg
        _save_json(store_path, data)
        print("[QUALIFY] '" + prospect_id + "': SITE UNREACHABLE -- weak_presence=True")
        return prospect

    html_lower = html.lower()
    has_viewport = bool(re.search(r'<meta[^>]+name=["\']viewport["\']', html_lower))
    has_chat_widget = any(sig in html_lower for sig in CHAT_WIDGET_SIGNATURES)

    weak = (not has_viewport) or (not has_chat_widget)
    notes = []
    if not has_viewport:
        notes.append("no mobile viewport tag found")
    if not has_chat_widget:
        notes.append("no chat/AI agent widget detected")
    if not notes:
        notes.append("site looks modern -- has viewport + a chat widget already")

    prospect["qualified"] = True
    prospect["weak_presence"] = weak
    prospect["qualification_notes"] = "; ".join(notes)
    _save_json(store_path, data)

    print("[QUALIFY] '" + prospect_id + "': weak_presence=" + str(weak) + " -- " + prospect["qualification_notes"])
    return prospect


def board(store_path):
    data = _load_json(store_path, {"prospects": {}})
    prospects = data.get("prospects", {})
    if not prospects:
        print("NO PROSPECTS YET.")
        return
    weak = [(pid, p) for pid, p in prospects.items() if p.get("weak_presence")]
    other = [(pid, p) for pid, p in prospects.items() if not p.get("weak_presence")]
    print("=== PROSPECT BOARD (" + str(len(prospects)) + ") ===")
    print("\n[WEAK WEB PRESENCE -- BEST LEADS] (" + str(len(weak)) + ")")
    for pid, p in weak:
        print("  - " + pid + ": " + p["host_name"] + " (" + p["business"] + ") -- " + str(p.get("qualification_notes")))
    print("\n[OTHER / UNQUALIFIED] (" + str(len(other)) + ")")
    for pid, p in other:
        status = p.get("qualification_notes") or "not yet qualified"
        print("  - " + pid + ": " + p["host_name"] + " (" + p["business"] + ") -- " + status)


def _usage():
    print("Usage:")
    print("  python3 prospect_finder.py <store_path> add <prospect_id> <host_name> <business> <website_url_or_none> <source>")
    print("  python3 prospect_finder.py <store_path> qualify <prospect_id>")
    print("  python3 prospect_finder.py <store_path> board")


def main(argv):
    if len(argv) < 3:
        _usage()
        return 2

    store_path, command = argv[1], argv[2]
    rest = argv[3:]

    if command == "add":
        if len(rest) != 5:
            _usage()
            return 2
        prospect_id, host_name, business, website_url, source = rest
        if website_url.lower() == "none":
            website_url = ""
        return 0 if add_prospect(store_path, prospect_id, host_name, business, website_url, source) else 1

    if command == "qualify":
        if len(rest) != 1:
            _usage()
            return 2
        return 0 if qualify(store_path, rest[0]) is not None else 1

    if command == "board":
        board(store_path)
        return 0

    print("Unknown command '" + command + "'.")
    _usage()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
