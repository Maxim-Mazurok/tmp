"""Parse sales log files and update main .md files with frequency tables."""

import math
import re
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import TypedDict

SALES_DIR = Path(__file__).parent
REGIONS = {
    "alamo": "Alamo Sea",
    "dam": "Land Act Dam",
    "roxwood": "Roxwood",
    "ocean": "Ocean",
    "cave": "Cave",
    "humane-labs": "Humane Labs",
}


class BundleInfo(TypedDict):
    fish: list[str]
    bonus: int


BUNDLES: dict[str, BundleInfo] = {
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

# Time per fish (seconds)
SECONDS_WAITING_FOR_BITE = 100  # decreases with level ups
SECONDS_REELING_IN = 15         # improves with skill
SECONDS_PER_FISH = SECONDS_WAITING_FOR_BITE + SECONDS_REELING_IN
FISH_PER_HOUR = 3600 / SECONDS_PER_FISH

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


def _stars_string(name: str) -> str:
    """Return the star display string for a fish name."""
    if name not in PRICES:
        return "?"
    _price, star_count, color = PRICES[name]
    if star_count == 0:
        return "-"
    result = "\u2605" * star_count
    if color:
        result += f" {color}"
    return result


def _stars_sort_key(name: str) -> tuple[int, str]:
    """Return (star_count, color) for sorting. Higher stars first, green last."""
    if name not in PRICES:
        return (0, "")
    _price, star_count, color = PRICES[name]
    return (star_count, color)


def build_table(counts: Counter) -> str:
    """Build a padded markdown table sorted by stars (desc) then % (desc)."""
    total = sum(counts.values())

    # Prepare data rows: (name, count, pct, bundles_str, stars_str)
    raw_rows = []
    for name, count in counts.items():
        percentage = count / total * 100
        bundles = ", ".join(FISH_BUNDLES.get(name, []))
        stars = _stars_string(name)
        star_count, color = _stars_sort_key(name)
        raw_rows.append((name, count, percentage, bundles, stars, star_count, color))

    # Sort: stars desc, green after regular, then % desc
    raw_rows.sort(key=lambda row: (-row[5], row[6], -row[2]))

    data = [
        (name, str(count), f"{percentage:.1f}%", stars, bundles)
        for name, count, percentage, bundles, stars, _star_count, _color in raw_rows
    ]
    total_row = ("**Total**", f"**{total}**", "**100%**", "", "")

    # Column widths
    w_name = max(len("Fish"), max(len(row[0]) for row in data), len(total_row[0]))
    w_count = max(len("Count"), max(len(row[1]) for row in data), len(total_row[1]))
    w_pct = max(len("%"), max(len(row[2]) for row in data), len(total_row[2]))
    w_stars = max(len("Stars"), max(len(row[3]) for row in data), len(total_row[3]))
    w_bun = max(len("Bundles"), max((len(row[4]) for row in data), default=0), len(total_row[4]))

    def fmt(name: str, count: str, percentage: str, stars: str, bundles: str) -> str:
        return (
            f"| {name:<{w_name}} | {count:>{w_count}} | {percentage:>{w_pct}}"
            f" | {stars:<{w_stars}} | {bundles:<{w_bun}} |"
        )

    lines = [
        fmt("Fish", "Count", "%", "Stars", "Bundles"),
        (
            f"|{'-' * (w_name + 2)}|{'-' * (w_count + 1)}:|{'-' * (w_pct + 1)}:"
            f"|{'-' * (w_stars + 2)}|{'-' * (w_bun + 2)}|"
        ),
    ]
    for row in data:
        lines.append(fmt(*row))
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


def build_comparison_table() -> str:
    """Build a revenue comparison table using total fish frequencies.

    For each location with data, computes:
    - Expected $/fish from sales (weighted average price by catch frequency)
    - Which bundles are available and their probability-weighted bonus per fish
    - Total expected $/fish
    """
    rows = []
    for region_key, region_name in REGIONS.items():
        log_path = SALES_DIR / f"{region_key}-log.md"
        if not log_path.exists():
            continue

        counts = parse_log(log_path)
        if not counts:
            continue

        total_fish = sum(counts.values())

        # Weighted average sale price per fish
        total_sale_value = sum(
            counts[name] * PRICES[name][0]
            for name in counts
            if name in PRICES
        )
        sale_value_per_fish = total_sale_value / total_fish

        # Bundle value per fish:
        # For each bundle, compute the probability that a random fish contributes
        # to completing it. The bottleneck is the rarest fish in the bundle.
        # Expected completions per N fish ≈ min(probability_i) * N for each bundle.
        # So bundle value per fish = sum(min_prob * bonus) for each available bundle.
        bundle_value_per_fish = 0.0
        available_bundles = []
        for bundle_name, bundle_info in BUNDLES.items():
            fish_probabilities = []
            for fish in bundle_info["fish"]:
                if fish not in counts:
                    break
                fish_probabilities.append(counts[fish] / total_fish)
            else:
                # All fish in this bundle were caught at this location
                bottleneck_probability = min(fish_probabilities)
                bundle_contribution = bottleneck_probability * bundle_info["bonus"]
                bundle_value_per_fish += bundle_contribution
                available_bundles.append(bundle_name)

        total_value_per_fish = sale_value_per_fish + bundle_value_per_fish

        bundles_string = ", ".join(available_bundles) if available_bundles else "none"
        revenue_per_hour = total_value_per_fish * FISH_PER_HOUR

        rows.append((
            region_name,
            str(total_fish),
            f"${sale_value_per_fish:,.0f}",
            bundles_string,
            f"${bundle_value_per_fish:,.0f}",
            f"**${total_value_per_fish:,.0f}**",
            f"${revenue_per_hour:,.0f}",
        ))

    if not rows:
        return ""

    headers = (
        "Location", "Fish Caught", "$/Fish (sales)",
        "Available Bundles", "$/Fish (bundles)", "$/Fish (total)",
        "$/Hour",
    )
    right_aligned_columns = {1, 2, 4, 5, 6}
    widths = [
        max(len(headers[column]), max(len(row[column]) for row in rows))
        for column in range(len(headers))
    ]

    def format_row(*values: str) -> str:
        return "| " + " | ".join(
            f"{value:>{widths[column]}}" if column in right_aligned_columns
            else f"{value:<{widths[column]}}"
            for column, value in enumerate(values)
        ) + " |"

    lines = [format_row(*headers)]
    separator_parts = []
    for column in range(len(headers)):
        if column in right_aligned_columns:
            separator_parts.append(f"{'-' * (widths[column] + 1)}:")
        else:
            separator_parts.append(f"{'-' * (widths[column] + 2)}")
    lines.append("|" + "|".join(separator_parts) + "|")
    for row in rows:
        lines.append(format_row(*row))
    return "\n".join(lines)


def expected_fish_to_complete_bundle(
    fish_probabilities: list[float],
) -> float:
    """Compute expected number of fish to catch before completing a bundle.

    Uses inclusion-exclusion on the coupon collector problem with unequal
    probabilities. For bundle fish with catch probabilities p_1 ... p_k:

    E[T] = sum over non-empty subsets S: (-1)^(|S|+1) / sum(p_i for i in S)
    """
    item_count = len(fish_probabilities)
    expected_value = 0.0
    for subset_size in range(1, item_count + 1):
        sign = (-1) ** (subset_size + 1)
        for subset in combinations(range(item_count), subset_size):
            probability_sum = sum(fish_probabilities[i] for i in subset)
            expected_value += sign / probability_sum
    return expected_value


def build_bundle_details(region_counts: dict[str, Counter]) -> str:
    """Build a bundle details section showing expected fish per bundle completion."""
    sections = []

    for region_name, counts in region_counts.items():
        total_fish = sum(counts.values())
        bundle_rows = []

        for bundle_name, bundle_info in BUNDLES.items():
            fish_probabilities = []
            fish_details = []
            for fish in bundle_info["fish"]:
                if fish not in counts:
                    break
                probability = counts[fish] / total_fish
                fish_probabilities.append(probability)
                fish_details.append(
                    f"{fish}: {counts[fish]}/{total_fish} ({probability:.1%})"
                )
            else:
                expected_fish = expected_fish_to_complete_bundle(fish_probabilities)
                expected_time_seconds = expected_fish * SECONDS_PER_FISH
                expected_time_minutes = expected_time_seconds / 60
                bonus_per_fish = bundle_info["bonus"] / expected_fish
                bundle_rows.append((
                    bundle_name,
                    ", ".join(bundle_info["fish"]),
                    f"${bundle_info['bonus']:,}",
                    f"{expected_fish:.0f}",
                    f"{expected_time_minutes:.0f} min",
                    f"${bonus_per_fish:,.0f}",
                    " \\| ".join(fish_details),
                ))

        if not bundle_rows:
            continue

        headers = (
            "Bundle", "Fish", "Bonus",
            "Avg Fish to Complete", "Avg Time", "Bonus/Fish", "Catch Rates",
        )
        widths = [
            max(len(headers[column]), max(len(row[column]) for row in bundle_rows))
            for column in range(len(headers))
        ]

        bundle_right_columns = {2, 3, 4, 5}

        def format_bundle_row(*values: str) -> str:
            return "| " + " | ".join(
                f"{value:>{widths[column]}}" if column in bundle_right_columns
                else f"{value:<{widths[column]}}"
                for column, value in enumerate(values)
            ) + " |"

        lines = [f"### {region_name}", "", format_bundle_row(*headers)]
        separator_parts = []
        for column in range(len(headers)):
            if column in bundle_right_columns:
                separator_parts.append(f"{'-' * (widths[column] + 1)}:")
            else:
                separator_parts.append(f"{'-' * (widths[column] + 2)}")
        lines.append("|" + "|".join(separator_parts) + "|")
        for row in bundle_rows:
            lines.append(format_bundle_row(*row))
        sections.append("\n".join(lines))

    if not sections:
        return ""
    return "## Bundle Details\n\n" + "\n\n".join(sections)


def _regularized_lower_gamma(shape: float, x: float) -> float:
    """P(a, x) — regularized lower incomplete gamma via series expansion."""
    if x <= 0:
        return 0.0
    term = 1.0 / shape
    total = term
    for n in range(1, 300):
        term *= x / (shape + n)
        total += term
        if abs(term) < 1e-12 * abs(total):
            break
    return math.exp(-x + shape * math.log(x) - math.lgamma(shape)) * total


def _chi_squared_p_value(statistic: float, degrees_of_freedom: int) -> float:
    """Upper-tail p-value for a chi-squared statistic."""
    if degrees_of_freedom <= 0 or statistic <= 0:
        return 1.0
    return 1.0 - _regularized_lower_gamma(
        degrees_of_freedom / 2.0, statistic / 2.0
    )


def fit_integer_weights(
    observed_counts: list[int],
    max_weight: int = 10,
) -> tuple[list[int], float, float]:
    """Find simplest integer weights matching observed distribution.

    Groups fish with identical counts so they always get the same weight.
    Weights are monotonically non-increasing with count (higher count -> higher
    or equal weight).  Picks the smallest total weight that passes p > 0.05.
    Returns (weights, chi_squared, p_value).
    """
    fish_count = len(observed_counts)
    total = sum(observed_counts)
    degrees_of_freedom = fish_count - 1

    # Group by count value (descending).  Fish with the same count share a
    # group and will always receive the same weight.
    indexed = sorted(enumerate(observed_counts), key=lambda pair: -pair[1])
    groups: list[tuple[int, list[int]]] = []
    for original_index, count in indexed:
        if groups and count == groups[-1][0]:
            groups[-1][1].append(original_index)
        else:
            groups.append((count, [original_index]))

    group_count = len(groups)
    group_sizes = [len(indices) for _, indices in groups]

    # Enumerate all non-increasing weight vectors (one weight per group).
    candidates: list[tuple[int, list[int], float, float]] = []

    def search(
        group_index: int,
        max_allowed: int,
        current_group_weights: list[int],
    ) -> None:
        if group_index == group_count:
            weights = [0] * fish_count
            total_weight = 0
            for g_index, (_, indices) in enumerate(groups):
                for fish_index in indices:
                    weights[fish_index] = current_group_weights[g_index]
                total_weight += current_group_weights[g_index] * group_sizes[g_index]

            expected = [total * weight / total_weight for weight in weights]
            chi_squared = sum(
                (observed_counts[i] - expected[i]) ** 2 / expected[i]
                for i in range(fish_count)
            )
            p_value = _chi_squared_p_value(chi_squared, degrees_of_freedom)
            candidates.append((total_weight, weights, chi_squared, p_value))
            return

        for weight in range(1, max_allowed + 1):
            search(group_index + 1, weight, current_group_weights + [weight])

    search(0, max_weight, [])

    passing = [candidate for candidate in candidates if candidate[3] > 0.05]
    if passing:
        # AIC-like scoring: balance fit quality vs complexity.
        # Lower is better: chi_squared + 2 * (distinct_weights - 1)
        passing.sort(key=lambda candidate: (
            candidate[2] + 2 * (len(set(candidate[1])) - 1),
            candidate[0],
        ))
        _, weights, chi_squared, p_value = passing[0]
    else:
        candidates.sort(key=lambda candidate: candidate[2])
        _, weights, chi_squared, p_value = candidates[0]

    common = math.gcd(*weights)
    return (
        [weight // common for weight in weights],
        chi_squared,
        p_value,
    )


def build_drop_rate_analysis(region_counts: dict[str, Counter]) -> str:
    """Build drop rate analysis: tier distribution and within-tier weight fitting."""
    if not region_counts:
        return ""

    sections: list[str] = ["## Drop Rate Analysis"]

    # --- Tier Distribution ---
    tier_data: dict[str, dict[int, tuple[int, int]]] = {}
    for region_name, counts in region_counts.items():
        total = sum(counts.values())
        tier_totals: dict[int, int] = {1: 0, 2: 0, 3: 0}
        for fish_name, fish_count in counts.items():
            if fish_name in PRICES:
                _price, star_count, _color = PRICES[fish_name]
                if star_count in tier_totals:
                    tier_totals[star_count] += fish_count
        tier_data[region_name] = {
            stars: (tier_total, total)
            for stars, tier_total in tier_totals.items()
        }

    region_names = list(region_counts.keys())

    tier_rows: list[tuple[str, ...]] = []
    for stars in [3, 2, 1]:
        star_label = "\u2605" * stars
        values: list[str] = [star_label]
        percentages: list[float] = []
        for region_name in region_names:
            tier_count, total = tier_data[region_name][stars]
            percentage = tier_count / total * 100
            percentages.append(percentage)
            values.append(f"{percentage:.1f}%")
        if len(region_names) > 1:
            average = sum(percentages) / len(percentages)
            values.append(f"{average:.1f}%")
        tier_rows.append(tuple(values))

    tier_headers: tuple[str, ...] = ("Tier",) + tuple(region_names)
    if len(region_names) > 1:
        tier_headers += ("Average",)
    tier_right_columns = set(range(1, len(tier_headers)))
    tier_widths = [
        max(len(tier_headers[column]), max(len(row[column]) for row in tier_rows))
        for column in range(len(tier_headers))
    ]

    def format_tier_row(*values: str) -> str:
        return "| " + " | ".join(
            f"{value:>{tier_widths[column]}}" if column in tier_right_columns
            else f"{value:<{tier_widths[column]}}"
            for column, value in enumerate(values)
        ) + " |"

    tier_separator = "|"
    for column in range(len(tier_headers)):
        if column in tier_right_columns:
            tier_separator += f"{"-" * (tier_widths[column] + 1)}:|"
        else:
            tier_separator += f"{"-" * (tier_widths[column] + 2)}|"

    sections.extend([
        "",
        "### Tier Distribution",
        "",
        "Tier drop rates are consistent across locations,"
        " suggesting a fixed game mechanic:",
        "",
        format_tier_row(*tier_headers),
        tier_separator,
    ])
    for row in tier_rows:
        sections.append(format_tier_row(*row))

    # --- Within-Tier Weights ---
    sections.extend([
        "",
        "### Within-Tier Weights",
        "",
        "Fitted smallest integer weights per fish"
        " using \u03c7\u00b2 goodness-of-fit (p > 0.05 = acceptable).",
    ])

    for region_name, counts in region_counts.items():
        tiers: dict[int, list[tuple[str, int]]] = {1: [], 2: [], 3: []}
        for fish_name, fish_count in counts.items():
            if fish_name in PRICES:
                _price, star_count, _color = PRICES[fish_name]
                if star_count in tiers:
                    tiers[star_count].append((fish_name, fish_count))

        for stars in [3, 2, 1]:
            fish_in_tier = tiers[stars]
            if len(fish_in_tier) < 2:
                continue

            fish_in_tier.sort(key=lambda pair: -pair[1])
            observed = [count for _name, count in fish_in_tier]
            tier_total = sum(observed)

            weights, chi_squared, p_value = fit_integer_weights(observed)
            weight_sum = sum(weights)

            star_label = "\u2605" * stars
            sections.extend([
                "",
                f"#### {region_name} \u2014 {star_label}"
                f" ({len(fish_in_tier)} fish, {tier_total} observed)",
                "",
            ])

            table_rows: list[tuple[str, ...]] = []
            for i, (name, count) in enumerate(fish_in_tier):
                observed_percentage = count / tier_total * 100
                expected_percentage = weights[i] / weight_sum * 100
                expected_count = tier_total * weights[i] / weight_sum
                residual = count - expected_count
                table_rows.append((
                    name,
                    str(count),
                    f"{observed_percentage:.1f}%",
                    str(weights[i]),
                    f"{expected_percentage:.1f}%",
                    f"{residual:+.1f}",
                ))

            weight_headers = (
                "Fish", "Count", "Observed %",
                "Weight", "Expected %", "Residual",
            )
            weight_right_columns = {1, 2, 3, 4, 5}
            weight_widths = [
                max(
                    len(weight_headers[column]),
                    max(len(row[column]) for row in table_rows),
                )
                for column in range(len(weight_headers))
            ]

            def format_weight_row(
                *values: str,
                widths: list[int] = weight_widths,
                right_columns: set[int] = weight_right_columns,
            ) -> str:
                return "| " + " | ".join(
                    f"{value:>{widths[column]}}" if column in right_columns
                    else f"{value:<{widths[column]}}"
                    for column, value in enumerate(values)
                ) + " |"

            sections.append(format_weight_row(*weight_headers))
            weight_separator = "|"
            for column in range(len(weight_headers)):
                if column in weight_right_columns:
                    weight_separator += f"{"-" * (weight_widths[column] + 1)}:|"
                else:
                    weight_separator += f"{"-" * (weight_widths[column] + 2)}|"
            sections.append(weight_separator)
            for row in table_rows:
                sections.append(format_weight_row(*row))

            quality = (
                "excellent" if p_value > 0.5
                else "good" if p_value > 0.1
                else "acceptable" if p_value > 0.05
                else "poor"
            )
            sections.extend([
                "",
                f"\u03c7\u00b2 = {chi_squared:.2f},"
                f" df = {len(fish_in_tier) - 1},"
                f" p = {p_value:.3f}"
                f" \u2014 {quality} fit",
            ])

    return "\n".join(sections)


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
    prices_header = """# Fish Prices

## Pricing Tiers

| Location     | ★      | ★★     | ★★★    |
|--------------|-------:|-------:|-------:|"""
    for location, tiers in TIER_PRICES.items():
        prices_header += f"\n| {location:<12} | ${tiers[1]:,} | ${tiers[2]:,} | ${tiers[3]:,} |"
    prices_header += "\n\nGreen stars (★ green) = Humane Labs tier. Special fish have fixed prices.\n\n## All Fish\n\n"
    table = build_prices_table()
    prices_md.write_text(prices_header + table + "\n", encoding="utf-8")
    print(f"  prices.md updated ({len(PRICES)} fish)")

    # Write comparison.md
    comparison_table = build_comparison_table()
    if comparison_table:
        region_counts: dict[str, Counter] = {}
        for region_key, region_name in REGIONS.items():
            log_path = SALES_DIR / f"{region_key}-log.md"
            if log_path.exists():
                counts = parse_log(log_path)
                if counts:
                    region_counts[region_name] = counts

        bundle_details = build_bundle_details(region_counts)
        drop_rate_analysis = build_drop_rate_analysis(region_counts)
        time_note = (
            f"Assuming {SECONDS_WAITING_FOR_BITE}s wait for bite"
            f" + {SECONDS_REELING_IN}s reel-in"
            f" = {SECONDS_PER_FISH}s per fish"
            f" ({FISH_PER_HOUR:.1f} fish/hour)."
        )
        content = f"# Location Comparison\n\n{time_note}\n\n{comparison_table}\n"
        if bundle_details:
            content += f"\n{bundle_details}\n"
        if drop_rate_analysis:
            content += f"\n{drop_rate_analysis}\n"

        comparison_md = SALES_DIR / "comparison.md"
        comparison_md.write_text(content)
        print("  comparison.md updated")


if __name__ == "__main__":
    main()
