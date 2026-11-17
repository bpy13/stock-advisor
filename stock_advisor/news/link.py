"""Link a news story to the watchlist symbols and the six drivers it concerns.

The names file `config/aliases.csv` (columns `symbol,alias,kind`) lists what to look for. The
`symbol` column holds a watchlist symbol, or a driver name from `risk.DRIVERS` ("oil", ...).
Kinds decide how an alias matches:

- `name`, `short`, `driver`: any case, whole words only ("Tencent", "crude oil").
- `weak`: exact case, and only when the story also confirms it: another alias of the same
  symbol or driver matched, or a cue word such as "shares" or "rates" appears. "Apple" alone
  could be the fruit; "Apple shares fall" is the company.
- `ticker`: exact case. A ticker of one or two letters, or one written with "$" in the file
  ("$LOW"), links only as "$LOW" or after an exchange ("NYSE: LOW"). A numeric Hong Kong code
  ("00700") links only after an exchange ("HKEX: 00700") or, with 5 digits, in brackets.
- `zh`, `hans`: Chinese text, matched anywhere (Chinese has no spaces). `zh` is Traditional
  Chinese as used in Hong Kong; `hans` marks a Simplified second row.

An alias that is part of a longer alias of another target gives way ("BYD" inside "BYD
Electronic"). An alias followed by a building word ("HSBC Building", "中銀大廈") is an address,
not news about the company. Holdings that the names file lacks join at run time with drafted
ticker aliases; nothing about the holdings is written to a tracked file.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union

from stock_advisor.risk import DRIVERS

ALIASES_PATH = Path(__file__).resolve().parents[2] / "config" / "aliases.csv"
KINDS = ("name", "short", "weak", "ticker", "zh", "hans", "driver")

_EXCHANGES = r"(?:NYSE\s+American|NYSE\s+Arca|NYSEARCA|NYSE|NASDAQ|Nasdaq|HKEX|HKEx|SEHK|HKG|HK)"
_PREFIX = _EXCHANGES + r"\s*[:：]\s*"
_CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
# Word edges use ASCII letters and digits only: Python's \w also matches Chinese characters,
# which would hide "0700.HK" or "\u80a1\u50f9" when they touch Chinese text.
_W0, _W1 = r"(?<![A-Za-z0-9_$])", r"(?![A-Za-z0-9_])"
# A building or street word right after a name (one capitalised word may sit between).
_ADDRESS_EN = re.compile(
    r"\s+(?:[A-Z][\w'&]*\s+)?(?:Building|Tower|Centre|Center|Plaza|Road|Street|Avenue|House"
    r"|Square|Arena|Stadium)\b"
)
_ADDRESS_ZH = re.compile(r"[^\s，。、：:]{0,4}?(?:大廈|大樓|廣場)")
# "olive oil prices" or "palm oil futures" are not crude oil.
_NOT_CRUDE = re.compile(
    r"(?:palm|olive|vegetable|cooking|edible|essential|fish|coconut|sunflower|soybean|soy|rapeseed)\s+$", re.I
)
# "銀行業" is "the banking industry", not "中國銀行" the bank.
_INDUSTRY_ZH = "業"

# Cue words that confirm a `weak` alias. Symbols share one list; each driver has its own.
_COMPANY_CUES = (
    r"shares?|stocks?|earnings|revenue|profits?|quarter(?:ly)?|CEO|chief executive|investors?"
    r"|analysts?|results|sales|buyback|dividends?|guidance|upgrades?|downgrades?|valuation"
    r"|market value|IPO|acquisition|takeover|Inc\.?|Corp\.?|Nasdaq|NYSE|"
    r"股價|股份|股東|業績|盈利|收入|季度|市值|派息|回購|評級|收購"
)
_DRIVER_CUES = {
    "oil": r"barrels?|crude|OPEC|output|supply|demand|prices?|油價|原油",
    "us_rates": r"rates?|inflation|policy|yields?|hikes?|cuts?|minutes|chair|FOMC|Treasur(?:y|ies)|議息|加息|減息|利率",
    "china_hk_tech": r"stocks?|shares?|index|tech|科技",
    "us_tech": r"stocks?|shares?|index|tech|科技",
    "cyber_security": r"attacks?|breach|hack(?:ers?|ing)?|security|攻擊|黑客",
    "usd_cny": r"dollar|exchange rate|currency|PBOC|PBoC|central bank|fixing|depreciat\w*|devaluat\w*"
    r"|weak(?:er|ens?)|strong(?:er|ens?)|美元|匯率|貶值|升值",
}


@dataclass(frozen=True)
class Alias:
    target: str  # watchlist symbol or driver name
    alias: str
    kind: str


@dataclass(frozen=True)
class LinkResult:
    """What a story is about: symbols and drivers (sorted), and each (target, matched text)."""

    symbols: List[str]
    drivers: List[str]
    matches: List[Tuple[str, str]]

    @property
    def linked(self) -> bool:
        return bool(self.symbols or self.drivers)


def read_aliases(path: Union[str, Path] = ALIASES_PATH) -> List[Alias]:
    """Read and check the names file. Lines starting with '#' are comments."""
    path = Path(path)
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]
    rows = list(csv.reader(lines))
    if not rows or [c.strip() for c in rows[0]] != ["symbol", "alias", "kind"]:
        raise ValueError(f"{path.name}: header must be symbol,alias,kind")
    out: List[Alias] = []
    for n, row in enumerate(rows[1:], start=2):
        if len(row) != 3:
            raise ValueError(f"{path.name} row {n}: expected 3 columns, got {len(row)}: {row}")
        target, alias, kind = (c.strip() for c in row)
        if not target or not alias:
            raise ValueError(f"{path.name} row {n}: empty symbol or alias")
        if kind not in KINDS:
            raise ValueError(f"{path.name} row {n}: unknown kind {kind!r}")
        out.append(Alias(target, alias, kind))
    return out


def _short_name(name: str) -> str:
    """'HSBC Holdings plc' -> 'HSBC'; 'Walt Disney Company (The)' -> 'Walt Disney'."""
    suffixes = r"(?:\(\w+\)|plc|Inc\.?|Corp\.?|Corporation|Company|Co\.?|Limited|Ltd\.?|Holdings|Group|&|and)"
    short = name
    while True:
        cut = re.sub(rf"[\s,]+{suffixes}$", "", short).strip()
        if cut == short:
            return short
        short = cut


def draft_aliases(symbol: str, name: str = "") -> List[Alias]:
    """Drafted aliases for one watchlist row: its name, short name and ticker forms."""
    rows: List[Alias] = []
    if name and name != symbol:
        full = re.sub(r"^(.*) \(The\)$", r"The \1", name)
        rows.append(Alias(symbol, full, "name"))
        short = _short_name(name)
        if short not in (full, name, symbol) and len(short) > 2:
            rows.append(Alias(symbol, short, "short"))
    hk = re.fullmatch(r"(\d{4,5})\.HK", symbol)
    if hk:
        code4 = hk.group(1)[-4:].rjust(4, "0")
        bare = code4.lstrip("0") or "0"
        forms = [f"{code4}.HK", f"{bare}.HK", f"{code4} HK", code4.rjust(5, "0"), code4]
        if len(bare) >= 3:  # "5 HK" is too often "top 5 HK stocks"
            forms.insert(3, f"{bare} HK")
    elif symbol.startswith("^") or "=" in symbol:
        forms = []
    else:
        forms = [symbol] + ([symbol.replace("-", "."), "$" + symbol.replace("-", ".")] if "-" in symbol else [])
    seen = set()
    for f in forms:
        if f not in seen:
            seen.add(f)
            rows.append(Alias(symbol, f, "ticker"))
    return rows


def _alt(aliases: Iterable[str], fold: bool = False) -> str:
    """One regex for many aliases, as a prefix tree: a flat list of 1,000 alternatives is
    tried one by one at every word (about 10 ms a story); the tree shares common starts.
    The longer branch is tried first, so the longest alias wins at a position. A space in an
    alias matches any run of spaces. `fold` lowercases the keys for a case-blind pattern."""
    trie: dict = {}
    for a in set(aliases):
        node = trie
        for ch in (a.lower() if fold else a):
            node = node.setdefault(ch, {})
        node[""] = {}  # end of an alias

    def emit(node: dict) -> str:
        branches = [(r"\s+" if ch == " " else re.escape(ch)) + emit(child)
                    for ch, child in sorted(node.items()) if ch]
        if not branches:
            return ""
        body = branches[0] if len(branches) == 1 else "(?:" + "|".join(branches) + ")"
        if "" in node:  # an alias may end here; try the longer ones first (greedy "?")
            return f"(?:{body})?" if len(branches) == 1 else body + "?"
        return body

    return emit(trie)


class Linker:
    """Compiled matcher over the names file. Build once, call `link` per story."""

    def __init__(self, aliases: Iterable[Alias]):
        self.aliases = list(aliases)
        self._by_text: Dict[Tuple[str, str], List[Alias]] = {}  # (mode, normalised text)
        groups: Dict[str, List[str]] = {"ci": [], "cs": [], "zh": [], "strict": [], "bracket": []}
        for a in self.aliases:
            for mode, text in self._modes(a):
                groups[mode].append(text)
                self._by_text.setdefault((mode, self._norm(mode, text)), []).append(a)
        w0, w1 = _W0, _W1
        self._patterns: Dict[str, Optional[re.Pattern]] = {
            "ci": re.compile(rf"{w0}(?:{_alt(groups['ci'], fold=True)}){w1}", re.I) if groups["ci"] else None,
            "cs": re.compile(rf"{w0}(?:{_alt(groups['cs'])}){w1}") if groups["cs"] else None,
            "zh": re.compile(rf"(?:{_alt(groups['zh'])})(?!{_INDUSTRY_ZH})") if groups["zh"] else None,
            # Strict tickers: the ticker is group 1, after "$" or an exchange prefix.
            "strict": re.compile(rf"(?=[$NHS])(?:\$|(?<![A-Za-z0-9_])(?:{_PREFIX}))({_alt(groups['strict'])}){w1}")
            if groups["strict"] else None,
            "bracket": re.compile(rf"[(（\[]\s*({_alt(groups['bracket'])})\s*[)）\]]") if groups["bracket"] else None,
        }
        self._prefix = re.compile(rf"(?<![A-Za-z0-9_]){_PREFIX}(?=[\d$A-Z])")
        self._company_cue = re.compile(rf"{_W0}(?:{_COMPANY_CUES}){_W1}", re.I)
        self._driver_cue = {d: re.compile(rf"{_W0}(?:{c}){_W1}", re.I) for d, c in _DRIVER_CUES.items()}

    @staticmethod
    def _norm(mode: str, text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        return text.lower() if mode == "ci" else text

    @staticmethod
    def _modes(a: Alias) -> List[Tuple[str, str]]:
        """The matchers an alias joins, with the text each one looks for."""
        if _CJK.search(a.alias):
            return [("zh", a.alias)]
        if a.kind == "ticker":
            # Every ticker links after "$" or an exchange prefix.
            base = a.alias.lstrip("$")
            modes = [("strict", base)]
            if base.isdigit():
                if len(base) == 5:  # "騰訊(00700)"; 4 digits in brackets are too often a year
                    modes.append(("bracket", base))
            elif not a.alias.startswith("$") and len(base) > 2:
                modes.append(("cs", base))  # bare, exact case
            return modes
        if a.kind == "weak":
            return [("cs", a.alias)]
        return [("ci", a.alias)]

    def link(self, title: str, summary: str = "", body: Optional[str] = None) -> LinkResult:
        text = "\n".join(t for t in (title, summary, body) if t)
        text = text.replace("\u2019", "'").replace("\u00a0", " ")
        prefix_spans = [m.span() for m in self._prefix.finditer(text)]
        hits: List[Tuple[int, int, Alias, str]] = []  # start, end, alias, matched text
        for mode, pat in self._patterns.items():
            if pat is None:
                continue
            for m in pat.finditer(text):
                grp = 1 if mode in ("strict", "bracket") else 0
                start, end = m.span(grp)
                matched = m.group(grp)
                if mode in ("ci", "cs", "zh") and any(s <= start < e for s, e in prefix_spans):
                    continue  # "HKEX" or "Nasdaq" in "HKEX: 0700" is an exchange, not news
                if self._is_address(text, end, mode):
                    continue
                key = (mode, self._norm(mode, matched))
                for a in self._by_text.get(key, []):
                    if a.target == "oil" and _NOT_CRUDE.search(text[max(0, start - 20):start]):
                        continue
                    hits.append((start, end, a, matched))
        # An alias inside a longer alias of another target gives way.
        kept = [
            h for h in hits
            if not any(o[0] <= h[0] and h[1] <= o[1] and (o[1] - o[0]) > (h[1] - h[0])
                       and o[2].target != h[2].target for o in hits)
        ]
        strong = {h[2].target for h in kept if h[2].kind != "weak"}
        result: List[Tuple[str, str]] = []
        for start, end, a, matched in sorted(kept, key=lambda h: h[0]):
            if a.kind == "weak" and a.target not in strong and not self._cued(a.target, text):
                continue
            if (a.target, matched) not in result:
                result.append((a.target, matched))
        targets = {t for t, _ in result}
        return LinkResult(
            symbols=sorted(t for t in targets if t not in DRIVERS),
            drivers=sorted(t for t in targets if t in DRIVERS),
            matches=result,
        )

    @staticmethod
    def _is_address(text: str, end: int, mode: str) -> bool:
        rest = text[end:end + 40]
        if mode == "zh":
            return bool(_ADDRESS_ZH.match(rest))
        return bool(_ADDRESS_EN.match(rest))

    def _cued(self, target: str, text: str) -> bool:
        pat = self._driver_cue.get(target, self._company_cue)
        return bool(pat.search(text))


def build_linker(
    path: Union[str, Path] = ALIASES_PATH, include_holdings: bool = True,
    watchlist_path: Optional[Union[str, Path]] = None,
) -> Linker:
    """The names file, plus drafted ticker aliases for holdings that the file lacks."""
    aliases = read_aliases(path)
    if include_holdings:
        from stock_advisor.watchlist import load_watchlist

        known = {a.target for a in aliases}
        for item in load_watchlist(include_holdings=True, path=watchlist_path):
            if item.kind == "holding" and item.symbol not in known:
                aliases.extend(draft_aliases(item.symbol))
    return Linker(aliases)


@lru_cache(maxsize=1)
def _default_linker() -> Linker:
    return build_linker()


def link(title: str, summary: str = "", body: Optional[str] = None) -> LinkResult:
    """Link one story with the default names file and the current holdings."""
    return _default_linker().link(title, summary, body)
