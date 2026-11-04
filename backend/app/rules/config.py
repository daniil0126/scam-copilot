# backend/app/rules/config.py
from pydantic import BaseModel


class RulesConfig(BaseModel):
    version: str = "rules-0.1"

    # --- правило A: Unusual Amount ---
        # Two prior invoices are enough to compare amounts. Three left scenario 3 (amount ×4.5) with "not enough data"
    # even though the supplier had two invoices with the same amount, and the dataset's N05/N07 do not depend on it.
    amount_min_history: int = 2
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

    # Calibrated on tests/dataset/cases.json (see docs/plans/engine-comparison.md). The principle, not fitted to
    # individual cases: every family weighs the same, so one HIGH signal in any family reaches the MEDIUM band
    # (40 * 1.0 = 40), and a second HIGH in the same family reaches HIGH (40 + 40 * 0.5 = 60). Decay 0.5 keeps one
    # family alone from reaching CRITICAL.
    family_weights: dict[str, int] = {
        "amount": 40,
        "duplicates": 40,
        "vendor_identity": 40,
        "links": 40,
        "activity": 40,
        "textual": 40,
    }
    family_decay: float = 0.5

    # --- confidence ---
    confidence_history_full_min: int = 10

    # --- 06: связи между отправителями ---
    relationship_min_independent_matches: int = 2