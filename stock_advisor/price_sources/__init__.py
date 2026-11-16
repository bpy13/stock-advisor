"""Price sources. Each module has ``fetch(symbol, interval, start, end) -> (raw, adjusted)``.

A source that serves one market only also has ``MARKET`` and ``ELIGIBLE_KINDS``; the refresh
skips other symbols without asking it.
"""
from __future__ import annotations

from stock_advisor.price_sources import alpaca, futu, yahoo

SOURCES = {"yahoo": yahoo, "alpaca": alpaca, "futu": futu}
