"""Draft names-file rows for watchlist symbols that `config/aliases.csv` does not list yet.

    python scripts/build_aliases.py            # append drafted rows for new watchlist symbols
    python scripts/build_aliases.py --dry-run  # print them, write nothing

Brian and Claude edit the names file by hand (Chinese names, short names, `weak` marks, driver
keywords), so this script never rewrites or removes a row: it only appends rows for symbols
that have none. Drafts are the watchlist name, a short name without "Holdings", "Inc." and so
on, and ticker forms ("0700.HK", "700 HK", "00700"). Read the drafts after a run: a short name
that is also an everyday word ("Apple") should become kind `weak`.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_advisor.news.link import ALIASES_PATH, draft_aliases, read_aliases  # noqa: E402
from stock_advisor.watchlist import load_watchlist  # noqa: E402

HEADER = (
    "# Names file for the news linker (stock_advisor/news/link.py explains each kind).\n"
    "# Columns: symbol (watchlist symbol, or a driver name from risk.DRIVERS), alias, kind.\n"
    "symbol,alias,kind\n"
)
SKIP_KINDS = ("driver", "fx")  # driver series link through driver keywords, not their tickers


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--path", type=Path, default=ALIASES_PATH)
    args = ap.parse_args(argv)

    known = {a.target for a in read_aliases(args.path)} if args.path.exists() else set()
    new = [
        a for item in load_watchlist(include_holdings=False)
        if item.kind not in SKIP_KINDS and item.symbol not in known
        for a in draft_aliases(item.symbol, item.name)
    ]
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    for a in new:
        writer.writerow([a.target, a.alias, a.kind])
    if args.dry_run:
        print(buf.getvalue(), end="")
    else:
        if not args.path.exists():
            args.path.write_text(HEADER, encoding="utf-8")
        with args.path.open("a", encoding="utf-8", newline="") as f:
            f.write(buf.getvalue())
    print(f"{len({a.target for a in new})} symbols, {len(new)} rows {'drafted' if args.dry_run else 'appended'}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
