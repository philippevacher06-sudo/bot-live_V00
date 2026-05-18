#!/usr/bin/env python3
"""
V24.3.2 - ENTRY QUALITY REPORT

Autonomous log reader for Bot Pivot observation logs.

It does not import bot modules, does not call the broker API, and does not
modify engine state. It only reads a log file and prints a per-symbol report
focused on LIMIT entry quality.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import re
import sys
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, TextIO


DEFAULT_LOG_GLOB = "logs/BOT_PIVOT_07D_24_7_DEMO_*.log"

KNOWN_SYMBOLS = {
    "DE40",
    "US100",
    "BTCUSD",
    "ETHUSD",
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "EURJPY",
    "AUDUSD",
    "NZDUSD",
    "USDCAD",
    "USDCHF",
    "GBPJPY",
    "EURGBP",
    "XAUUSD",
    "XAGUSD",
}

TOKEN_BLOCKLIST = {
    "ACTIVE",
    "AGE",
    "API",
    "BASKET",
    "BB",
    "BLOCKED",
    "BOLLINGER",
    "BROKER",
    "BUY",
    "CANCEL",
    "CHECK",
    "COUNT",
    "EMPTY",
    "ENTRY",
    "ERROR",
    "EXEC",
    "EXECUTION",
    "FALSE",
    "FILL",
    "GET",
    "HIGH",
    "HTTP",
    "INTERNAL",
    "LADDER",
    "LIMIT",
    "LOCAL",
    "LOG",
    "LOW",
    "MARKETABLE",
    "MID",
    "NEW",
    "OK",
    "OPEN",
    "ORDER",
    "PEND",
    "PENDING",
    "POS",
    "POSITION",
    "PRICE",
    "RATE",
    "REJECT",
    "RESET",
    "SELL",
    "SIGNAL",
    "SMALL",
    "STATE",
    "TARGET",
    "TOO",
    "TP",
    "TRUE",
    "UPL",
    "WIDTH",
    "WORKINGORDERS",
}

EVENT_MARKERS = (
    "BASKET_TP_LADDER_CHECK",
    "BOLLINGER_WIDTH_OBSERVE",
    "BOLLINGER_ENTRY_OBSERVE",
    "BROKER_EMPTY_RESET",
    "REFRESH_06C_RATE_LIMIT",
    "BASKET_REJECT_BOLLINGER_TOO_FAR",
    "BASKET_REJECT_MARKETABLE_LIMIT",
    "BOLLINGER_WIDTH_TOO_SMALL",
    "BASKET_PENDING_CANCEL",
    "BASKET_TP_BLOCKED",
    "BASKET_TP_OK",
    "BASKET_REJECT",
    "BASKET_FILL",
    "BASKET_NEW",
    "LIMIT_OK",
)

KEY_VALUE_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)=([^\s|,;]+)")
TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9._-]{1,15}\b")


@dataclass
class LastSeen:
    line_no: int = 0
    text: str = ""
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class SymbolStats:
    counts: Counter = field(default_factory=Counter)
    reject_reasons: Counter = field(default_factory=Counter)
    cancel_ages: list[float] = field(default_factory=list)
    entry_dists: list[float] = field(default_factory=list)
    entry_ratios: list[float] = field(default_factory=list)
    width_ratios: list[float] = field(default_factory=list)
    width_ok: int = 0
    width_false: int = 0
    last_entry: LastSeen = field(default_factory=LastSeen)
    last_cancel: LastSeen = field(default_factory=LastSeen)
    last_width: LastSeen = field(default_factory=LastSeen)
    last_tp_ladder: LastSeen = field(default_factory=LastSeen)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build V24.3.2 ENTRY QUALITY REPORT from Bot Pivot logs."
    )
    parser.add_argument(
        "log",
        nargs="?",
        default=None,
        help=(
            "Log file to scan. Use '-' for stdin. If omitted, the newest "
            f"{DEFAULT_LOG_GLOB} file is used from the current directory."
        ),
    )
    parser.add_argument(
        "--last-lines",
        type=int,
        default=0,
        help="Only scan the last N lines of the log.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json", "csv"),
        default="markdown",
        help="Output format.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional output path. Without this, the report is printed to stdout.",
    )
    return parser.parse_args(argv)


def newest_log(pattern: str = DEFAULT_LOG_GLOB) -> Path:
    matches = [Path(p) for p in glob.glob(pattern)]
    if not matches:
        raise FileNotFoundError(f"No log found for pattern: {pattern}")
    return max(matches, key=lambda p: p.stat().st_mtime)


def normalize_key(key: str) -> str:
    return key.strip().lower()


def parse_fields(line: str) -> dict[str, str]:
    return {normalize_key(k): v.strip() for k, v in KEY_VALUE_RE.findall(line)}


def parse_float(value: object | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip().strip("[]()")
    text = text.rstrip(",;|")
    for suffix in ("ms", "pts", "pips", "sec", "s", "%"):
        if text.lower().endswith(suffix):
            text = text[: -len(suffix)]
            break
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def parse_bool(value: object | None) -> bool | None:
    if value is None:
        return None
    text = str(value).strip().lower().rstrip(",;|")
    if text in {"1", "true", "yes", "y", "ok"}:
        return True
    if text in {"0", "false", "no", "n", "ko"}:
        return False
    return None


def scan_tokens(text: str) -> list[str]:
    tokens = []
    for token in TOKEN_RE.findall(text):
        token = token.strip().strip(".,:;|[]()")
        if not token or "_" in token or token in TOKEN_BLOCKLIST:
            continue
        if token.startswith("BOT") or token.startswith("HTTP"):
            continue
        if token in KNOWN_SYMBOLS:
            tokens.append(token)
            continue
        looks_like_fx = len(token) == 6 and token[:3].isalpha() and token[3:].isalpha()
        has_digit = any(ch.isdigit() for ch in token)
        if looks_like_fx or has_digit:
            tokens.append(token)
    return tokens


def find_symbol(line: str, marker: str | None = None) -> str:
    for symbol in sorted(KNOWN_SYMBOLS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(symbol)}\b", line):
            return symbol

    if marker and "|" in line:
        parts = [part.strip() for part in line.split("|")]
        for idx, part in enumerate(parts):
            if marker in part:
                nearby = " ".join(parts[max(0, idx - 2) : idx + 3])
                tokens = scan_tokens(nearby)
                if tokens:
                    return tokens[0]

    tokens = scan_tokens(line)
    if tokens:
        return tokens[0]
    return "UNKNOWN"


def iter_log_lines(
    source: str | Path | None, last_lines: int = 0
) -> tuple[str, int, int, Iterator[tuple[int, str]]]:
    """Return (label, total_lines, first_scanned_line, iterator)."""

    if source is None:
        path = newest_log()
        source = path

    if str(source) == "-":
        raw_lines = [(idx, line.rstrip("\n")) for idx, line in enumerate(sys.stdin, 1)]
        total = len(raw_lines)
        if last_lines > 0:
            raw_lines = raw_lines[-last_lines:]
        first = raw_lines[0][0] if raw_lines else 0
        return "stdin", total, first, iter(raw_lines)

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(str(path))

    if last_lines > 0:
        buf: deque[tuple[int, str]] = deque(maxlen=last_lines)
        total = 0
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for total, line in enumerate(fh, 1):
                buf.append((total, line.rstrip("\n")))
        raw_lines = list(buf)
        first = raw_lines[0][0] if raw_lines else 0
        return str(path), total, first, iter(raw_lines)

    def stream() -> Iterator[tuple[int, str]]:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for idx, line in enumerate(fh, 1):
                yield idx, line.rstrip("\n")

    total = 0
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for total, _ in enumerate(fh, 1):
            pass
    first = 1 if total else 0
    return str(path), total, first, stream()


def ratio_from_fields(fields: dict[str, str]) -> float | None:
    for key in ("dist_ratio", "distance_ratio", "ratio"):
        value = parse_float(fields.get(key))
        if value is not None:
            return value
    return None


def distance_from_fields(fields: dict[str, str]) -> float | None:
    for key in ("dist", "distance", "l1_dist", "distance_l1_price"):
        value = parse_float(fields.get(key))
        if value is not None:
            return value

    l1 = parse_float(fields.get("l1"))
    if l1 is None:
        return None
    for key in ("price", "mid", "px", "ref_price", "snapshot_mid", "stream_mid"):
        price = parse_float(fields.get(key))
        if price is not None:
            return abs(l1 - price)
    return None


def cancel_age_from_fields(fields: dict[str, str], line: str) -> float | None:
    value = parse_float(fields.get("age"))
    if value is not None:
        return value
    match = re.search(r"\bage\s*[:=]\s*([0-9]+(?:[.,][0-9]+)?)\s*s\b", line, re.I)
    if match:
        return parse_float(match.group(1))
    return None


def reject_reason(line: str, fields: dict[str, str]) -> str:
    explicit = fields.get("reason") or fields.get("reject") or fields.get("why")
    if explicit:
        return explicit.strip().upper().strip(",;|")

    upper = line.upper()
    if "BASKET_REJECT_BOLLINGER_TOO_FAR" in upper or "BOLLINGER_TOO_FAR" in upper:
        return "BOLLINGER_TOO_FAR"
    if "BASKET_REJECT_MARKETABLE_LIMIT" in upper or "MARKETABLE_LIMIT" in upper:
        return "MARKETABLE_LIMIT"
    if "BOLLINGER_WIDTH_TOO_SMALL" in upper or "WIDTH TOO SMALL" in upper:
        return "BOLLINGER_WIDTH_TOO_SMALL"
    if "MIN_DISTANCE" in upper or "MIN DISTANCE" in upper:
        return "MIN_DISTANCE"
    if "MARKETABLE" in upper:
        return "MARKETABLE_LIMIT"
    return "UNCLASSIFIED"


def add_last(last: LastSeen, line_no: int, line: str, fields: dict[str, str]) -> None:
    last.line_no = line_no
    last.text = line
    last.fields = dict(fields)


def process_line(
    line_no: int, line: str, stats_by_symbol: defaultdict[str, SymbolStats]
) -> None:
    upper = line.upper()
    markers = [marker for marker in EVENT_MARKERS if marker in upper]
    if not markers:
        return

    fields = parse_fields(line)
    symbol = find_symbol(line, markers[0])
    stats = stats_by_symbol[symbol]

    if "BASKET_NEW" in upper:
        stats.counts["BASKET_NEW"] += 1

    if "LIMIT_OK" in upper:
        stats.counts["LIMIT_OK"] += 1

    if "BASKET_FILL" in upper:
        stats.counts["BASKET_FILL"] += 1

    if "BASKET_TP_OK" in upper:
        stats.counts["BASKET_TP_OK"] += 1

    if "BASKET_TP_BLOCKED" in upper:
        stats.counts["BASKET_TP_BLOCKED"] += 1

    if "BASKET_TP_LADDER_CHECK" in upper:
        stats.counts["BASKET_TP_LADDER_CHECK"] += 1
        add_last(stats.last_tp_ladder, line_no, line, fields)

    if "BROKER_EMPTY_RESET" in upper:
        stats.counts["BROKER_EMPTY_RESET"] += 1

    if "REFRESH_06C_RATE_LIMIT" in upper:
        stats.counts["REFRESH_06C_RATE_LIMIT"] += 1

    if "BASKET_PENDING_CANCEL" in upper:
        stats.counts["BASKET_PENDING_CANCEL"] += 1
        age = cancel_age_from_fields(fields, line)
        if age is not None:
            stats.cancel_ages.append(age)
        add_last(stats.last_cancel, line_no, line, fields)

    if "BOLLINGER_ENTRY_OBSERVE" in upper:
        stats.counts["BOLLINGER_ENTRY_OBSERVE"] += 1
        dist = distance_from_fields(fields)
        ratio = ratio_from_fields(fields)
        if dist is not None:
            stats.entry_dists.append(dist)
        if ratio is not None:
            stats.entry_ratios.append(ratio)
        add_last(stats.last_entry, line_no, line, fields)

    if "BOLLINGER_WIDTH_OBSERVE" in upper:
        stats.counts["BOLLINGER_WIDTH_OBSERVE"] += 1
        ok = parse_bool(fields.get("ok"))
        width = parse_float(fields.get("width"))
        required = parse_float(fields.get("required") or fields.get("min_width"))
        ratio = parse_float(fields.get("ratio"))
        if ratio is None and width is not None and required:
            ratio = width / required
        if ratio is not None:
            stats.width_ratios.append(ratio)
        if ok is True:
            stats.width_ok += 1
        elif ok is False:
            stats.width_false += 1
            stats.counts["BOLLINGER_WIDTH_TOO_SMALL"] += 1
        add_last(stats.last_width, line_no, line, fields)

    if (
        "BASKET_REJECT" in upper
        or "BOLLINGER_WIDTH_TOO_SMALL" in upper
        or "BOLLINGER TOO SMALL" in upper
        or "WIDTH TOO SMALL" in upper
    ):
        if "BASKET_REJECT" in upper:
            stats.counts["BASKET_REJECT"] += 1
        reason = reject_reason(line, fields)
        stats.reject_reasons[reason] += 1
        if reason == "BOLLINGER_TOO_FAR":
            stats.counts["BASKET_REJECT_BOLLINGER_TOO_FAR"] += 1
        elif reason == "MARKETABLE_LIMIT":
            stats.counts["BASKET_REJECT_MARKETABLE_LIMIT"] += 1
        elif reason == "BOLLINGER_WIDTH_TOO_SMALL":
            stats.counts["BOLLINGER_WIDTH_TOO_SMALL"] += 1


def average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def fmt_number(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def fmt_avg_max(values: list[float], digits: int = 2) -> str:
    if not values:
        return "-"
    return f"{fmt_number(average(values), digits)}/{fmt_number(max(values), digits)}"


def width_ok_percent(stats: SymbolStats) -> str:
    total = stats.width_ok + stats.width_false
    if total <= 0:
        return "-"
    return f"{(100.0 * stats.width_ok / total):.0f}%"


def active_score(item: tuple[str, SymbolStats]) -> int:
    _, stats = item
    return sum(stats.counts.values()) + len(stats.entry_dists) + len(stats.cancel_ages)


def summary_rows(stats_by_symbol: dict[str, SymbolStats]) -> list[dict[str, object]]:
    rows = []
    for symbol, stats in sorted(
        stats_by_symbol.items(), key=lambda item: (-active_score(item), item[0])
    ):
        rows.append(
            {
                "symbol": symbol,
                "BASKET_NEW": stats.counts["BASKET_NEW"],
                "LIMIT_OK": stats.counts["LIMIT_OK"],
                "BASKET_FILL": stats.counts["BASKET_FILL"],
                "BASKET_TP_OK": stats.counts["BASKET_TP_OK"],
                "BASKET_PENDING_CANCEL": stats.counts["BASKET_PENDING_CANCEL"],
                "cancel_age_avg": average(stats.cancel_ages),
                "cancel_age_max": max(stats.cancel_ages) if stats.cancel_ages else None,
                "BASKET_REJECT_BOLLINGER_TOO_FAR": stats.counts[
                    "BASKET_REJECT_BOLLINGER_TOO_FAR"
                ],
                "BASKET_REJECT_MARKETABLE_LIMIT": stats.counts[
                    "BASKET_REJECT_MARKETABLE_LIMIT"
                ],
                "BOLLINGER_WIDTH_TOO_SMALL": stats.counts[
                    "BOLLINGER_WIDTH_TOO_SMALL"
                ],
                "width_ok_percent": width_ok_percent(stats),
                "entry_dist_avg": average(stats.entry_dists),
                "entry_dist_max": max(stats.entry_dists) if stats.entry_dists else None,
                "entry_ratio_avg": average(stats.entry_ratios),
                "entry_ratio_max": max(stats.entry_ratios)
                if stats.entry_ratios
                else None,
            }
        )
    return rows


def make_markdown(
    stats_by_symbol: dict[str, SymbolStats],
    source_label: str,
    total_lines: int,
    first_scanned_line: int,
    scanned_lines: int,
) -> str:
    lines: list[str] = []
    lines.append("# V24.3.2 - ENTRY QUALITY REPORT")
    lines.append("")
    lines.append(f"- log: `{source_label}`")
    lines.append(f"- lines in source: `{total_lines}`")
    lines.append(f"- lines scanned: `{scanned_lines}` from line `{first_scanned_line}`")
    lines.append("")

    rows = summary_rows(stats_by_symbol)
    if not rows:
        lines.append("No entry-quality events found in the scanned log range.")
        return "\n".join(lines) + "\n"

    headers = [
        "Asset",
        "NEW",
        "LIMIT_OK",
        "FILL",
        "TP_OK",
        "CANCEL",
        "cancel age avg/max",
        "REJ far",
        "REJ market",
        "WIDTH small",
        "BB width OK",
        "L1/price avg/max",
        "dist_ratio avg/max",
    ]
    lines.append("## Summary by asset")
    lines.append("")
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        values = [
            str(row["symbol"]),
            str(row["BASKET_NEW"]),
            str(row["LIMIT_OK"]),
            str(row["BASKET_FILL"]),
            str(row["BASKET_TP_OK"]),
            str(row["BASKET_PENDING_CANCEL"]),
            (
                "-"
                if row["cancel_age_avg"] is None
                else f"{fmt_number(row['cancel_age_avg'], 1)}/{fmt_number(row['cancel_age_max'], 1)}s"
            ),
            str(row["BASKET_REJECT_BOLLINGER_TOO_FAR"]),
            str(row["BASKET_REJECT_MARKETABLE_LIMIT"]),
            str(row["BOLLINGER_WIDTH_TOO_SMALL"]),
            str(row["width_ok_percent"]),
            (
                "-"
                if row["entry_dist_avg"] is None
                else f"{fmt_number(row['entry_dist_avg'], 4)}/{fmt_number(row['entry_dist_max'], 4)}"
            ),
            (
                "-"
                if row["entry_ratio_avg"] is None
                else f"{fmt_number(row['entry_ratio_avg'], 3)}/{fmt_number(row['entry_ratio_max'], 3)}"
            ),
        ]
        lines.append("| " + " | ".join(values) + " |")

    lines.append("")
    lines.append("## Last observed entry/cancel context")
    lines.append("")
    for symbol, stats in sorted(
        stats_by_symbol.items(), key=lambda item: (-active_score(item), item[0])
    ):
        if not (stats.last_entry.line_no or stats.last_cancel.line_no or stats.last_width.line_no):
            continue
        parts = [f"- {symbol}:"]
        if stats.last_entry.line_no:
            fields = stats.last_entry.fields
            parts.append(
                "entry line "
                f"{stats.last_entry.line_no}"
                f" L1={fields.get('l1', '-')}"
                f" dist={fields.get('dist', fields.get('distance', '-'))}"
                f" dist_ratio={fields.get('dist_ratio', fields.get('ratio', '-'))}"
            )
        if stats.last_cancel.line_no:
            age = cancel_age_from_fields(stats.last_cancel.fields, stats.last_cancel.text)
            parts.append(
                "cancel line "
                f"{stats.last_cancel.line_no}"
                f" age={fmt_number(age, 1)}s"
            )
        if stats.last_width.line_no:
            fields = stats.last_width.fields
            parts.append(
                "width line "
                f"{stats.last_width.line_no}"
                f" width={fields.get('width', '-')}"
                f" required={fields.get('required', fields.get('min_width', '-'))}"
                f" ratio={fields.get('ratio', '-')}"
                f" ok={fields.get('ok', '-')}"
            )
        lines.append(" ".join(parts))

    lines.append("")
    lines.append("## Reject reasons")
    lines.append("")
    for symbol, stats in sorted(
        stats_by_symbol.items(), key=lambda item: (-sum(item[1].reject_reasons.values()), item[0])
    ):
        if not stats.reject_reasons:
            continue
        reasons = ", ".join(
            f"{reason}={count}" for reason, count in stats.reject_reasons.most_common()
        )
        lines.append(f"- {symbol}: {reasons}")

    return "\n".join(lines) + "\n"


def write_csv(rows: list[dict[str, object]], output: TextIO) -> None:
    fieldnames = [
        "symbol",
        "BASKET_NEW",
        "LIMIT_OK",
        "BASKET_FILL",
        "BASKET_TP_OK",
        "BASKET_PENDING_CANCEL",
        "cancel_age_avg",
        "cancel_age_max",
        "BASKET_REJECT_BOLLINGER_TOO_FAR",
        "BASKET_REJECT_MARKETABLE_LIMIT",
        "BOLLINGER_WIDTH_TOO_SMALL",
        "width_ok_percent",
        "entry_dist_avg",
        "entry_dist_max",
        "entry_ratio_avg",
        "entry_ratio_max",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        source_label, total_lines, first_scanned_line, line_iter = iter_log_lines(
            args.log, args.last_lines
        )
        stats_by_symbol: defaultdict[str, SymbolStats] = defaultdict(SymbolStats)
        scanned_lines = 0
        for line_no, line in line_iter:
            scanned_lines += 1
            process_line(line_no, line, stats_by_symbol)

        if args.format == "markdown":
            report = make_markdown(
                dict(stats_by_symbol),
                source_label,
                total_lines,
                first_scanned_line,
                scanned_lines,
            )
        elif args.format == "json":
            payload = {
                "source": source_label,
                "total_lines": total_lines,
                "first_scanned_line": first_scanned_line,
                "scanned_lines": scanned_lines,
                "rows": summary_rows(dict(stats_by_symbol)),
                "reject_reasons": {
                    symbol: dict(stats.reject_reasons)
                    for symbol, stats in sorted(stats_by_symbol.items())
                    if stats.reject_reasons
                },
            }
            report = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        else:
            from io import StringIO

            buf = StringIO()
            write_csv(summary_rows(dict(stats_by_symbol)), buf)
            report = buf.getvalue()

        if args.out:
            Path(args.out).write_text(report, encoding="utf-8")
        else:
            sys.stdout.write(report)
        return 0
    except Exception as exc:
        print(f"ENTRY_QUALITY_REPORT_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
