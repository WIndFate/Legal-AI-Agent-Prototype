import re

# PII detection patterns for Japanese contracts
PII_PATTERNS = [
    {"type": "phone", "pattern": r"0[0-9]{1,4}[-ー]?[0-9]{1,4}[-ー]?[0-9]{3,4}"},
    {"type": "mynumber", "pattern": r"[0-9０-９]{4}\s?[0-9０-９]{4}\s?[0-9０-９]{4}"},
    {"type": "email", "pattern": r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"},
    {"type": "address", "pattern": r"[東京都大阪府京都府北海道].{2,10}[市区町村郡].{1,20}[0-9０-９]"},
    {"type": "postal_code", "pattern": r"〒?\d{3}[-ー]\d{4}"},
]


def detect_pii(text: str) -> list[dict]:
    """Detect PII patterns in contract text. Returns list of {type, start, end, text}."""
    warnings = []
    for pattern_def in PII_PATTERNS:
        for match in re.finditer(pattern_def["pattern"], text):
            warnings.append({
                "type": pattern_def["type"],
                "start": match.start(),
                "end": match.end(),
                "text": match.group(),
            })
    return warnings
