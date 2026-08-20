#!/usr/bin/env python3
"""
youtube_distribution.py -- Turnover Titans

Real link between a finished Commercial Genie render and a host's
webpage. This does NOT call the YouTube upload API -- that requires
a real Google Cloud OAuth setup (client ID/secret, consent screen)
that isn't configured on this machine yet. Building a fake uploader
that pretends to call an API with no credentials would be exactly
the kind of stub this project keeps ripping out -- so this piece
covers only what's real right now: once a video is uploaded to
YouTube (by hand, or later by an automated uploader once OAuth
exists), record the real YouTube video ID, generate the real embed
HTML, and inject it into that host's already-generated webpage.

Nothing here invents a video ID or pretends an upload happened.
"""

import json
import os
import sys
from datetime import datetime, timezone

EMBED_TEMPLATE = """    <div class="card">
      <h2>Featured Video</h2>
      <div style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;">
        <iframe src="https://www.youtube.com/embed/{video_id}"
          style="position:absolute;top:0;left:0;width:100%;height:100%;"
          frameborder="0" allowfullscreen></iframe>
      </div>
    </div>
"""


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


def record_video(registry_path, signup_id, youtube_video_id, source_render_path):
    if not youtube_video_id or len(youtube_video_id.strip()) < 6:
        print("ERROR: '" + str(youtube_video_id) + "' does not look like a real YouTube video ID.")
        return False

    registry = _load_json(registry_path, {"videos": {}})
    registry.setdefault("videos", {})
    registry["videos"][signup_id] = {
        "youtube_video_id": youtube_video_id.strip(),
        "source_render_path": source_render_path,
        "recorded_at": _now(),
    }
    _save_json(registry_path, registry)
    print("[DISTRIBUTION] Recorded real video '" + youtube_video_id + "' for '" + signup_id + "'.")
    return True


def inject_embed(registry_path, site_path, signup_id):
    registry = _load_json(registry_path, {"videos": {}})
    video = registry.get("videos", {}).get(signup_id)
    if video is None:
        print("ERROR: no recorded video for '" + signup_id + "'. Run record_video first.")
        return False

    if not os.path.exists(site_path):
        print("ERROR: site file not found at " + site_path)
        return False

    with open(site_path, "r", encoding="utf-8") as f:
        html = f.read()

    if "</main>" not in html:
        print("ERROR: site file has no </main> tag to inject before.")
        return False

    embed_html = EMBED_TEMPLATE.format(video_id=video["youtube_video_id"])
    new_html = html.replace("</main>", embed_html + "</main>")

    with open(site_path, "w", encoding="utf-8") as f:
        f.write(new_html)

    print("[DISTRIBUTION] Embedded video into " + site_path)
    return True


def _usage():
    print("Usage:")
    print("  python3 youtube_distribution.py <registry_path> record <signup_id> <youtube_video_id> <source_render_path>")
    print("  python3 youtube_distribution.py <registry_path> embed <signup_id> <site_path>")


def main(argv):
    if len(argv) < 3:
        _usage()
        return 2

    registry_path, command = argv[1], argv[2]
    rest = argv[3:]

    if command == "record":
        if len(rest) != 3:
            _usage()
            return 2
        signup_id, video_id, render_path = rest
        return 0 if record_video(registry_path, signup_id, video_id, render_path) else 1

    if command == "embed":
        if len(rest) != 2:
            _usage()
            return 2
        signup_id, site_path = rest
        return 0 if inject_embed(registry_path, site_path, signup_id) else 1

    print("Unknown command '" + command + "'.")
    _usage()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
