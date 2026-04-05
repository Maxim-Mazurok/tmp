"""Log parsing, fish classification, and tier/probability utilities."""

import re
from collections import Counter
from pathlib import Path

from constants import (
    BUNDLES,
    LOCATION_ORDER,
    PRICES,
    REGIONS,
    SALES_DIR,
    TIER_DROP_PERCENTAGES,
    TIER_PRICES,
)


def parse_log(path: Path) -> Counter:
    """Parse a log file and return total fish counts across all batches."""
    totals: Counter = Counter()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line == "--sold":
            continue
        match = re.match(r"^(.+?)(?:\t|  )(\d+)$", line)
        if match:
            name, count = match.group(1), int(match.group(2))
            totals[name] += count
    return totals


def stars_string(name: str) -> str:
    """Return the star display string for a fish name."""
    if name not in PRICES:
        return "?"
    _price, star_count, color = PRICES[name]
    if star_count == 0:
        return "-"
    result = "x" * star_count
    if color:
        result += f" {color}"
    return result


def stars_sort_key(name: str) -> tuple[int, str]:
    """Return (star_count, color) for sorting. Higher stars first, green last."""
    if name not in PRICES:
        return (0, "")
    _price, star_count, color = PRICES[name]
    return (star_count, color)


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


def fish_location(name: str) -> str:
    """Determine which location a fish belongs to based on its price and star tier."""
    if name not in PRICES:
        return "Unknown"
    price, star_count, color = PRICES[name]
    return get_location(price, star_count, color)


# Count fish species per (location, star_tier) for probability estimation
_LOCATION_TIER_SPECIES: dict[str, dict[int, int]] = {}
for _name, (_price, _stars, _color) in PRICES.items():
    _location = fish_location(_name)
    if _location not in ("Unknown", "Special"):
        _LOCATION_TIER_SPECIES.setdefault(_location, {})
        _LOCATION_TIER_SPECIES[_location][_stars] = (
            _LOCATION_TIER_SPECIES[_location].get(_stars, 0) + 1
        )


def detect_unlocked_locations() -> list[str]:
    """Auto-detect unlocked locations based on which have log data.

    Returns all locations from the first up to the highest one with a log file,
    since locations unlock in order.
    """
    highest_index = -1
    for region_key, region_name in REGIONS.items():
        log_path = SALES_DIR / f"{region_key}-log.md"
        if log_path.exists():
            counts = parse_log(log_path)
            if counts:
                index = LOCATION_ORDER.index(region_name)
                if index > highest_index:
                    highest_index = index
    if highest_index < 0:
        return []
    return LOCATION_ORDER[:highest_index + 1]


def bundle_min_tier(bundle_name: str) -> int | None:
    """Return the minimum tier (1-based index) needed for a bundle.

    Returns None if any fish has an unknown location.
    """
    bundle_info = BUNDLES[bundle_name]
    max_index = -1
    for fish in bundle_info["fish"]:
        location = fish_location(fish)
        if location not in LOCATION_ORDER:
            return None
        index = LOCATION_ORDER.index(location)
        if index > max_index:
            max_index = index
    return max_index + 1


def estimate_fish_probability(
    fish_name: str,
    location: str,
    location_counts: Counter,
) -> float | None:
    """Estimate the catch probability for an unseen fish at a location.

    Uses the location's observed tier distribution and the percentage template
    for that tier. Assigns the lowest percentage slot since unseen fish are
    likely the rarest.
    """
    _, star_count, _ = PRICES[fish_name]
    total = sum(location_counts.values())

    tier_caught = sum(
        count for name, count in location_counts.items()
        if name in PRICES and PRICES[name][1] == star_count
    )
    if tier_caught == 0:
        return None

    species_in_tier = _LOCATION_TIER_SPECIES.get(location, {}).get(star_count, 1)
    tier_rate = tier_caught / total

    # Use the lowest percentage from the template for unseen fish
    template = TIER_DROP_PERCENTAGES.get(star_count)
    if template and species_in_tier <= len(template):
        lowest_percentage = template[species_in_tier - 1]
        template_sum = sum(template[:species_in_tier])
        return tier_rate * lowest_percentage / template_sum

    return tier_rate / species_in_tier


def model_fish_probability(
    fish_name: str,
    location: str,
    location_counts: Counter,
) -> float | None:
    """Compute the model-based probability for a fish at a location.

    Uses the tier's percentage template to assign probabilities based on the
    fish's rank within its tier (sorted by observed count, descending).
    """
    _, star_count, _ = PRICES[fish_name]
    template = TIER_DROP_PERCENTAGES.get(star_count)
    if template is None:
        return None

    total = sum(location_counts.values())
    if total == 0:
        return None

    # Collect all fish in this tier at this location, sorted by count
    tier_fish = []
    for name, count in location_counts.items():
        if name in PRICES and PRICES[name][1] == star_count:
            tier_fish.append((name, count))
    tier_fish.sort(key=lambda pair: -pair[1])

    tier_total = sum(count for _, count in tier_fish)
    if tier_total == 0:
        return None

    tier_rate = tier_total / total

    # Find rank of this fish in tier
    species_in_tier = _LOCATION_TIER_SPECIES.get(location, {}).get(star_count, 1)
    fish_rank = None
    for rank, (name, _count) in enumerate(tier_fish):
        if name == fish_name:
            fish_rank = rank
            break

    if fish_rank is None:
        # Unseen fish gets the lowest slot
        fish_rank = species_in_tier - 1

    used_count = min(species_in_tier, len(template))
    if fish_rank >= used_count:
        fish_rank = used_count - 1

    percentage = template[fish_rank]
    template_sum = sum(template[:used_count])
    return tier_rate * percentage / template_sum
