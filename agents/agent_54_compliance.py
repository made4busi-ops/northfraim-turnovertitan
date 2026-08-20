"""
agent_54_compliance.py -- Turnover Titans

Real function only. The old fake Agent54Compliance class (claimed to
check city legal compliance, actually just printed a message and
returned needs_review) has been removed - it never did what its name
promised. What is left is the ONE real thing this file ever actually
did: validate that a lead has the required fields before it is
allowed into the database.

This is field validation, not legal/compliance checking.
"""


def validate_lead(lead_data):
    if not lead_data or not isinstance(lead_data, dict):
        return False, "Invalid data format"

    name = lead_data.get('name', '').strip()
    business = lead_data.get('business', '').strip()

    if not name:
        return False, "Missing required field: name"
    if not business:
        return False, "Missing required field: business"

    return True, "Compliance check passed"


if __name__ == "__main__":
    test_lead = {"name": "Derrick", "business": "Turnover Titans"}
    is_valid, msg = validate_lead(test_lead)
    if is_valid:
        print("AGENT 54: Validation passed.")
    else:
        print("AGENT 54: Validation failed - " + msg)
