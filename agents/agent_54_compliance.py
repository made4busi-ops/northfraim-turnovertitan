import sys

def validate_lead(lead_data):
    """
    Validates lead data to ensure name and business are present.
    Expects a dictionary with 'name' and 'business' keys.
    """
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
    # Quick local test
    test_lead = {"name": "Derrick", "business": "Turnover Titans"}
    is_valid, msg = validate_lead(test_lead)
    if is_valid:
        print("AGENT 54: Validation passed.")
    else:
        print(f"AGENT 54: Validation failed - {msg}")
