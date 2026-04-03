"""Parse sales log files and update main .md files with frequency tables."""

import re
from collections import Counter
from pathlib import Path

SALES_DIR = Path(__file__).parent
REGIONS = {
    "alamo": "Alamo Sea",
    "dam": "Land Act Dam",
}

BUNDLES = {
    "Bronze Multizone #1": {"fish": ["Dutch Fish", "Ocean Perch", "Broadbill"], "bonus": 10750},
    "Bronze Multizone #2": {"fish": ["Brook Trout", "Pufferfish", "Green Eel"], "bonus": 11000},
    "Silver Multizone #1": {"fish": ["Swordfish", "Blue Warehou", "Stingray"], "bonus": 12500},
    "Silver Multizone #2": {"fish": ["Trevella", "Red Snapper", "Oreo Dory"], "bonus": 12250},
    "Gold Multizone #1": {"fish": ["Bluefin Tuna", "Musky", "Dolphinfish"], "bonus": 12750},
    "Gold Multizone #2": {"fish": ["Blue Marlin", "Blobfish", "Whale Shark"], "bonus": 15000},
    "Alamo Starter": {"fish": ["Morwhong", "Southern Tuna", "Silver Trevally"], "bonus": 10000},
    "Low Level Multizone": {"fish": ["Scallop", "Carp", "Grenadier"], "bonus": 11000},
}

# Fish prices: name -> (price, stars)
PRICES: dict[str, tuple[int, int]] = {
    "Black Bream": (1500, 1),
    "Carp": (1850, 2),
    "Morwhong": (1350, 1),
    "Musky": (2150, 3),
    "Silver Trevally": (2000, 3),
    "Southern Tuna": (1650, 2),
}

# Reverse lookup: fish name -> list of bundle names
FISH_BUNDLES: dict[str, list[str]] = {}
for bname, binfo in BUNDLES.items():
    for fish in binfo["fish"]:
        FISH_BUNDLES.setdefault(fish, []).append(bname)


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
    """Build a padded markdown table sorted alphabetically with bundles column."""
    rows = sorted(counts.items(), key=lambda x: x[0])
    total = sum(counts.values())

    # Prepare data rows: (name, count_str, pct_str, bundles_str)
    data = []
    for name, count in rows:
        pct = count / total * 100
        bundles = ", ".join(FISH_BUNDLES.get(name, []))
        data.append((name, str(count), f"{pct:.1f}%", bundles))
    total_row = ("**Total**", f"**{total}**", "**100%**", "")

    # Column widths
    w_name = max(len("Fish"), max(len(r[0]) for r in data), len(total_row[0]))
    w_count = max(len("Count"), max(len(r[1]) for r in data), len(total_row[1]))
    w_pct = max(len("%"), max(len(r[2]) for r in data), len(total_row[2]))
    w_bun = max(len("Bundles"), max((len(r[3]) for r in data), default=0), len(total_row[3]))

    def fmt(n: str, c: str, p: str, b: str) -> str:
        return f"| {n:<{w_name}} | {c:>{w_count}} | {p:>{w_pct}} | {b:<{w_bun}} |"

    lines = [
        fmt("Fish", "Count", "%", "Bundles"),
        f"|{'-' * (w_name + 2)}|{'-' * (w_count + 1)}:|{'-' * (w_pct + 1)}:|{'-' * (w_bun + 2)}|",
    ]
    for name, count_s, pct_s, bun_s in data:
        lines.append(fmt(name, count_s, pct_s, bun_s))
    lines.append(fmt(*total_row))
    return "\n".join(lines)


def build_bundles_table() -> str:
    """Build a padded markdown table of all bundles."""
    data = []
    for bname, binfo in BUNDLES.items():
        fish_list = ", ".join(binfo["fish"])
        bonus = f"${binfo['bonus']:,}"
        data.append((bname, fish_list, bonus))

    w_name = max(len("Bundle"), max(len(r[0]) for r in data))
    w_fish = max(len("Fish"), max(len(r[1]) for r in data))
    w_bonus = max(len("Bonus"), max(len(r[2]) for r in data))

    def fmt(n: str, f: str, b: str) -> str:
        return f"| {n:<{w_name}} | {f:<{w_fish}} | {b:>{w_bonus}} |"

    lines = [
        fmt("Bundle", "Fish", "Bonus"),
        f"|{'-' * (w_name + 2)}|{'-' * (w_fish + 2)}|{'-' * (w_bonus + 1)}:|",
    ]
    for row in data:
        lines.append(fmt(*row))
    return "\n".join(lines)


def build_prices_table() -> str:
    """Build a padded markdown table of fish prices."""
    data = []
    for name in sorted(PRICES):
        price, stars = PRICES[name]
        data.append((name, f"${price:,}", "\u2605" * stars))

    w_name = max(len("Fish"), max(len(r[0]) for r in data))
    w_price = max(len("Price"), max(len(r[1]) for r in data))
    w_stars = max(len("Stars"), max(len(r[2]) for r in data))

    def fmt(n: str, p: str, s: str) -> str:
        return f"| {n:<{w_name}} | {p:>{w_price}} | {s:<{w_stars}} |"

    lines = [
        fmt("Fish", "Price", "Stars"),
        f"|{'-' * (w_name + 2)}|{'-' * (w_price + 1)}:|{'-' * (w_stars + 2)}|",
    ]
    for row in data:
        lines.append(fmt(*row))
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

    # Write bundles.md
    bundles_md = SALES_DIR / "bundles.md"
    table = build_bundles_table()
    bundles_md.write_text(f"# Bundles\n\n{table}\n")
    print(f"  bundles.md updated ({len(BUNDLES)} bundles)")

    # Write prices.md
    prices_md = SALES_DIR / "prices.md"
    table = build_prices_table()
    prices_md.write_text(f"# Fish Prices\n\n{table}\n", encoding="utf-8")
    print(f"  prices.md updated ({len(PRICES)} fish)")


if __name__ == "__main__":
    main()
