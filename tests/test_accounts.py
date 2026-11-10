import json

import pytest

from stock_advisor import accounts
from stock_advisor.accounts import load_accounts


def _write(tmp_path, **overrides):
    data = {
        "accounts": [{"name": "a", "broker": "futu", "cash": {"HKD": 5, "USD": 2}, "trade_file": None}],
        "limits": {"max_position_weight": 0.25, "min_trade_hkd": 10000, "whole_board_lots": True},
    }
    data.update(overrides)
    p = tmp_path / "accounts.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_loads_valid_file(tmp_path):
    accts, limits = load_accounts(_write(tmp_path))
    assert accts[0].broker == "futu" and accts[0].cash == {"HKD": 5.0, "USD": 2.0}
    assert accts[0].trade_file is None
    assert limits.max_position_weight == 0.25 and limits.whole_board_lots is True


def test_sample_file_loads(monkeypatch, tmp_path):
    monkeypatch.setattr(accounts, "REAL_PATH", tmp_path / "missing.json")
    accts, limits = load_accounts()
    assert accts and limits.min_trade_hkd == 10000


def test_unknown_broker(tmp_path):
    p = _write(tmp_path, accounts=[{"name": "a", "broker": "nope", "cash": {}}])
    with pytest.raises(ValueError, match=r"accounts\[0\]\.broker"):
        load_accounts(p)


def test_negative_cash(tmp_path):
    p = _write(tmp_path, accounts=[{"name": "a", "broker": "futu", "cash": {"HKD": -1}}])
    with pytest.raises(ValueError, match=r"cash\.HKD"):
        load_accounts(p)


def test_unknown_currency(tmp_path):
    p = _write(tmp_path, accounts=[{"name": "a", "broker": "futu", "cash": {"EUR": 1}}])
    with pytest.raises(ValueError, match="currency"):
        load_accounts(p)


@pytest.mark.parametrize("w", [-0.1, 1.5, "x"])
def test_weight_out_of_range(tmp_path, w):
    p = _write(tmp_path, limits={"max_position_weight": w, "min_trade_hkd": 1, "whole_board_lots": True})
    with pytest.raises(ValueError, match="max_position_weight"):
        load_accounts(p)
