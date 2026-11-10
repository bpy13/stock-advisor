import pandas as pd
import pytest

from stock_advisor.price_sources import futu


class FakeCtx:
    """Stands in for futu.OpenQuoteContext; ``pages`` is a list of frames served in order."""

    def __init__(self, pages, remain=10):
        self.pages, self.remain, self.calls = pages, remain, []

    def get_history_kl_quota(self, get_detail=False):
        return 0, (1, self.remain, [])

    def request_history_kline(self, code, start, end, ktype, autype, max_count, page_req_key):
        self.calls.append((code, ktype, autype, page_req_key))
        i = 0 if page_req_key is None else int(page_req_key)
        nxt = str(i + 1) if i + 1 < len(self.pages) else None
        return 0, self.pages[i], nxt


def _frame(rows):
    return pd.DataFrame([dict(time_key=t, open=o, high=h, low=lo, close=c, volume=v)
                         for t, o, h, lo, c, v in rows])


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    monkeypatch.setattr(futu, "_eligible", lambda: {"0005.HK", "AAPL"})
    monkeypatch.setattr(futu, "_limiter", futu._RateLimiter())
    monkeypatch.setitem(futu._state, "ctx", None)
    futu._state["seen"].clear()


def _use(monkeypatch, ctx):
    monkeypatch.setattr(futu, "_context", lambda: ctx)
    return ctx


def test_symbol_mapping():
    assert futu.to_futu_code("0005.HK") == "HK.00005"
    assert futu.to_futu_code("2800.HK") == "HK.02800"
    assert futu.to_futu_code("9988.HK") == "HK.09988"
    with pytest.raises(ValueError):
        futu.to_futu_code("AAPL")


def test_daily_raw_adjusted_and_paging(monkeypatch):
    p1 = _frame([("2025-03-03 00:00:00", 10, 11, 9, 10.5, 100)])
    p2 = _frame([("2025-03-04 00:00:00", 10.5, 12, 10, 11, 200)])
    ctx = _use(monkeypatch, FakeCtx([p1, p2]))
    raw, adj = futu.fetch("0005.HK", "1d")
    assert [c[2] for c in ctx.calls] == ["None", "None", "qfq", "qfq"]
    assert {c[0] for c in ctx.calls} == {"HK.00005"} and ctx.calls[1][3] == "1"
    assert list(raw.index.strftime("%Y-%m-%d")) == ["2025-03-03", "2025-03-04"]
    assert list(raw["close"]) == [10.5, 11] and list(adj["volume"]) == [100, 200]


def test_hourly_end_label_to_utc_start(monkeypatch):
    # Hong Kong labels (bar end): 10:30 -> 09:30 bar, 12:00 -> 11:30 bar (lunch cut), 14:00 -> 13:00 bar.
    rows = [("2025-03-03 10:30:00", 1, 2, 1, 2, 10), ("2025-03-03 12:00:00", 2, 3, 2, 3, 20),
            ("2025-03-03 14:00:00", 3, 4, 3, 4, 30), ("2025-03-03 10:45:00", 9, 9, 9, 9, 1)]
    _use(monkeypatch, FakeCtx([_frame(rows)]))
    raw, adj = futu.fetch("0005.HK", "60m")
    assert adj is None
    hk = [t.tz_convert("Asia/Hong_Kong").strftime("%H:%M") for t in raw.index]
    assert hk == ["09:30", "11:30", "13:00"]
    assert str(raw.index.tz) == "UTC" and list(raw["volume"]) == [10, 20, 30]


def test_rate_limit_waits_when_window_full():
    now, slept = [0.0], []
    lim = futu._RateLimiter(clock=lambda: now[0], sleep=lambda s: (slept.append(s), now.__setitem__(0, now[0] + s)))
    for _ in range(futu.MAX_REQUESTS):
        lim.wait()
    assert slept == []
    now[0] = 10.0
    lim.wait()
    assert slept == [pytest.approx(20.0)]


def test_quota_stop_names_the_problem(monkeypatch):
    _use(monkeypatch, FakeCtx([_frame([])], remain=0))
    with pytest.raises(futu.QuotaExhausted, match="quota"):
        futu.fetch("0005.HK", "1d")


def test_closed_port_gives_clear_error(monkeypatch):
    monkeypatch.setattr(futu, "_port_open", lambda: False)
    with pytest.raises(futu.FutuNotRunning, match="Futu OpenD is not running"):
        futu.fetch("0005.HK", "1d")


def test_non_hk_symbol_is_skipped(monkeypatch):
    ctx = _use(monkeypatch, FakeCtx([]))
    raw, adj = futu.fetch("AAPL", "1d")
    assert raw.empty and adj is None and ctx.calls == []
