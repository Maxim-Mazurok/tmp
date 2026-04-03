"""Parse sales log files and update main .md files with frequency tables."""

import re
from collections import Counter
from pathlib import Path

SALES_DIR = Path(__file__).parent
REGIONS = {
    "alamo": "Alamo Sea",
    "dam": "Land Act Dam",
}


def parse_log(path: Path) -> Counter:
    """Parse a log file and return total fish counts across all batches."""
    totals: Counter = Counter()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line == "--sold":
            continue
        m = re.match(r"^(.+?)\t(\d+)$", line)
        if m:
            name, count = m.group(1), int(m.group(2))
            totals[name] += count
    return totals


def build_table(counts: Counter) -> str:
    """Build a padded markdown table sorted alphabetically."""
    rows = sorted(counts.items(), key=lambda x: x[0])
    total = sum(counts.values())

    # Prepare data rows: (name, count_str, pct_str)
    data = []
    for name, count in rows:
        pct = count / total * 100
        data.append((name, str(count), f"{pct:.1f}%"))
    total_row = ("**Total**", f"**{total}**", "**100%**")

    # Column widths
    w_name = max(len("Fish"), max(len(r[0]) for r in data), len(total_row[0]))
    w_count = max(len("Count"), max(len(r[1]) for r in data), len(total_row[1]))
    w_pct = max(len("%"), max(len(r[2]) for r in data), len(total_row[2]))

    def fmt(n: str, c: str, p: str) -> str:
        return f"| {n:<{w_name}} | {c:>{w_count}} | {p:>{w_pct}} |"

    lines = [
        fmt("Fish", "Count", "%"),
        f"|{'-' * (w_name + 2)}|{'-' * (w_count + 1)}:|{'-' * (w_pct + 1)}:|",
    ]
    for name, count_s, pct_s in data:
        lines.append(fmt(name, count_s, pct_s))
    lines.append(fmt(*total_row))
    return "\n".join(lines)


def update_md(region_key: str, region_name: str) -> None:
    log_path = SALES_DIR / f"{region_key}-log.md"
    md_path = SALES_DIR / f"{region_key}.md"

    if not log_path.exists():
        print(f"  skipping {region_key}: no log file")
        return

    counts = parse_log(log_path)
    if not counts:
        print(f"  skipping {region_key}: no data")
        return

    batches = log_path.read_text().count("--sold")
    table = build_table(counts)
    content = f"# {region_name}\n\n{batches} batches sold\n\n{table}\n"
    md_path.write_text(content)
    print(f"  {region_key}.md updated ({len(counts)} fish, {batches} batches)")


def main() -> None:
    for key, name in REGIONS.items():
        update_md(key, name)


if __name__ == "__main__":
    main()
