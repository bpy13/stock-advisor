"""Link every stored news story to watchlist symbols and drivers (Task 5.2).

  python scripts/link_history.py [--db PATH] [--batch 2000] [--report-dir data/reports]

Resumable: a story with a link_state is skipped, so a rerun carries on where it stopped. Queue
it with jobq.ps1 in the cpu lane. A dropped story stays in `items`; nothing is deleted. The log
ends with counts (total, linked, dropped, linked per symbol for the top 20), and a report
`news-links-<date>.md` holds the counts and 30 random linked and 30 random dropped headlines
for a reading check. Writes `news.db` through the store only; the watcher and the backfill
task write it too (one writer at a time, the store waits up to 30 s).
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Optional, Sequence

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from stock_advisor.news.link import build_linker  # noqa: E402
from stock_advisor.news.store import NewsStore  # noqa: E402

logger = logging.getLogger("link_history")


def link_history(store: NewsStore, linker, batch: int = 2000) -> int:
    """Link every story that has no link_state yet. Returns how many were linked."""
    after, done = "", 0
    while True:
        items = store.items_to_link(after, batch)
        if not items:
            return done
        links = []
        for i in items:
            found = linker.link(i.title, i.summary, i.body)
            links.append((i.id, list(dict.fromkeys([*i.symbols, *found.symbols])),
                          list(found.drivers)))
        store.set_links(links)
        after = items[-1].id
        done += len(items)
        logger.info("linked %d stories so far", done)


def summary(store: NewsStore) -> dict:
    counts = store.link_counts()
    return {
        "total": sum(counts.values()),
        "linked": counts.get("linked", 0),
        "dropped": counts.get("dropped", 0),
        "unlinked": counts.get(None, 0),
        "per_symbol": store.linked_per_symbol(20),
    }


def write_report(store: NewsStore, stats: dict, out_dir: Path, today: Optional[date] = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"news-links-{(today or date.today()).isoformat()}.md"
    lines = [
        f"# News links, {(today or date.today()).isoformat()}", "",
        f"- Stories total: {stats['total']}",
        f"- Linked: {stats['linked']}",
        f"- Dropped: {stats['dropped']}",
        f"- Not linked yet: {stats['unlinked']}", "",
        "## Linked stories per symbol (top 20)", "",
    ]
    lines += [f"- {sym}: {n}" for sym, n in stats["per_symbol"]]
    for state in ("linked", "dropped"):
        lines += ["", f"## 30 random {state} headlines (reading check)", ""]
        lines += [f"- [{src}] {when[:10]} {title}" for src, when, title in store.sample_by_state(state, 30)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Link the stored news history.")
    parser.add_argument("--db", help="path of news.db (default: the repo's data/cache/news/news.db)")
    parser.add_argument("--batch", type=int, default=2000)
    parser.add_argument("--report-dir", default=str(_REPO_ROOT / "data" / "reports"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with NewsStore(args.db) as store:
        link_history(store, build_linker(), args.batch)
        stats = summary(store)
        report = write_report(store, stats, Path(args.report_dir))
    logger.info("stories total %d, linked %d, dropped %d, not linked %d",
                stats["total"], stats["linked"], stats["dropped"], stats["unlinked"])
    for sym, n in stats["per_symbol"]:
        logger.info("  %s: %d", sym, n)
    logger.info("report: %s", report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
