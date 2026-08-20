#!/usr/bin/env python3
"""
webpage_generator.py -- Turnover Titans

Tier 1 deliverable: real per-host smart webpage generator.
Reads a real signup from the Tollbooth (signup_tiers.py's store),
optionally pulls a matching property from property_registry.py's
store, and writes a real standalone HTML file for that host.

One reusable template, cloned/configured per customer -- not
hand-built per host.
"""

import json
import os
import sys

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{business} -- Managed by Turnover Titans</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{ font-family: Arial, sans-serif; margin: 0; background: #f7f7f7; color: #222; }}
  header {{ background: #1b2a4a; color: #fff; padding: 40px 20px; text-align: center; }}
  header h1 {{ margin: 0 0 8px 0; }}
  .tagline {{ color: #cbd5e1; }}
  main {{ max-width: 700px; margin: 30px auto; padding: 0 20px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .property-list li {{ margin-bottom: 6px; }}
  footer {{ text-align: center; padding: 20px; color: #888; font-size: 0.9em; }}
</style>
</head>
<body>
<header>
  <h1>{business}</h1>
  <div class="tagline">Hosted &amp; managed by Turnover Titans</div>
</header>
<main>
  <div class="card">
    <h2>Welcome</h2>
    <p>{host_name} runs {business} with Turnover Titans handling turnover, cleaning, and guest operations behind the scenes.</p>
  </div>
  <div class="card">
    <h2>Properties</h2>
    <ul class="property-list">
{property_items}
    </ul>
  </div>
  <div class="card">
    <h2>Contact</h2>
    <p>Questions about a stay? Reach out and we'll get back to you shortly.</p>
  </div>
</main>
<footer>Powered by NorthFRAIM Turnover Titans</footer>
</body>
</html>
"""


def _load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def generate_page(tollbooth_path, properties_path, signup_id, output_dir):
    tollbooth = _load_json(tollbooth_path)
    if tollbooth is None or signup_id not in tollbooth.get("signups", {}):
        print("ERROR: signup '" + signup_id + "' not found in " + tollbooth_path)
        return None

    signup = tollbooth["signups"][signup_id]
    host_name = signup["host_name"]
    business = signup["business"]

    properties = _load_json(properties_path) or {"properties": {}}
    matched = []
    for pid, prop in properties.get("properties", {}).items():
        if prop.get("owner", "").strip().lower() == host_name.strip().lower():
            matched.append((pid, prop))

    if matched:
        property_items = "\n".join(
            "      <li>" + prop["name"] + "</li>" for pid, prop in matched
        )
    else:
        property_items = "      <li>No properties on file yet.</li>"

    html = TEMPLATE.format(
        business=business,
        host_name=host_name,
        property_items=property_items,
    )

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, signup_id + ".html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print("[WEBPAGE] Generated page for '" + signup_id + "' (" + business + ") -> " + out_path)
    return out_path


def _usage():
    print("Usage:")
    print("  python3 webpage_generator.py <tollbooth_path> <properties_path> <signup_id> <output_dir>")


def main(argv):
    if len(argv) != 5:
        _usage()
        return 2
    tollbooth_path, properties_path, signup_id, output_dir = argv[1], argv[2], argv[3], argv[4]
    result = generate_page(tollbooth_path, properties_path, signup_id, output_dir)
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
