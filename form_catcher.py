import base64
import html
import json
import os
import sqlite3
import sys
import logging
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

sys.path.insert(0, os.path.expanduser("~/data_moat"))
from logger import log_event as data_moat_log_event

OPS_PASSWORD = os.getenv("OPS_PASSWORD", "")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
PUBLIC_DOMAIN = os.getenv("TT_PUBLIC_DOMAIN", "http://localhost:8080")

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
                    automatic_tax={"enabled": True},
                    customer_email=data.get("customer_email") or None,
                    metadata={
                        "bedroom_tier": quote.bedroom_tier,
                        "service_tier": quote.service_tier,
                        "addons": ",".join(quote.addons),
                        "same_day": str(quote.same_day),
                        "total": str(quote.total),
                    },
                    success_url=f"{PUBLIC_DOMAIN}/book?checkout=success",
                    cancel_url=f"{PUBLIC_DOMAIN}/book",
                )
            except stripe.StripeError as e:
                self._send_json(502, {"error": f"Payment provider error: {getattr(e, 'user_message', None) or str(e)}"})
                return
            self._send_json(200, {"checkout_url": session.url, "session_id": session.id, "total": quote.total})
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
