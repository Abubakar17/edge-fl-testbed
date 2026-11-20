#!/usr/bin/env python3
"""Summarise P1-00 baseline measurements (ping + iperf3) into one table.

Expects the files produced by the baseline PowerShell loop:
    ping_<a>_<b>_<round>.txt          e.g. ping_h3_n2l_1.txt
    iperf_<src>_to_<dst>_<round>.json e.g. iperf_n2l_to_h3_2.json

Usage:
    python summarize_baseline.py [folder]      (default: current folder)

Prints a table and writes baseline_summary.csv in the same folder.
Values are the median across rounds; min-max shows the spread.
Standard library only.
"""

import csv
import json
import re
import statistics
import sys
from pathlib import Path

PING_RE = re.compile(r"^ping_(\w+?)_(\w+?)_(\d+)\.txt$")
IPERF_RE = re.compile(r"^iperf_(\w+?)_to_(\w+?)_(\d+)\.json$")
RTT_RE = re.compile(r"rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms")
LOSS_RE = re.compile(r"([\d.]+)% packet loss")


def read_text(path: Path) -> str:
    """Read a file whatever encoding PowerShell used (UTF-8, UTF-8 BOM, UTF-16)."""
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


def parse_ping(path: Path):
    text = read_text(path)
    rtt = RTT_RE.search(text)
    loss = LOSS_RE.search(text)
    if not rtt:
        return None
    _min, avg, _max, mdev = map(float, rtt.groups())
    return {"avg": avg, "mdev": mdev, "loss": float(loss.group(1)) if loss else None}


def parse_iperf(path: Path):
    data = json.loads(read_text(path))
    if "error" in data:
        print(f"  ! {path.name}: iperf3 error: {data['error']}")
        return None
    end = data.get("end", {})
    received = end.get("sum_received", {})
    sent = end.get("sum_sent", {})
    if "bits_per_second" not in received:
        return None
    return {
        "mbps": received["bits_per_second"] / 1e6,  # what actually arrived
        "retransmits": sent.get("retransmits"),  # only reported by a Linux sender
    }


def spread(values, digits=2):
    return f"{min(values):.{digits}f}-{max(values):.{digits}f}" if len(values) > 1 else ""


def main():
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    pings, iperfs = {}, {}

    for f in sorted(folder.iterdir()):
        if m := PING_RE.match(f.name):
            res = parse_ping(f)
            if res:
                pings.setdefault(f"{m[1]} <-> {m[2]}", []).append(res)
            else:
                print(f"  ! {f.name}: no rtt line found (did the ping fail?)")
        elif m := IPERF_RE.match(f.name):
            res = parse_iperf(f)
            if res:
                iperfs.setdefault(f"{m[1]} -> {m[2]}", []).append(res)

    if not pings and not iperfs:
        sys.exit(f"No ping_*.txt or iperf_*.json files found in {folder.resolve()}")

    rows = []
    for link, runs in sorted(pings.items()):
        avgs = [r["avg"] for r in runs]
        losses = [r["loss"] for r in runs if r["loss"] is not None]
        rows.append(
            {
                "test": "ping RTT",
                "link": link,
                "rounds": len(runs),
                "median": round(statistics.median(avgs), 3),
                "unit": "ms",
                "spread": spread(avgs, 3),
                "extra": f"jitter(mdev) {statistics.median(r['mdev'] for r in runs):.3f} ms, "
                f"loss {max(losses) if losses else 0:.0f}%",
            }
        )
    for link, runs in sorted(iperfs.items()):
        mbps = [r["mbps"] for r in runs]
        retr = [r["retransmits"] for r in runs if r["retransmits"] is not None]
        rows.append(
            {
                "test": "iperf3 TCP",
                "link": link,
                "rounds": len(runs),
                "median": round(statistics.median(mbps), 1),
                "unit": "Mbit/s",
                "spread": spread(mbps),
                "extra": f"retransmits {int(statistics.median(retr))}" if retr else "",
            }
        )

    # Print a readable table
    headers = ["test", "link", "rounds", "median", "unit", "spread", "extra"]
    widths = {h: max(len(h), *(len(str(r[h])) for r in rows)) for h in headers}
    line = "  ".join(h.ljust(widths[h]) for h in headers)
    print(line)
    print("-" * len(line))
    for r in rows:
        print("  ".join(str(r[h]).ljust(widths[h]) for h in headers))

    out = folder / "baseline_summary.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
