"""Price sources. Each module has ``fetch(symbol, interval, start, end) -> (raw, adjusted)``.

Tasks 2.3 and 2.4 each add one line to ``SOURCES``.
"""
from __future__ import annotations

from stock_advisor.price_sources import yahoo

SOURCES = {"yahoo": yahoo}
