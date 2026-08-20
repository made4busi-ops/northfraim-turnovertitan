import os
import anthropic
from dotenv import load_dotenv
load_dotenv()

class MasterAgent:
    def __init__(self, name, template, api_client=None):
        self.name = name
        self.template = template
        self.api_client = api_client

    def reason(self, task):
        if not self.api_client:
            return {
                "agent": self.name,
                "template": self.template["name"],
                "reasoning": f"[Mock Mode] {self.template['logic']}",
                "decision": f"Execute task: {task}",
                "confidence": 0.85
            }
        
        message = self.api_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            temperature=0.7,
            system=self.template["system_prompt"],
            messages=[{"role": "user", "content": task}]
        )
        
        response_text = message.content[0].text
        return {
            "agent": self.name,
            "template": self.template["name"],
            "reasoning": response_text,
            "decision": "Processed by Claude",
            "confidence": 0.95
        }

def build_system(stub_mode=False):
    tim_ferriss_template = {
        "name": "Tim Ferriss 80/20",
        "system_prompt": "You are a Tim Ferriss AI. Apply 80/20 analysis. What is the 20% of effort that yields 80% of results? Be fast, fear-set, and ship.",
        "logic": "80/20 rule applied. Ship fast."
    }
    anti_patterns_template = {
        "name": "Anti-Patterns Safety",
        "system_prompt": "You are an Anti-Patterns AI. Check for glitches, decision failures, and edge cases. Provide safety workarounds.",
        "logic": "Safety check applied. No glitches detected."
    }

    api_client = None
    if not stub_mode:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            api_client = anthropic.Anthropic(api_key=api_key)

    agents = {
        "Task Prioritizer": MasterAgent("Task Prioritizer", tim_ferriss_template, api_client),
        "Safety Checker": MasterAgent("Safety Checker", anti_patterns_template, api_client)
    }
    return agents
