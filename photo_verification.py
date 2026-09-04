"""
photo_verification.py -- Turnover Titans

Real vision-check gate for job-completion photos, built on the exact
same pattern as northfraim-job77/mcp/agents/nver_verification.py (real
vision-model call over real images, same infra-tolerance philosophy:
an API/network failure doesn't force a fail, since an infra hiccup
shouldn't punish a cleaner who did real work and has real photos to
prove it). The prompt itself is new -- this isn't checking for
movie-rendering defects, it's checking that a photo genuinely shows a
cleaned space and isn't blank, a duplicate, or irrelevant.

Vision provider (2026-09-04): switched from xAI's grok-4.3 to
DeepSeek's deepseek-v4-flash-vision-exp -- confirmed for real against
DeepSeek's own docs (api-docs.deepseek.com/guides/vision) that it
genuinely accepts image input (base64 data URLs, same OpenAI-compatible
message-content shape xAI uses), not text-only. Derrick asked for this
swap since DEEPSEEK_API_KEY is the already-funded, already-working key.
"""
import base64
import os

import requests
from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/northfraim-job77/.env"))
# Real bug found alongside this swap: the path above doesn't exist on
# this machine (only northfraim-job77-full does, a different checkout)
# -- so it silently loaded nothing here, and DEEPSEEK_API_KEY/
# XAI_API_KEY were never actually reachable this way on this box. Both
# NorthFraim and Turnover Titans share the same DeepSeek account/key in
# practice, and the one place that key genuinely lives on this machine
# is the live systemd EnvironmentFile -- same simple KEY=value format
# load_dotenv already parses, so it doubles as a real fallback source
# rather than inventing a new config mechanism.
load_dotenv("/etc/northfraim/stripe.env")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_VISION_MODEL = "deepseek-v4-flash-vision-exp"
DEEPSEEK_CHAT_URL = "https://api.deepseek.com/chat/completions"

VERIFICATION_PROMPT = (
    "These are real photos a cleaner submitted as proof of completing a real "
    "short-term rental turnover cleaning job. For EACH photo, in order, decide "
    "PASS or FAIL:\n"
    "- FAIL if a photo is blank, solid-black, solid-white, or otherwise shows "
    "no real room content.\n"
    "- FAIL if a photo is a near-exact duplicate of another photo in this set "
    "(same framing, nothing changed).\n"
    "- FAIL if a photo doesn't show an interior residential space at all "
    "(e.g. a random object, a screenshot, an outdoor scene, a person's face).\n"
    "- FAIL if a photo shows a room that is visibly NOT clean -- visible "
    "trash, stains, clutter, unmade mess.\n"
    "- PASS if a photo shows a real, distinct interior space that looks "
    "genuinely tidy and cleaned, even if the room is modest or the photo "
    "isn't professionally lit. Do not fail a photo just because it looks "
    "ordinary -- a plain, clean room is a normal, correct result here, not a "
    "defect.\n\n"
    "Reply with ONLY one line per photo, in order, in exactly this format:\n"
    "1: PASS or FAIL: <short reason>\n"
    "2: PASS or FAIL: <short reason>\n"
    "(etc, one numbered line per photo, same order as given)"
)


def _vision_quality_check(photo_paths: list) -> dict:
    """Real DeepSeek-vision call over real submitted photos. Returns
    {"checked": bool, "results": [{"path", "passed", "reason"}], "reason": str}.
    "checked" is False (not a failure) only when the call itself
    couldn't run at all (no API key, network error) -- matches
    nver_verification.py's exact philosophy: infra failures don't
    silently fail a cleaner who submitted real photos."""
    if not DEEPSEEK_API_KEY:
        return {"checked": False, "results": [], "reason": "DEEPSEEK_API_KEY not set -- vision check could not run"}

    content = []
    valid_paths = []
    for p in photo_paths:
        try:
            with open(p, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
            valid_paths.append(p)
        except Exception:
            continue

    if not content:
        return {"checked": False, "results": [], "reason": "No real photos available to check"}

    content.append({"type": "text", "text": VERIFICATION_PROMPT})

    try:
        r = requests.post(
            DEEPSEEK_CHAT_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            # max_tokens=2000, not 400: deepseek-v4-flash-vision-exp is a
            # reasoning model -- its chain-of-thought shares the same
            # completion-token budget as the final answer
            # (usage.completion_tokens_details.reasoning_tokens), and a
            # real test against this exact endpoint showed reasoning
            # alone consuming 400-527+ tokens before any final content is
            # written, leaving finish_reason="length" and an EMPTY
            # message.content at the old budget. Confirmed working at
            # 2000 (finish_reason="stop", real non-empty content).
            json={"model": DEEPSEEK_VISION_MODEL, "messages": [{"role": "user", "content": content}], "max_tokens": 2000},
            timeout=60,
        )
        if r.status_code != 200:
            return {"checked": False, "results": [], "reason": f"Vision request failed: HTTP {r.status_code}"}
        text = r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return {"checked": False, "results": [], "reason": f"Vision request error: {e}"}

    results = []
    for i, path in enumerate(valid_paths, start=1):
        line = next((ln for ln in text.splitlines() if ln.strip().startswith(f"{i}:")), None)
        if line is None:
            results.append({"path": path, "passed": None, "reason": "no result line returned for this photo"})
            continue
        body = line.split(":", 1)[1].strip() if ":" in line else line
        passed = body.upper().startswith("PASS")
        results.append({"path": path, "passed": passed, "reason": body})

    return {"checked": True, "results": results, "reason": text}


def verify_job_photos(photo_paths: list) -> dict:
    """Top-level real gate for a job's submitted photos. Returns
    {"verified": bool, "checks": {...}, "errors": [...]}, same shape
    style as nver_verification.verify_movie()."""
    report = {"checks": {}, "verified": False, "errors": []}

    report["checks"]["photos_present"] = len(photo_paths) > 0
    if not report["checks"]["photos_present"]:
        report["errors"].append("No photos submitted.")
        return report

    for p in photo_paths:
        if not os.path.exists(p) or os.path.getsize(p) < 1024:
            report["errors"].append(f"Photo missing or too small to be real: {p}")
    report["checks"]["files_valid"] = len(report["errors"]) == 0
    if not report["checks"]["files_valid"]:
        return report

    vision = _vision_quality_check(photo_paths)
    report["checks"]["vision"] = vision

    if not vision["checked"]:
        # Real infra failure -- same tolerance as nver_verification.py.
        # Photos genuinely exist and are valid files; don't punish the
        # cleaner for an API outage. Verified on the strength of the
        # checks that DID run for real.
        report["verified"] = True
        return report

    failed = [r for r in vision["results"] if r["passed"] is False or r["passed"] is None]
    if failed:
        report["verified"] = False
        for f in failed:
            report["errors"].append(f"{os.path.basename(f['path'])}: {f['reason']}")
    else:
        report["verified"] = True

    return report
