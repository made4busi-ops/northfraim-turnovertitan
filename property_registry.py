#!/usr/bin/env python3
"""
property_registry.py -- Turnover Titans

The missing piece for the hub vision: a real list of every property,
starting with Derrick's own.
"""

import json
import os
import sys
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load(store_path):
    if not os.path.exists(store_path):
        return {"properties": {}}
    try:
        with open(store_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print("WARNING: could not read " + store_path + ": " + str(e))
        return {"properties": {}}
    if not isinstance(data, dict) or not isinstance(data.get("properties"), dict):
        return {"properties": {}}
    return data


def _save(store_path, data):
    directory = os.path.dirname(os.path.abspath(store_path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = store_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, store_path)


def add_property(store_path, property_id, name, owner, notes="", access_details=""):
    data = _load(store_path)
    if property_id in data["properties"]:
        print("WARNING: property '" + property_id + "' already exists. Not overwritten.")
        return False
    data["properties"][property_id] = {
        "name": name,
        "owner": owner,
        "notes": notes,
        "access_details": access_details,
        "added_at": _now(),
    }
    _save(store_path, data)
    print("[REGISTRY] Added property '" + property_id + "': " + name + " (owner: " + owner + ")")
    return True


def get_property(store_path, property_id):
    data = _load(store_path)
    prop = data["properties"].get(property_id)
    if prop is None:
        print("WARNING: property '" + property_id + "' not found.")
        return None
    print("=== " + property_id + " ===")
    print("Name: " + prop["name"])
    print("Owner: " + prop["owner"])
    if prop.get("access_details"):
        print("Access details: " + prop["access_details"])
    if prop.get("notes"):
        print("Notes: " + prop["notes"])
    print("Added: " + prop["added_at"])
    return prop


def list_properties(store_path):
    data = _load(store_path)
    if not data["properties"]:
        print("NO PROPERTIES REGISTERED YET.")
        return
    print("=== PROPERTY REGISTRY (" + str(len(data["properties"])) + ") ===")
    for pid, prop in data["properties"].items():
        print("  - " + pid + ": " + prop["name"] + " (owner: " + prop["owner"] + ")")


def _usage():
    print("Usage:")
    print("  python3 property_registry.py <store_path> add <property_id> <name> <owner> [notes]")
    print("  python3 property_registry.py <store_path> get <property_id>")
    print("  python3 property_registry.py <store_path> list")


def main(argv):
    if len(argv) < 3:
        _usage()
        return 2

    store_path, command = argv[1], argv[2]
    rest = argv[3:]

    if command == "add":
        if len(rest) < 3:
            _usage()
            return 2
        notes = " ".join(rest[3:]) if len(rest) > 3 else ""
        return 0 if add_property(store_path, rest[0], rest[1], rest[2], notes) else 1

    if command == "get":
        if len(rest) != 1:
            _usage()
            return 2
        return 0 if get_property(store_path, rest[0]) is not None else 1

    if command == "list":
        list_properties(store_path)
        return 0

    print("Unknown command '" + command + "'.")
    _usage()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
