import os
import sys
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
from agents.agent_53_sniper import drop_lead
from master_agents_framework import build_system
from central_brain import CentralBrain

LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(filename=os.path.join(LOG_DIR, 'titans.log'), level=logging.INFO, format='%(asctime)s - %(message)s')

stub_mode = not os.getenv("ANTHROPIC_API_KEY")
brain_agents = build_system(stub_mode=stub_mode)
brain = CentralBrain()
prioritizer = brain_agents["Task Prioritizer"]

class FormHandler(BaseHTTPRequestHandler):
    def do_POST(self):
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
