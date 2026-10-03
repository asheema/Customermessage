from __future__ import annotations
import re

PHONE_RE = re.compile(r'(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)')
EMAIL_RE = re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', re.I)
CARD_RE = re.compile(r'\b(?:\d[ -]*?){13,19}\b')
ACCOUNT_RE = re.compile(r'\b(?:account|a/c|acct)[\s:#-]*[A-Z0-9-]{4,}\b', re.I)

def redact_pii(text: str | None) -> tuple[str, list[str]]:
    if not text:
        return "", []
    redactions = []
    out = str(text)
    patterns = [(PHONE_RE, "[PHONE]", "phone"), (EMAIL_RE, "[EMAIL]", "email"),
                (CARD_RE, "[PAYMENT_DATA]", "payment"), (ACCOUNT_RE, "[ACCOUNT_ID]", "account")]
    for pattern, replacement, label in patterns:
        if pattern.search(out):
            out = pattern.sub(replacement, out)
            redactions.append(label)
    return out, redactions
