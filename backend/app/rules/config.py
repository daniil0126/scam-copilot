# backend/app/rules/config.py
from pydantic import BaseModel

class RulesConfig(BaseModel):
    version: str = "rules-0.1"

    # --- правило A: Unusual Amount ---
    amount_min_history: int = 3
    amount_ratio_medium: float = 2.5
    amount_ratio_high: float = 5.0
    amount_ratio_critical: float = 10.0

    # --- правило B: Duplicate ---
    duplicate_date_window_days: int = 3
    duplicate_amount_tolerance_pct: float = 0.01

    # --- правило C: Vendor Impersonation ---
    vendor_domain_distance_max: int = 2

    # --- правило D: Suspicious Link ---
    link_max_subdomain_depth: int = 2

    # --- правило E: Unusual Sender Activity ---
    activity_window_days: int = 7
    activity_burst_multiplier: float = 3.0

    # --- агрегация (05) ---
    level_low_max: int = 29
    level_medium_max: int = 59
    level_high_max: int = 79

    family_weights: dict[str, int] = {
        "amount": 25,
        "duplicates": 30,
        "vendor_identity": 30,
        "links": 20,
        "activity": 15,
        "textual": 10,
    }
    family_decay: float = 0.5

    # --- confidence ---
    confidence_history_full_min: int = 10

    # --- 06: связи между отправителями ---
    relationship_min_independent_matches: int = 2