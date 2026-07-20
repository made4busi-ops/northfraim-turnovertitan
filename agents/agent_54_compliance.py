def check_compliance(lead_data):
    """Checks if a lead is compliant."""
    if not lead_data.get('name') or not lead_data.get('business'):
        return False, "Missing name or business"
    return True, "Compliant"
