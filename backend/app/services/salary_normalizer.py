"""
Salary and CTC Normalization Service for EduMatrix Placement Intelligence.

Normalizes freeform CTC/salary inputs into standardized LPA representations,
enforces explicit currency and unit conventions, and extracts structured
numeric bounds (min_ctc_lpa, max_ctc_lpa) for analytics and filtering.
"""

import re
from typing import Optional, Tuple


def normalize_salary_range(val: Optional[str]) -> Optional[str]:
    """
    Validate and normalize salary/CTC strings to standardized LPA format.
    
    Conventions:
    - Target unit: LPA (Lakhs Per Annum in INR).
    - Ranges: '6-8 LPA', '6 to 8 LPA' -> '6.0 - 8.0 LPA'
    - Single LPA: '12 LPA', '12.5 LPA' -> '12.0 LPA', '12.5 LPA'
    - Raw numeric INR >= 10,000: '1200000', '12,00,000' -> '12.0 LPA' (divided by 100,000)
    - Single numeric < 100: '12', '8.5' -> '12.0 LPA', '8.5 LPA'
    - Rejects foreign currency (e.g. '$90k', '€50k') as ambiguous currency.
    - Rejects arbitrary non-numeric text (e.g. 'Best in industry', 'Negotiable').
    """
    if val is None:
        return None
    val_clean = str(val).strip()
    if not val_clean:
        return None
    
    # Check for ambiguous foreign currencies
    foreign_currencies = ['$', '€', '£', 'USD', 'EUR', 'GBP', 'AUD', 'CAD']
    if any(c in val_clean for c in foreign_currencies):
        raise ValueError(
            f"Ambiguous currency in salary '{val_clean}'. "
            "EduMatrix requires compensation in INR / LPA (e.g. '12.0 LPA')."
        )
    
    # Strip common INR prefixes and symbols
    s = val_clean.replace('₹', '').replace('Rs.', '').replace('Rs', '').replace('INR', '').strip()
    
    # Check for range: e.g. 6-8 LPA, 6 - 8 LPA, 6 to 8 LPA, 600000 - 800000
    range_match = re.match(
        r'^([\d\.]+)\s*(?:-|to)\s*([\d\.]+)\s*(?:LPA|lpa|Lacs|Lakhs)?$',
        s,
        re.IGNORECASE
    )
    if range_match:
        try:
            low = float(range_match.group(1))
            high = float(range_match.group(2))
        except ValueError:
            raise ValueError(f"Invalid numeric values in salary range '{val_clean}'.")
        
        # If numbers are raw INR amounts (e.g. 600000 - 800000)
        if low >= 10000:
            low = round(low / 100000.0, 2)
        if high >= 10000:
            high = round(high / 100000.0, 2)
        
        if low > high:
            raise ValueError(f"Invalid salary range: minimum ({low} LPA) exceeds maximum ({high} LPA).")
        
        return f"{low} - {high} LPA"
    
    # Single LPA: e.g. 12 LPA, 12.5 LPA, 12LPA
    single_lpa_match = re.match(r'^([\d\.]+)\s*(?:LPA|lpa|Lacs|Lakhs)$', s, re.IGNORECASE)
    if single_lpa_match:
        try:
            num = float(single_lpa_match.group(1))
            return f"{num} LPA"
        except ValueError:
            raise ValueError(f"Invalid numeric value in salary '{val_clean}'.")
    
    # Raw numeric amount: e.g. 1200000, 12,00,000, 12, 8.5
    s_digits = s.replace(',', '').strip()
    if re.match(r'^[\d\.]+$', s_digits):
        try:
            num = float(s_digits)
            if num >= 10000:  # Annual INR figure
                lpa = round(num / 100000.0, 2)
                return f"{lpa} LPA"
            elif num > 0:  # Numeric LPA figure
                return f"{num} LPA"
        except ValueError:
            pass
    
    # Unparseable / arbitrary text
    raise ValueError(
        f"Invalid salary/CTC format '{val_clean}'. "
        "Expected salary in LPA (e.g. '12 LPA', '6 - 8 LPA') or annual INR value."
    )


def extract_ctc_lpa_bounds(val: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract structured numeric minimum and maximum CTC bounds (in LPA)
    from a normalized or raw salary string.
    
    Returns:
        (min_ctc_lpa, max_ctc_lpa)
    """
    if not val:
        return None, None
    
    try:
        norm = normalize_salary_range(val)
    except Exception:
        return None, None
    
    if not norm:
        return None, None
    
    # Check for range: '6.0 - 8.0 LPA'
    range_match = re.match(r'^([\d\.]+)\s*-\s*([\d\.]+)\s*LPA$', norm, re.IGNORECASE)
    if range_match:
        return float(range_match.group(1)), float(range_match.group(2))
    
    # Check for single: '12.0 LPA'
    single_match = re.match(r'^([\d\.]+)\s*LPA$', norm, re.IGNORECASE)
    if single_match:
        val_float = float(single_match.group(1))
        return val_float, val_float
    
    return None, None
