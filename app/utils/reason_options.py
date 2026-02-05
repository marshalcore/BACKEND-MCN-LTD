"""
Reason options configuration for application tiers.
Regular tier: 1-3 selections
VIP tier: Unlimited selections
"""

REASON_OPTIONS = {
    "regular": [
        {"code": "employment", "text": "Seeking Employment & Work"},
        {"code": "skill_training", "text": "Skill Acquisition & Handwork Training"},
        {"code": "armed_forces", "text": "Armed Forces Preparation"},
        {"code": "personal_dev", "text": "Personal Development & Discipline"},
        {"code": "basic_ict", "text": "ICT Knowledge & Basic Computer Skills"}
    ],
    "vip": [
        {"code": "security_association", "text": "Security Association & Legal Protection"},
        {"code": "full_tech", "text": "Tech Career Pathway (Full SXTM Training)"},
        {"code": "networking", "text": "Networking & Professional Status Enhancement"},
        {"code": "security_awareness", "text": "Security Awareness & Risk Management"},
        {"code": "business_protection", "text": "Business Protection & Organizational Backup"},
        {"code": "advanced_ict", "text": "Advanced ICT & Cybersecurity Education"},
        {"code": "executive_training", "text": "Personal Development & Executive Training"}
    ]
}

def get_reasons_for_tier(tier: str):
    """Get available reasons for tier"""
    return REASON_OPTIONS.get(tier, [])

def validate_reasons_selection(tier: str, selected_codes: list):
    """Validate selected reasons against tier rules"""
    available_codes = [r["code"] for r in get_reasons_for_tier(tier)]
    
    # Check all selected are available
    for code in selected_codes:
        if code not in available_codes:
            return False, f"Reason '{code}' not available for {tier} tier"
    
    # Check count limits
    if tier == "regular":
        if len(selected_codes) < 1:
            return False, "Select at least 1 reason"
        if len(selected_codes) > 3:
            return False, "Maximum 3 reasons for Regular tier"
    
    elif tier == "vip":
        if len(selected_codes) < 1:
            return False, "Select at least 1 reason"
        # No maximum for VIP
    
    return True, "Valid"

def get_reason_text(code: str, tier: str = None):
    """Get human-readable text for a reason code"""
    if tier:
        for reason in REASON_OPTIONS.get(tier, []):
            if reason["code"] == code:
                return reason["text"]
    
    # If no tier specified or not found, search all
    for tier_reasons in REASON_OPTIONS.values():
        for reason in tier_reasons:
            if reason["code"] == code:
                return reason["text"]
    
    return code  # Return code itself if not found