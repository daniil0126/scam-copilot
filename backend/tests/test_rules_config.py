from app.rules.config import RulesConfig


def test_config_defaults_valid():
    cfg = RulesConfig()
    assert cfg.version
    assert cfg.amount_min_history >= 1


def test_levels_strictly_increasing():
    cfg = RulesConfig()
    assert cfg.level_low_max < cfg.level_medium_max < cfg.level_high_max


def test_amount_ratio_thresholds_ordered():
    cfg = RulesConfig()
    assert cfg.amount_ratio_medium < cfg.amount_ratio_high < cfg.amount_ratio_critical


def test_family_weights_positive():
    cfg = RulesConfig()
    assert all(w > 0 for w in cfg.family_weights.values())


def test_family_decay_in_0_1():
    cfg = RulesConfig()
    assert 0.0 < cfg.family_decay < 1.0