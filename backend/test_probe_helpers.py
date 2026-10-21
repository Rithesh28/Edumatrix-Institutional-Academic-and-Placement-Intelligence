import re
import statistics
from typing import Dict, Any, List, Optional, Tuple

HEADER_SYNONYMS = {
    "usn": [
        "usn", "usn no", "usn no.", "usn_no", "roll no", "roll no.", "roll_no", "rollno",
        "reg no", "reg no.", "reg_no", "regno", "register no", "register number",
        "registration no", "registration number", "enrollment no", "enrollment number",
        "univ seat no", "university seat number", "seat no", "student id", "candidate id"
    ],
    "name": [
        "candidate name", "candidate_name", "student name", "student_name", "name",
        "full name", "full_name", "applicant name", "name of candidate", "name of student"
    ],
    "email": [
        "email", "email id", "email_id", "emailid", "e-mail", "e-mail id", "mail",
        "college email", "student email", "personal email", "email address"
    ],
    "status": [
        "status", "result", "selection status", "selection_status", "round result",
        "round status", "shortlist status", "interview status", "final status",
        "outcome", "decision", "final result", "round 1 result", "round 2 result"
    ],
    "branch": [
        "branch", "department", "dept", "stream", "course", "discipline"
    ],
    "remarks": [
        "remarks", "comments", "feedback", "notes", "reason", "extra info"
    ]
}

BANNER_PATTERNS = [
    r"campus\s+recruitment",
    r"recruitment\s+drive",
    r"shortlist(?:ed)?\s+candidates?",
    r"selection\s+list",
    r"final\s+results?",
    r"examination\s+duty",
    r"exam\s+duty",
    r"duty\s+chart",
    r"college\s+of\s+engineering",
    r"department\s+of\s+",
    r"training\s+(?:&|and)\s+placement",
    r"coordinator\s+signature",
    r"page\s+\d+\s+of\s+\d+",
    r"date\s*:\s*\d+",
    r"venue\s*:\s*",
    r"time\s*:\s*\d+",
]

USN_REGEX = re.compile(r"\b[0-9][a-zA-Z]{2}[0-9]{2}[a-zA-Z]{0,3}[0-9]{2,4}\b", re.IGNORECASE)
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", re.IGNORECASE)

def normalize_key(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "", str(text).lower().strip())

def is_banner_row(row_text: str) -> bool:
    t = row_text.lower().strip()
    for pat in BANNER_PATTERNS:
        if re.search(pat, t):
            return True
    return False

def check_header_row(row_tokens: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Tuple[int, int]]]:
    row_text = " ".join(t["text"] for t in row_tokens).lower()
    norm_row = normalize_key(row_text)

    detected_cols: Dict[str, Tuple[int, int]] = {}
    for canon_field, syns in HEADER_SYNONYMS.items():
        for syn in syns:
            norm_syn = normalize_key(syn)
            if norm_syn in norm_row:
                # Find matching tokens to get bounding box
                matched_tokens = [t for t in row_tokens if normalize_key(t["text"]) in norm_syn or norm_syn in normalize_key(t["text"])]
                if matched_tokens:
                    col_left = min(t["left"] for t in matched_tokens)
                    col_right = max(t["right"] for t in matched_tokens)
                    detected_cols[canon_field] = (col_left, col_right)
                    break
    
    # Must match at least 2 distinct canonical headers
    is_header = len(detected_cols) >= 2
    return is_header, detected_cols

print("Verification script written.")
