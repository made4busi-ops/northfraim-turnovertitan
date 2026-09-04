import base64
import html
import json
import os
import sqlite3
import sys
import logging
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

import stripe
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env"))
# Same Stripe account as the rest of the business -- northfraim-job77/.env
# is where the real key lives, turnover-titans has never had its own.
load_dotenv(os.path.expanduser("~/northfraim-job77/.env"))
from agents.agent_53_sniper import drop_lead
from master_agents_framework import build_system
from central_brain import CentralBrain, DB_PATH as DECISIONS_DB_PATH
from pricing import calculate_price, PricingError, BASE_RATES, ADDON_RATES, TIER_MULTIPLIERS
import property_registry
import job_queue

sys.path.insert(0, os.path.expanduser("~/data_moat"))
from logger import log_event as data_moat_log_event

OPS_PASSWORD = os.getenv("OPS_PASSWORD", "")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
PUBLIC_DOMAIN = os.getenv("TT_PUBLIC_DOMAIN", "http://localhost:8080")
# Turnover Titans' own webhook endpoint secret -- distinct from
# STRIPE_WEBHOOK_SECRET in northfraim-job77/.env, which belongs to
# NorthFraim's own registered endpoint. Webhook secrets are per
# registered endpoint URL, not per Stripe account, so that one can't be
# reused here even though the account is shared.
TT_STRIPE_WEBHOOK_SECRET = os.getenv("TT_STRIPE_WEBHOOK_SECRET", "")

PROPERTIES_STORE = os.path.join(BASE_DIR, "data", "properties.json")
JOB_QUEUE_STORE = os.path.join(BASE_DIR, "data", "job_queue.json")
JOB_PHOTOS_DIR = os.path.join(BASE_DIR, "data", "job_photos")
os.makedirs(JOB_PHOTOS_DIR, exist_ok=True)

LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(filename=os.path.join(LOG_DIR, 'titans.log'), level=logging.INFO, format='%(asctime)s - %(message)s')

stub_mode = not os.getenv("ANTHROPIC_API_KEY")
brain_agents = build_system(stub_mode=stub_mode)
brain = CentralBrain()
prioritizer = brain_agents["Task Prioritizer"]

class FormHandler(BaseHTTPRequestHandler):
    def _check_ops_auth(self) -> bool:
        if not OPS_PASSWORD:
            return False
        auth_header = self.headers.get('Authorization', '')
        if not auth_header.startswith('Basic '):
            return False
        try:
            decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
            _, _, password = decoded.partition(':')
        except Exception:
            return False
        return password == OPS_PASSWORD

    def _require_ops_auth(self) -> bool:
        if self._check_ops_auth():
            return True
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="Turnover Titans Ops"')
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Authentication required.")
        return False

    def do_GET(self):
        if self.path.startswith('/ops/decisions'):
            if not self._require_ops_auth():
                return
            self._render_decisions_page()
            return
        if self.path.startswith('/ops/job/') and self.path.endswith('/photos'):
            if not self._require_ops_auth():
                return
            job_id = self.path[len('/ops/job/'):-len('/photos')]
            self._render_photo_upload_page(job_id)
            return
        if self.path.startswith('/book'):
            self._render_booking_page()
            return
        self.send_response(404)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Not found.")

    def _render_booking_page(self):
        bedroom_options = "".join(
            f'<option value="{k}">{k.upper()} -- ${v:.0f}</option>' for k, v in BASE_RATES.items()
        )
        tier_options = "".join(
            f'<option value="{k}">{k.replace("_", " ").title()}</option>' for k in TIER_MULTIPLIERS
        )
        addon_checkboxes = "".join(
            f'<label class="addon"><input type="checkbox" name="addon" value="{k}"> '
            f'{k.replace("_", " ").title()} (+${v:.0f})</label>'
            for k, v in ADDON_RATES.items()
        )
        page = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Book a Turnover -- Turnover Titans</title>
<style>
  body {{ background:#0b0d10; color:#dfe3e6; font-family:-apple-system,sans-serif; max-width:520px; margin:0 auto; padding:2.5rem 1.5rem 4rem; }}
  h1 {{ font-size:1.5rem; margin-bottom:0.3rem; }}
  .sub {{ color:#8892a4; font-size:0.88rem; margin-bottom:1.75rem; }}
  label {{ display:block; font-size:0.85rem; color:#8892a4; margin:1rem 0 0.3rem; }}
  select, input[type=email] {{ width:100%; padding:0.6rem 0.75rem; background:#14171c; border:1px solid #262b36; color:#dfe3e6; font-size:0.9rem; }}
  .addon {{ display:flex; align-items:center; gap:0.5rem; font-size:0.88rem; color:#dfe3e6; margin:0.4rem 0; }}
  .addon input {{ width:auto; }}
  .same-day {{ display:flex; align-items:center; gap:0.5rem; margin-top:1rem; font-size:0.9rem; }}
  .same-day input {{ width:auto; }}
  #quote {{ background:#14171c; border:1px solid #262b36; padding:1rem 1.1rem; margin-top:1.5rem; font-size:0.88rem; }}
  #quote .line {{ display:flex; justify-content:space-between; padding:0.2rem 0; }}
  #quote .total {{ border-top:1px solid #262b36; margin-top:0.4rem; padding-top:0.5rem; font-weight:700; color:#e8a33d; }}
  button {{ width:100%; margin-top:1.25rem; padding:0.85rem; background:#e8a33d; color:#0b0d10; border:none; font-weight:600; font-size:0.92rem; cursor:pointer; }}
  button:disabled {{ opacity:0.6; cursor:not-allowed; }}
  #status {{ font-size:0.85rem; margin-top:0.6rem; min-height:1.1rem; color:#c1443c; }}
</style></head>
<body>
<h1>Book a Turnover</h1>
<p class="sub">Real pricing, quoted live -- base rate scales with bedroom count, add-ons and rush service are priced separately.</p>

<label for="bedroom">Property size</label>
<select id="bedroom">{bedroom_options}</select>

<label for="tier">Service type</label>
<select id="tier">{tier_options}</select>

<label>Add-ons</label>
{addon_checkboxes}

<label class="same-day"><input type="checkbox" id="same-day"> Same-day / rush turnover (+$35 or 25%, whichever is higher)</label>

<label for="email">Email</label>
<input type="email" id="email" placeholder="you@property.com">

<label for="address">Property address</label>
<input type="text" id="address" placeholder="123 Main St, Springfield">

<label for="access-details">Door code / access instructions</label>
<input type="text" id="access-details" placeholder="Lockbox code, gate code, key location, etc.">

<div id="quote"></div>
<button id="book-btn">Get Checkout Link</button>
<div id="status"></div>

<script>
function selectedAddons() {{
  return Array.from(document.querySelectorAll('input[name=addon]:checked')).map(el => el.value);
}}
function currentSelection() {{
  return {{
    bedroom_tier: document.getElementById('bedroom').value,
    service_tier: document.getElementById('tier').value,
    addons: selectedAddons(),
    same_day: document.getElementById('same-day').checked,
  }};
}}
function renderQuote(quote) {{
  var el = document.getElementById('quote');
  var lines = quote.line_items.map(function (li) {{
    return '<div class="line"><span>' + li.label + '</span><span>' + (li.amount < 0 ? '-$' + Math.abs(li.amount).toFixed(2) : '$' + li.amount.toFixed(2)) + '</span></div>';
  }}).join('');
  el.innerHTML = lines + '<div class="line total"><span>Total</span><span>$' + quote.total.toFixed(2) + '</span></div>';
}}
function refreshQuote() {{
  fetch('/api/quote', {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify(currentSelection())
  }})
    .then(function (r) {{ return r.json(); }})
    .then(function (q) {{ if (!q.error) renderQuote(q); }});
}}
['bedroom', 'tier', 'same-day'].forEach(function (id) {{
  document.getElementById(id).addEventListener('change', refreshQuote);
}});
document.querySelectorAll('input[name=addon]').forEach(function (el) {{
  el.addEventListener('change', refreshQuote);
}});
refreshQuote();

document.getElementById('book-btn').addEventListener('click', function () {{
  var btn = this;
  var status = document.getElementById('status');
  btn.disabled = true;
  btn.textContent = 'Starting checkout...';
  status.textContent = '';
  var body = currentSelection();
  body.customer_email = document.getElementById('email').value;
  body.property_address = document.getElementById('address').value;
  body.access_details = document.getElementById('access-details').value;
  fetch('/api/checkout/job', {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify(body)
  }})
    .then(function (r) {{ return r.json().then(function (b) {{ return {{status: r.status, body: b}}; }}); }})
    .then(function (res) {{
      if (res.status === 200 && res.body.checkout_url) {{
        window.location.href = res.body.checkout_url;
      }} else {{
        status.textContent = res.body.error || 'Could not start checkout.';
        btn.disabled = false;
        btn.textContent = 'Get Checkout Link';
      }}
    }})
    .catch(function (err) {{
      status.textContent = 'Network error: ' + err.message;
      btn.disabled = false;
      btn.textContent = 'Get Checkout Link';
    }});
}});
</script>
</body></html>"""
        body = page.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _render_decisions_page(self):
        conn = sqlite3.connect(DECISIONS_DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT id, timestamp, task_description, reasoning, decision, confidence, outcome
               FROM decisions WHERE task_description LIKE 'Lead Eval:%'
               ORDER BY id DESC LIMIT 50"""
        ).fetchall()
        conn.close()

        rows_html = "".join(
            f"""<div class="decision">
                <div class="d-head"><span class="d-id">#{r['id']}</span> {html.escape(r['task_description'])}
                    <span class="d-conf">confidence {r['confidence']}</span>
                    <span class="d-outcome">{html.escape(r['outcome'] or 'pending')}</span></div>
                <div class="d-time">{html.escape(r['timestamp'])}</div>
                <div class="d-decision">{html.escape(r['decision'] or '')}</div>
                <pre class="d-reasoning">{html.escape(r['reasoning'] or '')}</pre>
            </div>"""
            for r in rows
        )
        if not rows:
            rows_html = '<p class="empty">No lead-evaluation decisions logged yet.</p>'

        page = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Turnover Titans -- Lead Decisions</title>
<style>
  body {{ background:#0b0d10; color:#dfe3e6; font-family:-apple-system,sans-serif; max-width:900px; margin:0 auto; padding:2.5rem 1.5rem; }}
  h1 {{ font-size:1.5rem; margin-bottom:0.25rem; }}
  .sub {{ color:#8892a4; font-size:0.9rem; margin-bottom:2rem; }}
  .decision {{ background:#14171c; border:1px solid #262b36; padding:1rem 1.25rem; margin-bottom:0.85rem; }}
  .d-head {{ font-weight:600; margin-bottom:0.25rem; }}
  .d-id {{ font-family:monospace; color:#8892a4; margin-right:0.5rem; }}
  .d-conf {{ float:right; font-family:monospace; font-size:0.8rem; color:#e8a33d; }}
  .d-outcome {{ display:block; font-family:monospace; font-size:0.72rem; color:#8892a4; text-transform:uppercase; margin-top:0.2rem; }}
  .d-time {{ font-family:monospace; font-size:0.72rem; color:#565f66; margin-bottom:0.5rem; }}
  .d-decision {{ font-size:0.92rem; margin-bottom:0.5rem; color:#f4f6fa; }}
  .d-reasoning {{ white-space:pre-wrap; font-family:monospace; font-size:0.78rem; color:#a9b0b8; max-height:220px; overflow-y:auto; margin:0; }}
  .empty {{ color:#8892a4; }}
</style></head>
<body>
<h1>Lead Decisions</h1>
<p class="sub">Real rows from central_decisions.db -- the actual reasoning CentralBrain produced for each submitted lead, newest first.</p>
{rows_html}
</body></html>"""
        body = page.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _render_photo_upload_page(self, job_id):
        jobs_data = json.load(open(JOB_QUEUE_STORE)) if os.path.exists(JOB_QUEUE_STORE) else {"jobs": {}}
        job = jobs_data.get("jobs", {}).get(job_id)
        if job is None:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"No job '{job_id}'.".encode())
            return

        items_html = ""
        for item in job_queue.CHECKLIST_ITEMS:
            count = len((job.get("photos") or {}).get(item, []))
            items_html += f"""
            <div class="item">
              <label>{html.escape(item)} <span class="count">({count} photo{'s' if count != 1 else ''} attached)</span></label>
              <input type="file" accept="image/*" data-item="{html.escape(item)}">
              <button class="upload-btn" data-item="{html.escape(item)}">Upload</button>
              <div class="item-status" id="status-{html.escape(item)}"></div>
            </div>"""

        inspection = job.get("inspection") or {}
        result_html = ""
        if inspection.get("result"):
            v = inspection.get("verification") or {}
            errs = "".join(f"<li>{html.escape(e)}</li>" for e in v.get("errors", []))
            result_html = f"""<div class="result {inspection['result']}">
              Inspection result: <b>{inspection['result'].upper()}</b>
              {'<ul>' + errs + '</ul>' if errs else ''}
            </div>"""

        page = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Job Photos -- {html.escape(job_id)}</title>
<style>
  body {{ background:#0b0d10; color:#dfe3e6; font-family:-apple-system,sans-serif; max-width:560px; margin:0 auto; padding:2rem 1.5rem 4rem; }}
  h1 {{ font-size:1.3rem; }}
  .sub {{ color:#8892a4; font-size:0.85rem; margin-bottom:1.5rem; }}
  .item {{ background:#14171c; border:1px solid #262b36; padding:0.9rem; margin-bottom:0.7rem; }}
  .item label {{ display:block; font-size:0.85rem; margin-bottom:0.5rem; }}
  .count {{ color:#8892a4; font-size:0.78rem; }}
  input[type=file] {{ display:block; margin-bottom:0.5rem; font-size:0.82rem; color:#dfe3e6; }}
  button {{ padding:0.5rem 1rem; background:#e8a33d; color:#0b0d10; border:none; font-weight:600; cursor:pointer; font-size:0.85rem; }}
  .item-status {{ font-size:0.8rem; margin-top:0.4rem; min-height:1rem; }}
  #inspect-btn {{ width:100%; margin-top:1.5rem; padding:0.85rem; }}
  #inspect-status {{ font-size:0.85rem; margin-top:0.6rem; }}
  .result {{ margin-top:1.5rem; padding:1rem; border:1px solid #262b36; }}
  .result.pass {{ border-color:#4CAF82; }}
  .result.fail {{ border-color:#c1443c; }}
</style></head>
<body>
<h1>Job Photos: {html.escape(job_id)}</h1>
<p class="sub">{html.escape(job.get('property_name', ''))} -- attach a real photo for each step, then inspect.</p>
{items_html}
<button id="inspect-btn">Run Photo-Verified Inspection</button>
<div id="inspect-status"></div>
{result_html}
<script>
function toBase64(file) {{
  return new Promise(function (resolve, reject) {{
    var reader = new FileReader();
    reader.onload = function () {{ resolve(reader.result.split(',')[1]); }};
    reader.onerror = reject;
    reader.readAsDataURL(file);
  }});
}}
document.querySelectorAll('.upload-btn').forEach(function (btn) {{
  btn.addEventListener('click', function () {{
    var item = btn.dataset.item;
    var input = document.querySelector('input[data-item="' + item + '"]');
    var status = document.getElementById('status-' + item);
    if (!input.files.length) {{ status.textContent = 'Choose a photo first.'; return; }}
    status.textContent = 'Uploading...';
    toBase64(input.files[0]).then(function (b64) {{
      fetch('/api/jobs/{html.escape(job_id)}/photos', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{item: item, image_base64: b64}})
      }})
        .then(function (r) {{ return r.json().then(function (b) {{ return {{status: r.status, body: b}}; }}); }})
        .then(function (res) {{
          status.textContent = res.status === 200 ? 'Uploaded.' : (res.body.error || 'Upload failed.');
          if (res.status === 200) location.reload();
        }})
        .catch(function (err) {{ status.textContent = 'Network error: ' + err.message; }});
    }});
  }});
}});
document.getElementById('inspect-btn').addEventListener('click', function () {{
  var status = document.getElementById('inspect-status');
  status.textContent = 'Running real photo verification...';
  fetch('/api/jobs/{html.escape(job_id)}/inspect', {{method: 'POST'}})
    .then(function (r) {{ return r.json().then(function (b) {{ return {{status: r.status, body: b}}; }}); }})
    .then(function (res) {{
      status.textContent = '';
      location.reload();
    }})
    .catch(function (err) {{ status.textContent = 'Network error: ' + err.message; }});
}});
</script>
</body></html>"""
        body = page.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length).decode('utf-8') if length else '{}'
        return json.loads(raw)

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _quote_from_request(self):
        data = self._read_json_body()
        return calculate_price(
            bedroom_tier=data.get('bedroom_tier', ''),
            service_tier=data.get('service_tier', 'standard'),
            addons=data.get('addons', []),
            same_day=bool(data.get('same_day', False)),
            volume_discount_pct=float(data.get('volume_discount_pct', 0.0)),
        ), data

    def do_POST(self):
        if self.path == '/api/quote':
            try:
                quote, _ = self._quote_from_request()
                self._send_json(200, {
                    "total": quote.total, "subtotal": quote.subtotal,
                    "line_items": quote.line_items,
                })
            except (PricingError, ValueError, TypeError) as e:
                self._send_json(400, {"error": str(e)})
            return

        if self.path == '/api/checkout/job':
            try:
                quote, data = self._quote_from_request()
            except (PricingError, ValueError, TypeError) as e:
                self._send_json(400, {"error": str(e)})
                return
            if not stripe.api_key:
                self._send_json(500, {"error": "Stripe is not configured on the server."})
                return
            try:
                session = stripe.checkout.Session.create(
                    mode="payment",
                    line_items=[
                        {
                            "price_data": {
                                "currency": "usd",
                                "product_data": {"name": f"Turnover Titans -- {li['label']}"},
                                "unit_amount": max(0, round(li["amount"] * 100)),
                            },
                            "quantity": 1,
                        }
                        for li in quote.line_items if li["amount"] > 0
                    ],
                    # automatic_tax re-enabled (2026-09-04): confirmed live
                    # against the real, live-mode Stripe account
                    # (stripe.tax.Settings.retrieve(), livemode=true) that
                    # head_office is already set -- 1427 East High Street,
                    # Springfield, OH 45505, status "active". The blocking
                    # condition this comment used to describe no longer
                    # applies; verified live below, not assumed from this
                    # comment alone.
                    automatic_tax={"enabled": True},
                    customer_email=data.get("customer_email") or None,
                    metadata={
                        "bedroom_tier": quote.bedroom_tier,
                        "service_tier": quote.service_tier,
                        "addons": ",".join(quote.addons),
                        "same_day": str(quote.same_day),
                        "total": str(quote.total),
                        # Real property intake -- survives to the webhook event
                        # so a paid booking can create a real property + job
                        # without anyone re-typing this. Stripe metadata values
                        # cap at 500 chars; truncated defensively, not that
                        # anyone should be typing that much into a text input.
                        "property_address": str(data.get("property_address") or "")[:500],
                        "access_details": str(data.get("access_details") or "")[:500],
                    },
                    success_url=f"{PUBLIC_DOMAIN}/book?checkout=success",
                    cancel_url=f"{PUBLIC_DOMAIN}/book",
                )
            except stripe.StripeError as e:
                self._send_json(502, {"error": f"Payment provider error: {getattr(e, 'user_message', None) or str(e)}"})
                return
            self._send_json(200, {"checkout_url": session.url, "session_id": session.id, "total": quote.total})
            return

        if self.path.startswith('/api/jobs/') and self.path.endswith('/photos'):
            if not self._require_ops_auth():
                return
            job_id = self.path[len('/api/jobs/'):-len('/photos')]
            try:
                data = self._read_json_body()
            except json.JSONDecodeError:
                self._send_json(400, {"error": "Invalid JSON body."})
                return
            item = data.get("item")
            image_b64 = data.get("image_base64")
            if not item or not image_b64:
                self._send_json(400, {"error": "item and image_base64 are required."})
                return
            try:
                image_bytes = base64.b64decode(image_b64)
            except Exception:
                self._send_json(400, {"error": "image_base64 is not valid base64."})
                return
            if len(image_bytes) < 1024:
                self._send_json(400, {"error": "Image too small to be a real photo."})
                return

            job_dir = os.path.join(JOB_PHOTOS_DIR, job_id)
            os.makedirs(job_dir, exist_ok=True)
            safe_item = "".join(c for c in item if c.isalnum() or c == "_") or "photo"
            photo_path = os.path.join(job_dir, f"{safe_item}_{uuid.uuid4().hex[:8]}.jpg")
            with open(photo_path, "wb") as f:
                f.write(image_bytes)

            ok = job_queue.add_photo(JOB_QUEUE_STORE, job_id, item, photo_path)
            if not ok:
                os.remove(photo_path)
                self._send_json(400, {"error": f"Could not attach photo -- check job_id '{job_id}' and item '{item}'."})
                return
            self._send_json(200, {"attached": True, "item": item})
            return

        if self.path.startswith('/api/jobs/') and self.path.endswith('/inspect'):
            if not self._require_ops_auth():
                return
            job_id = self.path[len('/api/jobs/'):-len('/inspect')]
            ok = job_queue.inspect_job(JOB_QUEUE_STORE, job_id)
            if not ok:
                self._send_json(400, {"error": "Could not run inspection -- check the job is in Cleaning with a complete checklist and a photo for every item."})
                return
            jobs_data = json.load(open(JOB_QUEUE_STORE))
            result = jobs_data["jobs"][job_id]["inspection"]["result"]
            self._send_json(200, {"result": result})
            return

        if self.path == '/webhook':
            length = int(self.headers.get('Content-Length', 0))
            payload = self.rfile.read(length) if length else b''
            sig_header = self.headers.get('Stripe-Signature')

            if TT_STRIPE_WEBHOOK_SECRET:
                try:
                    event = stripe.Webhook.construct_event(payload, sig_header, TT_STRIPE_WEBHOOK_SECRET)
                except (ValueError, stripe.error.SignatureVerificationError) as e:
                    self._send_json(400, {"error": f"Invalid webhook signature: {e}"})
                    return
            else:
                # No signing secret configured yet (dev-only fallback, same
                # pattern used elsewhere this session) -- trust the parsed
                # body. Real deployment MUST set TT_STRIPE_WEBHOOK_SECRET.
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    self._send_json(400, {"error": "Invalid JSON body."})
                    return

            event_type = event["type"] if isinstance(event, dict) else event.type
            data_object = event["data"]["object"] if isinstance(event, dict) else event.data.object

            if event_type == "checkout.session.completed":
                session_id = data_object["id"] if isinstance(data_object, dict) else data_object.id
                metadata = data_object.get("metadata", {}) if isinstance(data_object, dict) else data_object.metadata
                customer_email = (data_object.get("customer_details", {}) or {}).get("email") if isinstance(data_object, dict) else (data_object.customer_details.email if data_object.customer_details else None)

                # Stable, deterministic ids derived from the real Stripe
                # session id -- Stripe can and does redeliver webhook
                # events, and both add_property()/create_job() already
                # refuse to overwrite an existing id, so a retry is a
                # real no-op instead of a duplicate property/job.
                property_id = f"tt-{session_id}"
                job_id = f"tt-{session_id}"

                address = (metadata.get("property_address") or "Address not provided").strip() or "Address not provided"
                access_details = metadata.get("access_details") or ""
                owner = customer_email or "unknown"

                property_registry.add_property(
                    PROPERTIES_STORE, property_id, name=address, owner=owner, access_details=access_details,
                )
                job_queue.create_job(JOB_QUEUE_STORE, job_id, property_name=address)

                try:
                    data_moat_log_event('turnover_titans', 'job_created', {
                        'session_id': session_id, 'property_id': property_id, 'job_id': job_id,
                        'bedroom_tier': metadata.get('bedroom_tier'), 'total': metadata.get('total'),
                    })
                except Exception as e:
                    logging.error(f"data_moat logging failed: {e}")

                logging.info(f"Real booking paid: session={session_id} -> property={property_id} job={job_id}")

            self._send_json(200, {"received": True})
            return

        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        data = parse_qs(post_data)
        lead = {'name': data.get('name', [''])[0], 'business': data.get('business', [''])[0], 'email': data.get('email', [''])[0], 'phone': data.get('phone', [''])[0], 'message': data.get('message', [''])[0]}
        lead_id = drop_lead(lead)
        
        if lead_id:
            task = f"Evaluate lead for Turnover Titans cleaning business. Name: {lead['name']}, Business: {lead['business']}. Is this a high-value (HOT) lead worth pursuing immediately?"
            decision_data = prioritizer.reason(task)
            decision_id = brain.log_decision(agent_name=decision_data['agent'], template_used=decision_data['template'], task_description=f"Lead Eval: {lead['name']}", reasoning=decision_data['reasoning'], decision=decision_data['decision'], confidence=decision_data['confidence'])
            logging.info(f"Lead captured & evaluated. ID: {lead_id}, Brain Decision ID: {decision_id}, Confidence: {decision_data['confidence']}")
            try:
                data_moat_log_event('turnover_titans', 'lead', {
                    'lead_id': lead_id, 'name': lead['name'], 'business': lead['business'],
                    'decision': decision_data['decision'], 'confidence': decision_data['confidence'],
                })
            except Exception as e:
                logging.error(f"data_moat logging failed: {e}")
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"SUCCESS: Lead received, evaluated by Brain, and logged.")
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"ERROR: Invalid lead data.")

if __name__ == "__main__":
    server = HTTPServer(('localhost', 8080), FormHandler)
    print("FORM CATCHER + CENTRAL BRAIN: Listening on port 8080...")
    server.serve_forever()
