"""
Core Date & Time Utilities for EduMatrix
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional

# Default Institutional Timezone (Indian Standard Time)
IST = ZoneInfo("Asia/Kolkata")


def normalize_to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Normalize datetime to timezone-aware UTC.
    If the datetime is naive (no tzinfo), it is interpreted as Asia/Kolkata.
    Explicit timezone offsets are preserved and accurately converted to UTC.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt.astimezone(timezone.utc)
