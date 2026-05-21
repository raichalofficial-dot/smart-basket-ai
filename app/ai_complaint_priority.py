
def analyze_complaint_text(text):
    """
    Analyzes keywords in the complaint text to determine priority.
    """
    text = text.lower()
    
    high_keywords = [
        "fraud", "not delivered", "money deducted", "payment failed", 
        "payment issue", "wrong item", "damaged", "missing item", 
        "refund not received", "scam"
    ]
    
    medium_keywords = [
        "late", "delay", "slow delivery", "late delivery", "delivery delay",
        "not responding", "slow"
    ]
    
    if any(word in text for word in high_keywords):
        return "HIGH"
    elif any(word in text for word in medium_keywords):
        return "MEDIUM"
    else:
        return "LOW"

def detect_priority(text):
    """
    Helper function to detect priority from text.
    """
    return analyze_complaint_text(text)

def assign_priority(text):
    """
    Returns a dictionary with text and assigned priority.
    """
    priority = detect_priority(text)
    return {
        "complaint": text,
        "priority": priority
    }
