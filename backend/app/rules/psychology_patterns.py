"""Weighted coercive constructions, rather than isolated institution or payment words."""
# (reason code, regex, evidence weight). Patterns operate on normalized sentences.
PATTERNS = {
    'authority': [
        ('authority_claim_detected', r"\b(?:i am|i'm|we are|calling from|speaking from|i represent)\b.{0,55}\b(?:police|rbi|government|cyber\s*crime|bank officer|bank|court|tax department|company support|employer|chief executive)\b", .84),
        ('authority_claim_detected', r'\b(?:main|hum)\b.{0,35}\b(?:bank|rbi|police|cyber\s*crime|sarkar|court)\b.{0,35}\b(?:bol raha|bol rahi|se hu|se hoon|se hain)\b', .86),
        ('official_investigation_claim', r'\b(?:confidential|official)\b.{0,25}\b(?:police|government|cyber\s*crime)\b.{0,20}\binvestigation\b', .80),
        ('authority_role_claim', r'\b(?:as your|your assigned|this is|main)\b.{0,25}\b(?:bank officer|police officer|tax officer|support officer|senior executive|officer)\b', .75),
    ],
    'fear': [
        ('legal_threat_detected', r'\b(?:you|your|aap|aapka|tum|tumhara)\b.{0,70}\b(?:arrested|arrest|frozen|freeze|blocked|legal action|police case|penalty|jail|custody)\b', .84),
        ('conditional_threat_detected', r'\b(?:or|otherwise|warna|nahi to)\b.{0,35}\b(?:arrest|jail|freeze|frozen|blocked|block|legal action|penalty|case)\b', .82),
        ('legal_threat_detected', r'\blegal action\b.{0,18}\b(?:will be taken|against you|hoga|hogi)\b', .78),
        ('identity_crime_threat', r'\byour\b.{0,20}\b(?:aadhaar|identity)\b.{0,45}\b(?:money laundering|illegal|criminal)\b', .72),
    ],
    'urgency': [
        ('urgent_action_language', r'\b(?:transfer|pay|send|invest|deposit|payment karo|bhejo)\b.{0,40}\b(?:now|immediately|right now|today|abhi|aaj)\b', .83),
        ('urgent_action_language', r'\b(?:immediately|right now|abhi|aaj hi)\b.{0,35}\b(?:transfer|pay|send|invest|payment|bhejo|karo)\b', .83),
        ('short_payment_deadline', r'\b(?:within|sirf)\s+\d+\s+(?:minutes|min|minute)\b|\b(?:do not delay|act now|today only)\b', .76),
        ('same_day_expiry_pressure', r'\b(?:aaj|today|tonight)\b.{0,18}\b(?:last|only|expires|akhri)\b|\b(?:offer|opportunity)\b.{0,15}\bexpires (?:today|tonight)\b', .77),
    ],
    'scarcity': [
        ('limited_availability_claim', r'\b(?:only|sirf)\s+(?:\d+|one|two|few|ek|do)\s+(?:slots?|seats?|places?)\b|\b(?:last|limited|akhri)\s+(?:slot|slots|seat|opportunity|investment opportunity|chance)\b', .84),
        ('expiring_offer_claim', r'\b(?:offer|opportunity|allocation)\b.{0,20}\b(?:expires|limited|last)\b', .76),
    ],
    'trust': [
        ('credibility_appeal', r'\b(?:you can trust me|trust me|i am helping you|i have handled many cases|bharosa karo|mujh par bharosa|meri baat mano)\b', .79),
        ('relationship_trust_appeal', r'\bif you\b.{0,15}\bcare about me\b|\b(?:agar|tum)\b.{0,25}\b(?:pyar|pyaar|care)\b', .75),
        ('relationship_trust_appeal', r'\b(?:we have been together|our relationship|apna rishta)\b.{0,35}\b(?:trust|help me|bharosa|madad)\b', .72),
    ],
    'reward': [
        ('guaranteed_gain_claim', r'\bguaranteed\s+(?:\d+\s*%?\s*)?(?:returns?|profits?|gains?|cashback)\b|\b(?:investment|return|profit)\s+guaranteed\b', .85),
        ('doubling_or_prize_claim', r'\b(?:double your (?:money|investment)|money will double|paise double|high profit|lottery prize|assured returns|pakka return|return milega)\b', .77),
        ('reward_payment_inducement', r'\b(?:cashback|bonus|lottery)\b.{0,30}\b(?:receive|claim|milega|win)\b', .72),
    ],
    'social_proof': [
        ('others_benefited_claim', r'\b(?:thousands|hundreds|many users|many members|everyone|sab log|hazaron|bahut log)\b.{0,65}\b(?:earned|profit|benefited|kamaya|kama rahe|return mila)\b', .84),
        ('peer_success_claim', r'\b(?:other members|your friends|dusre members|aapke dost)\b.{0,55}\b(?:successful|profits?|joined|earned|kamaya)\b', .74),
    ],
    'secrecy': [
        ('secrecy_request_detected', r"\b(?:do not|don't|dont|never)\s+(?:tell|contact|discuss|inform|share)\b.{0,55}\b(?:anyone|family|bank|police|friends|investigation)\b", .88),
        ('secrecy_request_detected', r'\b(?:kisi ko|family ko|bank ko|ghar par)\s+mat\s+(?:batana|batao|bolna)|\bye baat\b.{0,15}\bsecret\b', .88),
        ('confidential_investigation_pressure', r'\b(?:investigation|inquiry|case)\b.{0,20}\bconfidential\b|\bconfidential\b.{0,20}\binvestigation\b', .65),
    ],
    'commitment': [
        ('prior_payment_leverage', r"\b(?:already|pehle|you've already)\b.{0,35}\b(?:invested|paid|sent|jama|payment)\b.{0,100}\b(?:more|extra|unlock|withdrawal|aur|dobara)\b", .86),
        ('withdrawal_unlock_payment', r'\b(?:pay|send|deposit|payment)\b.{0,40}\b(?:more|extra|additional|aur)\b.{0,40}\b(?:unlock|withdrawal|release|nikalne)\b', .81),
    ],
    'emotional_pressure': [
        ('conditional_care_pressure', r'\bif you\b.{0,15}\bcare about me\b.{0,70}\b(?:send|pay|money|help)\b', .86),
        ('medical_emergency_money_appeal', r'\b(?:i|my family|mujhe|meri family)\b.{0,30}\b(?:urgently need|desperately need|emergency|hospital)\b.{0,60}\b(?:money|payment|paise|treatment)\b', .76),
        ('relationship_emotional_pressure', r'\b(?:agar|tum)\b.{0,25}\b(?:pyar|pyaar|care)\b.{0,55}\b(?:paise|bhejo|madad|send)\b', .84),
    ],
}
# Suppression is sentence-scoped and never overrides positive evidence elsewhere.
BENIGN_QUALIFIERS = {
    'authority': r'\b(?:announced|released|published|guidelines|new policy|statement.{0,25}available|news article)\b',
    'fear': r'\bmy (?:bank )?account is (?:frozen|blocked)\b|\bmera account freeze\b',
    'urgency': r'\b(?:if convenient|when convenient|no rush|not urgent|due tomorrow|koi jaldi nahi|jab suvidha|aaram se)\b',
    'reward': r'\b(?:no guaranteed|not guaranteed|returns are not|profit is not|koi guaranteed.{0,10}nahi)\b',
    'scarcity': r'\b(?:no limited|not limited|no shortage|ample places)\b',
    'trust': r'\b(?:i trust my|trusted existing|known recipient)\b',
    'social_proof': r'\b(?:survey results|news report|statistics published)\b',
    'secrecy': r'\b(?:not confidential|please tell your|do contact your)\b',
    'commitment': r'\b(?:scheduled instalment|regular installment|no extra payment)\b',
    'emotional_pressure': r'\b(?:no emergency|routine hospital bill|not an emergency)\b',
}
