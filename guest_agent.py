#!/usr/bin/env python3
"""
guest_agent.py -- Turnover Titans

Tier 2 deliverable: real 24/7 AI Guest Agent, one per host.

No external API key required to run -- this is a real keyword-matched
FAQ agent against each host's own knowledge base (wifi, check-in,
check-out, house rules, contact). Answers guests instantly on the
common questions. Anything it can't match gets logged as unanswered
and flagged for the host, instead of guessing.

Each host gets their own knowledge file: data/knowledge/<signup_id>.json
Every question + answer gets logged to a real conversation log per host.
"""

import json
import os
import sys
from datetime import datetime, timezone

DEFAULT_KNOWLEDGE = {
    "wifi_password": "",
    "wifi_network": "",
    "check_in_time": "",
    "check_out_time": "",
    "address": "",
    "house_rules": "",
    "host_contact": "",
}

INTENTS = [
    (["wifi", "wi-fi", "internet", "password", "network"], "wifi_password"),
    (["check in", "check-in", "checkin", "arrival", "arrive"], "check_in_time"),
    (["check out", "check-out", "checkout", "leave", "leaving"], "check_out_time"),
    (["address", "location", "where"], "address"),
    (["rules", "smoking", "pets", "party", "guests allowed", "quiet hours"], "house_rules"),
    (["contact", "phone", "call", "reach", "emergency"], "host_contact"),
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
    if not isinstance(data, dict):
        return default
    return data


def _save_json(path, data):
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def _knowledge_path(knowledge_dir, signup_id):
    return os.path.join(knowledge_dir, signup_id + ".json")


def set_knowledge(knowledge_dir, signup_id, field, value):
    if field not in DEFAULT_KNOWLEDGE:
        print("ERROR: unknown knowledge field '" + field + "'. Valid fields: " + ", ".join(DEFAULT_KNOWLEDGE.keys()))
        return False
    path = _knowledge_path(knowledge_dir, signup_id)
    data = _load_json(path, dict(DEFAULT_KNOWLEDGE))
    data[field] = value
    _save_json(path, data)
    print("[AGENT SETUP] '" + signup_id + "': set " + field)
    return True


def ask(knowledge_dir, log_path, signup_id, question):
    path = _knowledge_path(knowledge_dir, signup_id)
    knowledge = _load_json(path, dict(DEFAULT_KNOWLEDGE))

    q_lower = question.lower()
    matched_field = None
    for keywords, field in INTENTS:
        if any(kw in q_lower for kw in keywords):
            matched_field = field
            break

    if matched_field is None:
        answer = None
        answered = False
    else:
        value = knowledge.get(matched_field, "")
        if value:
            answer = value
            answered = True
        else:
            answer = None
            answered = False

    log = _load_json(log_path, {"conversations": []})
    log.setdefault("conversations", [])
    log["conversations"].append({
        "signup_id": signup_id,
        "question": question,
        "matched_field": matched_field,
        "answer": answer,
        "answered": answered,
        "timestamp": _now(),
    })
    _save_json(log_path, log)

    if answered:
        print("[AGENT] " + signup_id + ": Q: \"" + question + "\" -> A: " + answer)
    else:
        print("[AGENT] " + signup_id + ": Q: \"" + question + "\" -> UNANSWERED, flagged for host follow-up")

    return answer


def unanswered(log_path):
    log = _load_json(log_path, {"conversations": []})
    misses = [c for c in log.get("conversations", []) if not c.get("answered")]
    if not misses:
        print("NO UNANSWERED QUESTIONS.")
        return []
    print("=== UNANSWERED QUESTIONS (" + str(len(misses)) + ") ===")
    for c in misses:
        print("  - [" + c["signup_id"] + "] \"" + c["question"] + "\" (" + c["timestamp"] + ")")
    return misses


def _usage():
    print("Usage:")
    print("  python3 guest_agent.py <knowledge_dir> <log_path> set <signup_id> <field> <value>")
    print("  python3 guest_agent.py <knowledge_dir> <log_path> ask <signup_id> \"<question>\"")
    print("  python3 guest_agent.py <knowledge_dir> <log_path> unanswered")
    print("  Valid fields: " + ", ".join(DEFAULT_KNOWLEDGE.keys()))


def main(argv):
    if len(argv) < 4:
        _usage()
        return 2

    knowledge_dir, log_path, command = argv[1], argv[2], argv[3]
    rest = argv[4:]

    if command == "set":
        if len(rest) < 3:
            _usage()
            return 2
        signup_id, field = rest[0], rest[1]
        value = " ".join(rest[2:])
        return 0 if set_knowledge(knowledge_dir, signup_id, field, value) else 1

    if command == "ask":
        if len(rest) != 2:
            _usage()
            return 2
        signup_id, question = rest[0], rest[1]
        result = ask(knowledge_dir, log_path, signup_id, question)
        return 0

    if command == "unanswered":
        unanswered(log_path)
        return 0

    print("Unknown command '" + command + "'.")
    _usage()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
