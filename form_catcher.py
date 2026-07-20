from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
import os
import sys
import logging

# Add parent dir to path to import agent_53
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from agents.agent_53_sniper import drop_lead

# Setup logging for the web server
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(filename=os.path.join(LOG_DIR, "titans.log"), level=logging.INFO, 
                    format='%asctime%s - %levelname - %message')

class FormHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/submit':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            fields = parse_qs(post_data)
            
            lead_data = {
                "name": fields.get('name', ['Unknown'])[0],
                "business": fields.get('business', ['Website Lead'])[0],
                "platform": "Website Form",
                "details": fields.get('message', [''])[0]
            }
            
            logging.info(f"Form received: {lead_data}")
            lead_id = drop_lead(lead_data)
            
            if lead_id:
                self.send_response(302)
                self.send_header('Location', '/?status=success')
                self.end_headers()
            else:
                logging.error(f"Failed to drop lead from form: {lead_data}")
                self.send_response(500)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Error processing request.")
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    port = 8081
    server = HTTPServer(('127.0.0.1', port), FormHandler) # Locked to localhost
    print(f"Form Catcher running on localhost:{port}")
    server.serve_forever()
