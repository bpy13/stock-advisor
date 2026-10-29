"""Task 6.2i: rebuild the reaction table and rerun the news backtest, under the memory guard.

Runs headless (started detached); logs to data/cache/news/model/rebuild_log.txt. A guard stop
exits with code 86. Nothing is resumable mid-run: the reaction files are replaced only at the
end, so a stopped run is simply started again.

    python scripts/run_rebuild_backtest.py
"""

import logging
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from stock_advisor import memory_guard  # noqa: E402
from stock_advisor.news_backtest_cli import MODEL_CACHE_DIR, main  # noqa: E402

LIMIT_GB = 16.0

if __name__ == "__main__":
    log_path = MODEL_CACHE_DIR / "rebuild_log.txt"
    logging.basicConfig(level=logging.INFO, filename=log_path,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.stdout = sys.stderr = open(log_path, "a", encoding="utf-8", buffering=1)
    memory_guard.start_memory_guard("rebuild backtest", LIMIT_GB)
    started = time.monotonic()
    print(time.strftime("start %Y-%m-%d %H:%M:%S"))
    code = main(["--rebuild-reactions"])
    print(time.strftime("end %Y-%m-%d %H:%M:%S"),
          f"total {(time.monotonic() - started) / 60:.1f} min, exit {code}")
    sys.exit(code)
