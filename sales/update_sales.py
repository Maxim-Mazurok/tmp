"""Parse sales log files and update main .md files with frequency tables."""

import re
from collections import Counter
from pathlib import Path

SALES_DIR = Path(__file__).parent
REGIONS = {
    "alamo": "Alamo Sea",
    "dam": "Land Act Dam",
    "roxwood": "Roxwood",
    "ocean": "Ocean",
    "cave": "Cave",
    "humane-labs": "Humane Labs",
}

BUNDLES = {
    "Bronze Multizone #1": {"fish": ["Dutch Fish", "Ocean Perch", "Broadbill"], "bonus": 10750},
    "Bronze Multizone #2": {"fish": ["Brook Trout", "Pufferfish", "Green Eel"], "bonus": 11000},
    "Silver Multizone #1": {"fish": ["Swordfish", "Blue Warehou", "Stingray"], "bonus": 12500},
    "Silver Multizone #2": {"fish": ["Trevella", "Red Snapper", "Oreo Dory"], "bonus": 12250},
    "Gold Multizone #1": {"fish": ["Bluefin Tuna", "Musky", "Dolphinfish"], "bonus": 12750},
    "Gold Multizone #2": {"fish": ["Blue Marlin", "Blobfish", "Whale Shark"], "bonus": 15000},
    "Alamo Starter": {"fish": ["Morwhong", "Southern Tuna", "Silver Trevally"], "bonus": 10000},
    "Low Level Multizone": {"fish": ["Scollop", "Carp", "Grenadier"], "bonus": 11000},
}

# Fish prices: name -> (price, star_count, star_color)
# star_color: "" for regular, "green" for green, "purple" for purple
PRICES: dict[str, tuple[int, int, str]] = {
    "Whale Shark": (2850, 3, "green"),
    "Greenback Flounder": (2350, 2, ""),
    "Flathead": (1350, 1, ""),
    "Dolphinfish": (2350, 3, ""),
    "Silver Perch": (2000, 2, ""),
    "Orange Roughy": (2150, 1, "green"),
    "Mulloway": (2150, 1, "green"),
    "Snapper": (2150, 1, "green"),
    "Blackfin Tuna": (2000, 2, ""),
    "Oreo Dory": (2350, 2, ""),
    "Ling": (2350, 2, ""),
    "Atlantic Wolffish": (2150, 1, "green"),
    "Archerfish": (2500, 2, "green"),
    "Dover Sole": (2500, 2, "green"),
    "Boarfish": (1850, 1, ""),
    "Flounder": (2000, 1, ""),
    "Shortfin Batfish": (1850, 1, ""),
    "King Whiting": (2650, 3, ""),
    "Black Marlin": (2500, 3, ""),
    "Sockeye Salmon": (2150, 1, "green"),
    "Escolar": (1500, 1, ""),
    "Snow Crab": (1650, 2, ""),
    "Wahoo": (1850, 2, ""),
    "Chadfin": (8150, 0, ""),
    "John Dory": (2500, 2, "green"),
    "Green Eel": (2000, 1, ""),
    "Toadfish": (2000, 1, ""),
    "Sailfish": (2850, 3, "green"),
    "Dungeness Crab": (1650, 1, ""),
    "Southern Tuna": (1650, 2, ""),
    "Murray Cod": (1500, 1, ""),
    "Atlantic Salmon": (1850, 2, ""),
    "Gummy Shark": (2000, 2, ""),
    "Australian Herring": (1650, 1, ""),
    "Morwhong": (1350, 1, ""),
    "Yellow Tail": (2150, 2, ""),
    "Anglerfish": (2650, 3, ""),
    "Viperfish": (2000, 1, ""),
    "Australian Anchovy": (1850, 1, ""),
    "Sculpin": (2000, 1, ""),
    "Trout": (1650, 2, ""),
    "Yellowfin Tuna": (2850, 3, "green"),
    "Pollock": (1850, 1, ""),
    "Sand Whiting": (1500, 1, ""),
    "Great Barracuda": (2000, 3, ""),
    "Ocean Jacket": (1650, 1, ""),
    "Stingray": (2150, 2, ""),
    "Swordfish": (2500, 2, "green"),
    "Tiger Flathead": (2000, 1, ""),
    "Pufferfish": (1850, 1, ""),
    "Sturgeon": (1850, 2, ""),
    "Southern Garfish": (1650, 2, ""),
    "Cavefish": (2350, 2, ""),
    "Blue Marlin": (2500, 3, ""),
    "Blobfish": (2650, 3, ""),
    "Gemfish": (2500, 2, "green"),
    "Speckled Sea Trout": (2150, 2, ""),
    "Sunfish": (2500, 3, ""),
    "Snake Eel": (2350, 2, ""),
    "3 Eyed Fish": (10_000, 4, "purple"),
    "Silver Trevally": (2000, 3, ""),
    "Trumpetfish": (1850, 2, ""),
    "Red Snapper": (2000, 2, ""),
    "Black Bream": (1500, 1, ""),
    "Salmon": (2150, 2, ""),
    "Clownfish": (1650, 1, ""),
    "Sandy Sprat": (1350, 1, ""),
    "Triggerfish": (1500, 1, ""),
    "Dutch Fish": (2150, 1, "green"),
    "Ocean Perch": (1650, 1, ""),
    "Scollop": (1350, 1, ""),
    "King Mackerel": (2350, 3, ""),
    "Blue Tang": (2150, 1, "green"),
    "Pufferfish w/ Carrot": (10_000, 4, "purple"),
    "Rainbow Trout": (2150, 3, ""),
    "Haddock": (1850, 1, ""),
    "Albacore": (1350, 1, ""),
    "Brown Trout": (2000, 2, ""),
    "Bluefin Tuna": (2000, 3, ""),
    "Blue Warehou": (1650, 2, ""),
    "Lion Fish": (1850, 1, ""),
    "Banded Butterfly": (1500, 1, ""),
    "Baby Pufferfish": (10_000, 4, "purple"),
    "Bluehead Wrasse": (2150, 1, "green"),
    "Carp": (1850, 2, ""),
    "Amberjack": (2150, 2, ""),
    "Barramundi": (1650, 1, ""),
    "Hogfish": (2500, 2, "green"),
    "Catfish": (2000, 1, ""),
    "Brook Trout": (1500, 1, ""),
    "Pike": (2150, 3, ""),
    "Blue Crab": (2000, 1, ""),
    "Halibut": (1350, 1, ""),
    "Broadbill": (1350, 1, ""),
    "Musky": (2150, 3, ""),
    "Grouper": (1650, 1, ""),
    "Grenadier": (2350, 3, ""),
    "Redfish": (1350, 1, ""),
    "Brown Eel": (2350, 2, ""),
    "Trevella": (1850, 2, ""),
    "Australian Pilchard": (1850, 1, ""),
    "Cod": (1500, 1, ""),
    "Golden Perch": (1650, 2, ""),
}

TIER_PRICES = {
    "Alamo Sea":    {1: 1350, 2: 1650, 3: 2000},
    "Land Act Dam": {1: 1500, 2: 1850, 3: 2150},
    "Roxwood":      {1: 1650, 2: 2000, 3: 2350},
    "Ocean":        {1: 1850, 2: 2150, 3: 2500},
    "Cave":         {1: 2000, 2: 2350, 3: 2650},
    "Humane Labs":  {1: 2150, 2: 2500, 3: 2850},
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


def get_location(price: int, stars: int, color: str) -> str:
    """Derive location from price, star count, and color."""
    if color == "green":
        return "Humane Labs"
    if color == "purple" or stars == 0:
        return "Special"
    for location, tier_prices in TIER_PRICES.items():
        if tier_prices.get(stars) == price:
            return location
    return "Unknown"


def build_prices_table() -> str:
    """Build a padded markdown table of fish prices with location."""
    data = []
    for name, (price, stars, color) in PRICES.items():
        price_string = f"${price:,}"
        if stars == 0:
            stars_string = "-"
        else:
            stars_string = "\u2605" * stars
            if color:
                stars_string += f" {color}"
        location = get_location(price, stars, color)
        data.append((name, price_string, stars_string, location))

    w_name = max(len("Fish"), max(len(row[0]) for row in data))
    w_price = max(len("Price"), max(len(row[1]) for row in data))
    w_stars = max(len("Stars"), max(len(row[2]) for row in data))
    w_location = max(len("Location"), max(len(row[3]) for row in data))

    def fmt(name: str, price: str, stars: str, location: str) -> str:
        return f"| {name:<{w_name}} | {price:>{w_price}} | {stars:<{w_stars}} | {location:<{w_location}} |"

    lines = [
        fmt("Fish", "Price", "Stars", "Location"),
        f"|{'-' * (w_name + 2)}|{'-' * (w_price + 1)}:|{'-' * (w_stars + 2)}|{'-' * (w_location + 2)}|",
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
