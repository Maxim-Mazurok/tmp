"""Parse sales log files and update main .md files with frequency tables."""

from collections import Counter
from itertools import combinations
from typing import TypedDict

from constants import (
    BUNDLES,
    FISH_BUNDLES,
    LOCATION_ORDER,
    PRICES,
    REGIONS,
    SALES_DIR,
    SECONDS_REELING_IN,
    SECONDS_REELING_IN_DEFAULT,
    SECONDS_WAITING_FOR_BITE,
    SPECIAL_FISH_NOTES,
    TIER_DROP_PERCENTAGES,
    TIER_PRICES,
    fish_per_hour,
    seconds_per_fish,
)
from markdown import format_markdown_table
from parsing import (
    bundle_min_tier,
    detect_unlocked_locations,
    estimate_fish_probability,
    fish_location,
    get_location,
    model_fish_probability,
    parse_log,
    stars_sort_key,
    stars_string,
)
from stats import fit_integer_weights, fit_percentage_template


def build_table(counts: Counter) -> str:
    """Build a padded markdown table sorted by stars (desc) then % (desc)."""
    total = sum(counts.values())

    raw_rows = []
    for name, count in counts.items():
        percentage = count / total * 100
        bundles = ", ".join(FISH_BUNDLES.get(name, []))
        stars = stars_string(name)
        star_count, color = stars_sort_key(name)
        raw_rows.append((name, count, percentage, bundles, stars, star_count, color))

    raw_rows.sort(key=lambda row: (-row[5], row[6], -row[2]))

    rows = [
        (name, str(count), f"{percentage:.1f}%", stars, bundles)
        for name, count, percentage, bundles, stars, _star_count, _color in raw_rows
    ]
    rows.append(("**Total**", f"**{total}**", "**100%**", "", ""))

    return format_markdown_table(
        headers=("Fish", "Count", "%", "Stars", "Bundles"),
        rows=rows,
        right_aligned_columns={1, 2},
    )


def build_bundles_table() -> str:
    """Build a padded markdown table of all bundles."""
    rows = []
    for bundle_name, bundle_info in BUNDLES.items():
        fish_list = ", ".join(bundle_info["fish"])
        bonus = f"${bundle_info['bonus']:,}"
        rows.append((bundle_name, fish_list, bonus))

    return format_markdown_table(
        headers=("Bundle", "Fish", "Bonus"),
        rows=rows,
        right_aligned_columns={2},
    )


def build_prices_table() -> str:
    """Build a padded markdown table of fish prices with location."""
    rows = []
    for name, (price, stars, color) in PRICES.items():
        price_string = f"${price:,}"
        if stars == 0:
            star_display = "-"
        else:
            star_display = "x" * stars
            if color:
                star_display += f" {color}"
        location = get_location(price, stars, color)
        rows.append((name, price_string, star_display, location))

    return format_markdown_table(
        headers=("Fish", "Price", "Stars", "Location"),
        rows=rows,
        right_aligned_columns={1},
    )


def build_special_fish_section(region_counts: dict[str, Counter]) -> str:
    """Build the special fish section with auto-detected sightings."""
    special_fish = [
        (name, price, stars, color)
        for name, (price, stars, color) in PRICES.items()
        if stars >= 4 or stars == 0
    ]
    if not special_fish:
        return ""

    sightings: dict[str, list[str]] = {}
    for region_name, counts in region_counts.items():
        for fish_name in counts:
            if fish_name in PRICES:
                _price, star_count, _color = PRICES[fish_name]
                if star_count >= 4 or star_count == 0:
                    sightings.setdefault(fish_name, []).append(region_name)

    rows = []
    for name, price, stars, color in special_fish:
        price_string = f"${price:,}"
        if stars == 0:
            star_display = "-"
        else:
            star_display = "x" * stars
            if color:
                star_display += f" {color}"
        locations = sightings.get(name, [])
        note = SPECIAL_FISH_NOTES.get(name, "")
        if locations and note:
            sightings_string = ", ".join(
                f"{location} ({note})" for location in locations
            )
        elif locations:
            sightings_string = ", ".join(locations)
        else:
            sightings_string = ""
        rows.append((name, price_string, star_display, sightings_string))

    table = format_markdown_table(
        headers=("Fish", "Price", "Stars", "Sightings"),
        rows=rows,
        right_aligned_columns={1},
    )

    lines = [
        "## Special Fish",
        "",
        "Special fish (xxxx purple) are zone-independent"
        " \u2014 they can appear at any fishing location.",
        "Heavy storm weather may increase chances.",
        "",
        table,
    ]
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

    batches = log_path.read_text(encoding="utf-8").count("--sold")
    table = build_table(counts)
    content = f"# {region_name}\n\n{batches} batches sold\n\n{table}\n"
    md_path.write_text(content, encoding="utf-8")
    print(f"  {region_key}.md updated ({len(counts)} fish, {batches} batches)")


def _compute_bundle_contributions(
    region_data: dict[str, Counter],
) -> dict[str, list[tuple[str, float, bool]]]:
    """Compute per-fish bundle bonus for each location.

    For single-location bundles, uses the bottleneck probability approximation:
    bonus_per_fish = min(p_i) * bonus.

    For cross-location (multizone) bundles, each bundle fish is assigned to the
    location with the highest catch probability. The bonus per fish is then
    bonus / sum(1/p_i), distributed equally to all contributing locations.

    Uses tier-based detection: a bundle is considered if all its fish belong to
    unlocked locations. For fish not yet observed, probabilities are estimated
    from the location's tier distribution.

    Returns: {region_name: [(bundle_name, bonus_per_fish, is_estimated), ...]}.
    """
    unlocked = detect_unlocked_locations()
    contributions: dict[str, list[tuple[str, float, bool]]] = {}

    for bundle_name, bundle_info in BUNDLES.items():
        min_tier = bundle_min_tier(bundle_name)
        if min_tier is None or min_tier > len(unlocked):
            continue

        fish_assignments: list[tuple[str, str, float]] = []
        all_resolved = True
        any_estimated = False

        for fish in bundle_info["fish"]:
            home_location = fish_location(fish)
            best_location = None
            best_probability = 0.0

            for region_name, counts in region_data.items():
                if fish in counts:
                    total_fish = sum(counts.values())
                    probability = counts[fish] / total_fish
                    if probability > best_probability:
                        best_probability = probability
                        best_location = region_name

            if best_location is None:
                home_counts = region_data.get(home_location)
                if home_counts:
                    estimated = estimate_fish_probability(
                        fish, home_location, home_counts,
                    )
                    if estimated:
                        best_probability = estimated
                        best_location = home_location
                        any_estimated = True

            if best_location is None:
                all_resolved = False
                break

            fish_assignments.append((fish, best_location, best_probability))

        if not all_resolved:
            continue

        contributing_locations = {location for _, location, _ in fish_assignments}

        if len(contributing_locations) == 1:
            location = next(iter(contributing_locations))
            bottleneck_probability = min(p for _, _, p in fish_assignments)
            bonus_per_fish = bottleneck_probability * bundle_info["bonus"]
            contributions.setdefault(location, []).append(
                (bundle_name, bonus_per_fish, any_estimated)
            )
        else:
            fish_count = len(fish_assignments)
            bonus_per_slot = bundle_info["bonus"] / fish_count
            for _, location, probability in fish_assignments:
                bonus_per_fish = probability * bonus_per_slot
                contributions.setdefault(location, []).append(
                    (bundle_name, bonus_per_fish, any_estimated)
                )

    return contributions


def _compute_observed_sale_values(
    region_data: dict[str, Counter],
) -> dict[str, float]:
    """Compute observed $/fish (sales) for each location."""
    sale_values: dict[str, float] = {}
    for location, counts in region_data.items():
        total_fish = sum(counts.values())
        total_value = sum(
            counts[name] * PRICES[name][0]
            for name in counts
            if name in PRICES
        )
        sale_values[location] = total_value / total_fish
    return sale_values


def _compute_model_sale_value(region_name: str, counts: Counter) -> float:
    """Compute model-based $/fish (sales) for a single location.

    For each fish, uses the model probability instead of observed frequency.
    """
    model_value = 0.0

    for fish_name in counts:
        if fish_name not in PRICES:
            continue
        price = PRICES[fish_name][0]
        probability = model_fish_probability(fish_name, region_name, counts)
        if probability is not None:
            model_value += probability * price

    return model_value


def _compute_model_sale_values(
    region_data: dict[str, Counter],
) -> dict[str, float]:
    """Compute model-based $/fish (sales) for each location."""
    return {
        location: _compute_model_sale_value(location, counts)
        for location, counts in region_data.items()
    }


def _grid_search_optimal(
    locations: list[str],
    sale_values: dict[str, float],
    bundles: list[tuple[str, int, list[BundleFishAssignment]]],
    granularity: int = 100,
) -> tuple[float, dict[str, float]]:
    """Grid-search for the optimal allocation fractions.

    Returns (best_revenue, best_fractions).
    """
    best_revenue = -1.0
    best_fractions: dict[str, float] = {}

    if len(locations) == 2:
        for step_a in range(granularity + 1):
            fraction_a = step_a / granularity
            fraction_b = 1.0 - fraction_a
            fractions = {locations[0]: fraction_a, locations[1]: fraction_b}
            revenue = _compute_revenue(fractions, sale_values, bundles)
            if revenue > best_revenue:
                best_revenue = revenue
                best_fractions = fractions.copy()
    elif len(locations) == 3:
        for step_a in range(granularity + 1):
            fraction_a = step_a / granularity
            remaining = granularity - step_a
            for step_b in range(remaining + 1):
                fraction_b = step_b / granularity
                fraction_c = 1.0 - fraction_a - fraction_b
                fractions = {
                    locations[0]: fraction_a,
                    locations[1]: fraction_b,
                    locations[2]: fraction_c,
                }
                revenue = _compute_revenue(fractions, sale_values, bundles)
                if revenue > best_revenue:
                    best_revenue = revenue
                    best_fractions = fractions.copy()

    return best_revenue, best_fractions


def build_comparison_table() -> str:
    """Build a revenue comparison table using total fish frequencies."""
    region_data: dict[str, Counter] = {}
    for region_key, region_name in REGIONS.items():
        log_path = SALES_DIR / f"{region_key}-log.md"
        if not log_path.exists():
            continue
        counts = parse_log(log_path)
        if not counts:
            continue
        region_data[region_name] = counts

    if not region_data:
        return ""

    bundle_contributions = _compute_bundle_contributions(region_data)
    observed_sale_values = _compute_observed_sale_values(region_data)
    model_sale_values = _compute_model_sale_values(region_data)

    rows = []
    for region_key, region_name in REGIONS.items():
        if region_name not in region_data:
            continue

        counts = region_data[region_name]
        total_fish = sum(counts.values())

        observed_sale_per_fish = observed_sale_values[region_name]
        model_sale_per_fish = model_sale_values[region_name]

        location_bundles = bundle_contributions.get(region_name, [])
        bundle_value_per_fish = sum(bonus for _, bonus, _ in location_bundles)
        available_bundle_names = [
            f"{name}~" if estimated else name
            for name, _, estimated in location_bundles
        ]

        observed_total = observed_sale_per_fish + bundle_value_per_fish
        model_total = model_sale_per_fish + bundle_value_per_fish

        bundles_string = (
            ", ".join(available_bundle_names) if available_bundle_names
            else "none"
        )

        rows.append((
            region_name,
            str(total_fish),
            f"${observed_sale_per_fish:,.0f}",
            f"${model_sale_per_fish:,.0f}",
            bundles_string,
            f"${bundle_value_per_fish:,.0f}",
            f"${observed_total:,.0f}",
            f"**${model_total:,.0f}**",
            f"${model_total * fish_per_hour(region_name):,.0f}",
        ))

    if not rows:
        return ""

    return format_markdown_table(
        headers=(
            "Location", "Fish Caught",
            "$/Fish observed", "$/Fish model",
            "Available Bundles", "$/Fish (bundles)",
            "$/Fish total (obs)", "$/Fish total (model)",
            "$/Hour (model)",
        ),
        rows=rows,
        right_aligned_columns={1, 2, 3, 5, 6, 7, 8},
    )


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


class BundleFishAssignment(TypedDict):
    fish: str
    location: str
    probability: float
    estimated: bool


def _resolve_available_bundles(
    region_data: dict[str, Counter],
) -> list[tuple[str, int, list[BundleFishAssignment]]]:
    """Resolve all available bundles with fish-to-location assignments.

    Returns: [(bundle_name, bonus, [BundleFishAssignment, ...]), ...]
    """
    unlocked = detect_unlocked_locations()
    result = []

    for bundle_name, bundle_info in BUNDLES.items():
        min_tier = bundle_min_tier(bundle_name)
        if min_tier is None or min_tier > len(unlocked):
            continue

        assignments: list[BundleFishAssignment] = []
        all_resolved = True

        for fish in bundle_info["fish"]:
            home_location = fish_location(fish)
            best_location = None
            best_probability = 0.0
            is_estimated = False

            for region_name, counts in region_data.items():
                if fish in counts:
                    total_fish = sum(counts.values())
                    probability = counts[fish] / total_fish
                    if probability > best_probability:
                        best_probability = probability
                        best_location = region_name

            if best_location is None:
                home_counts = region_data.get(home_location)
                if home_counts:
                    estimated = estimate_fish_probability(
                        fish, home_location, home_counts,
                    )
                    if estimated:
                        best_probability = estimated
                        best_location = home_location
                        is_estimated = True

            if best_location is None:
                all_resolved = False
                break

            assignments.append({
                "fish": fish,
                "location": best_location,
                "probability": best_probability,
                "estimated": is_estimated,
            })

        if all_resolved:
            result.append((bundle_name, bundle_info["bonus"], assignments))

    return result


def _compute_revenue(
    fractions: dict[str, float],
    sale_values: dict[str, float],
    bundles: list[tuple[str, int, list[BundleFishAssignment]]],
) -> float:
    """Compute total $/hour for a given time allocation.

    revenue = r * Σ(f_i * sale_i) + Σ_bundles(min_j(f_loc(j) * r * p_j) * bonus)

    For single-location bundles, the min collapses to f_loc * r * min(p_j).
    """
    sale_revenue = sum(
        fish_per_hour(location) * fractions.get(location, 0) * sale_value
        for location, sale_value in sale_values.items()
    )

    bundle_revenue = 0.0
    for _, bonus, assignments in bundles:
        locations = {assignment["location"] for assignment in assignments}
        if len(locations) == 1:
            location = next(iter(locations))
            fraction = fractions.get(location, 0)
            bottleneck = min(a["probability"] for a in assignments)
            bundle_revenue += fraction * fish_per_hour(location) * bottleneck * bonus
        else:
            rates = [
                fractions.get(a["location"], 0) * fish_per_hour(a["location"]) * a["probability"]
                for a in assignments
            ]
            bundle_revenue += min(rates) * bonus

    return sale_revenue + bundle_revenue


def build_optimal_allocation(region_data: dict[str, Counter]) -> str:
    """Find the optimal time allocation across locations to maximize $/hour.

    Solves: max r·Σ(fᵢ·saleᵢ) + Σ_bundles(min_j(f_loc(j)·r·pⱼ)·bonus)
    subject to Σfᵢ = 1, fᵢ ≥ 0.

    Uses grid search over allocation fractions (1% granularity).
    """
    if len(region_data) < 2:
        return ""

    locations = [
        name for name in LOCATION_ORDER if name in region_data
    ]
    if len(locations) < 2:
        return ""

    sale_values = _compute_observed_sale_values(region_data)
    model_sale_values = _compute_model_sale_values(region_data)

    bundles = _resolve_available_bundles(region_data)

    has_cross_location = any(
        len({a["location"] for a in assignments}) > 1
        for _, _, assignments in bundles
    )
    if not has_cross_location:
        return ""

    any_estimated = any(
        any(a["estimated"] for a in assignments)
        for _, _, assignments in bundles
    )

    # Grid search with 1% granularity
    granularity = 100
    best_revenue, best_fractions = _grid_search_optimal(
        locations, sale_values, bundles, granularity,
    )
    if not best_fractions:
        return ""

    baseline_revenues: dict[str, float] = {}
    model_baseline_revenues: dict[str, float] = {}
    for location in locations:
        solo = {loc: (1.0 if loc == location else 0.0) for loc in locations}
        baseline_revenues[location] = _compute_revenue(
            solo, sale_values, bundles,
        )
        model_baseline_revenues[location] = _compute_revenue(
            solo, model_sale_values, bundles,
        )

    # Optimize using model sale values
    model_best_revenue, model_best_fractions = _grid_search_optimal(
        locations, model_sale_values, bundles, granularity,
    )

    lines = ["## Optimal Allocation"]
    if any_estimated:
        lines.append("")
        lines.append("Note: some bundle fish probabilities are estimated (~).")
    lines.append("")
    lines.append(
        "Optimal time split across locations to maximize total $/hour"
        " (considering both sale value and cross-location bundle completions):"
    )
    lines.append("")

    allocation_rows = []
    for location in locations:
        observed_fraction = best_fractions.get(location, 0)
        model_fraction = model_best_fractions.get(location, 0)
        allocation_rows.append((
            location,
            f"{observed_fraction:.0%}",
            f"${sale_values[location]:,.0f}",
            f"${baseline_revenues[location]:,.0f}",
            f"{model_fraction:.0%}",
            f"${model_sale_values[location]:,.0f}",
            f"${model_baseline_revenues[location]:,.0f}",
        ))
    allocation_rows.append((
        "**Combined**",
        "100%",
        "",
        f"**${best_revenue:,.0f}**",
        "100%",
        "",
        f"**${model_best_revenue:,.0f}**",
    ))

    lines.append(format_markdown_table(
        headers=(
            "Location",
            "Time % (obs)", "$/Fish (obs)", "$/Hour (obs)",
            "Time % (model)", "$/Fish (model)", "$/Hour (model)",
        ),
        rows=allocation_rows,
        right_aligned_columns={1, 2, 3, 4, 5, 6},
    ))

    best_solo = max(baseline_revenues.values())
    model_best_solo = max(model_baseline_revenues.values())
    uplift = best_revenue - best_solo
    uplift_percentage = (uplift / best_solo) * 100 if best_solo > 0 else 0
    model_uplift = model_best_revenue - model_best_solo
    model_uplift_percentage = (
        (model_uplift / model_best_solo) * 100 if model_best_solo > 0 else 0
    )
    lines.append("")
    lines.append(
        f"**Observed:** splitting yields"
        f" **${best_revenue:,.0f}**/hour vs"
        f" **${best_solo:,.0f}**/hour best solo"
        f" (+${uplift:,.0f}/hour, +{uplift_percentage:.1f}%)."
    )
    lines.append(
        f"**Model:** splitting yields"
        f" **${model_best_revenue:,.0f}**/hour vs"
        f" **${model_best_solo:,.0f}**/hour best solo"
        f" (+${model_uplift:,.0f}/hour, +{model_uplift_percentage:.1f}%)."
    )

    return "\n".join(lines)


def build_bundle_details(region_counts: dict[str, Counter]) -> str:
    """Build a bundle details section showing expected fish per bundle completion."""
    sections = []

    bundle_detail_headers = (
        "Bundle", "Fish", "Bonus",
        "Avg Fish to Complete", "Avg Time", "Bonus/Fish", "Catch Rates",
    )
    bundle_detail_right_columns = {2, 3, 4, 5}

    # Single-location bundles (per region)
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
                expected_time_seconds = expected_fish * seconds_per_fish(region_name)
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

        table = format_markdown_table(
            headers=bundle_detail_headers,
            rows=bundle_rows,
            right_aligned_columns=bundle_detail_right_columns,
        )
        sections.append(f"### {region_name}\n\n{table}")

    # Cross-location bundles (tier-aware with estimation)
    unlocked = detect_unlocked_locations()
    cross_location_rows = []
    for bundle_name, bundle_info in BUNDLES.items():
        min_tier = bundle_min_tier(bundle_name)
        if min_tier is None or min_tier > len(unlocked):
            continue

        fish_assignments: list[tuple[str, str, float, str]] = []
        all_resolved = True
        for fish in bundle_info["fish"]:
            home_location = fish_location(fish)
            best_location = None
            best_probability = 0.0
            best_count = 0
            best_total = 0

            for region_name, counts in region_counts.items():
                if fish in counts:
                    total_fish = sum(counts.values())
                    probability = counts[fish] / total_fish
                    if probability > best_probability:
                        best_probability = probability
                        best_location = region_name
                        best_count = counts[fish]
                        best_total = total_fish

            if best_location is not None:
                detail = (
                    f"{fish} @ {best_location}:"
                    f" {best_count}/{best_total} ({best_probability:.1%})"
                )
            else:
                home_counts = region_counts.get(home_location)
                if home_counts:
                    estimated = estimate_fish_probability(
                        fish, home_location, home_counts,
                    )
                    if estimated:
                        best_probability = estimated
                        best_location = home_location
                        detail = (
                            f"{fish} @ {home_location}: ~{estimated:.1%} (est.)"
                        )

            if best_location is None:
                all_resolved = False
                break
            fish_assignments.append(
                (fish, best_location, best_probability, detail)
            )

        if not all_resolved:
            continue

        contributing_locations = {
            location for _, location, _, _ in fish_assignments
        }
        if len(contributing_locations) <= 1:
            continue

        total_expected_fish = sum(
            1.0 / p for _, _, p, _ in fish_assignments
        )
        expected_time_seconds = sum(
            (1.0 / p) * seconds_per_fish(location)
            for _, location, p, _ in fish_assignments
        )
        expected_time_minutes = expected_time_seconds / 60
        bonus_per_fish = bundle_info["bonus"] / total_expected_fish
        fish_details = [detail for _, _, _, detail in fish_assignments]
        cross_location_rows.append((
            bundle_name,
            ", ".join(bundle_info["fish"]),
            f"${bundle_info['bonus']:,}",
            f"{total_expected_fish:.0f}",
            f"{expected_time_minutes:.0f} min",
            f"${bonus_per_fish:,.0f}",
            " \\| ".join(fish_details),
        ))

    if cross_location_rows:
        table = format_markdown_table(
            headers=bundle_detail_headers,
            rows=cross_location_rows,
            right_aligned_columns=bundle_detail_right_columns,
        )
        sections.append(f"### Cross-Location\n\n{table}")

    if not sections:
        return ""
    return "## Bundle Details\n\n" + "\n\n".join(sections)


def build_drop_rate_analysis(region_counts: dict[str, Counter]) -> str:
    """Build drop rate analysis: tier distribution and within-tier weight fitting."""
    if not region_counts:
        return ""

    sections: list[str] = ["## Drop Rate Analysis"]

    # --- Tier Distribution ---
    tier_data: dict[str, dict[int, tuple[int, int]]] = {}
    for region_name, counts in region_counts.items():
        total = sum(counts.values())
        tier_totals: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}
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

    has_specials = any(
        tier_data[region_name][4][0] > 0 for region_name in region_names
    )
    tier_levels = [4, 3, 2, 1] if has_specials else [3, 2, 1]

    tier_rows: list[tuple[str, ...]] = []
    for stars in tier_levels:
        star_label = "x" * stars
        if stars == 4:
            star_label += " purple"
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

    tier_table = format_markdown_table(
        headers=tier_headers,
        rows=tier_rows,
        right_aligned_columns=set(range(1, len(tier_headers))),
    )

    sections.extend([
        "",
        "### Tier Distribution",
        "",
        "Tier drop rates are consistent across locations,"
        " suggesting a fixed game mechanic:",
        "",
        tier_table,
    ])

    # --- Within-Tier Weights ---
    sections.extend([
        "",
        "### Within-Tier Weights",
        "",
        "Observed frequencies vs model (percentage template) per fish.",
        "Model uses shared percentage templates across all locations"
        " (5% granularity).",
    ])

    for region_name, counts in region_counts.items():
        tiers: dict[int, list[tuple[str, int]]] = {1: [], 2: [], 3: [], 4: []}
        for fish_name, fish_count in counts.items():
            if fish_name in PRICES:
                _price, star_count, _color = PRICES[fish_name]
                if star_count in tiers:
                    tiers[star_count].append((fish_name, fish_count))

        for stars in [4, 3, 2, 1]:
            fish_in_tier = tiers[stars]
            if len(fish_in_tier) < 2:
                continue

            fish_in_tier.sort(key=lambda pair: -pair[1])
            observed = [count for _name, count in fish_in_tier]
            tier_total = sum(observed)

            weights, weight_chi_squared, weight_p = fit_integer_weights(observed)
            weight_sum = sum(weights)

            template = TIER_DROP_PERCENTAGES.get(stars)
            if template:
                percentages, template_chi_squared, template_p = (
                    fit_percentage_template(observed, template)
                )
                percentage_sum = sum(percentages)
            else:
                percentages = None

            star_label = "x" * stars
            sections.extend([
                "",
                f"#### {region_name} \u2014 {star_label}"
                f" ({len(fish_in_tier)} fish, {tier_total} observed)",
                "",
            ])

            weight_rows: list[tuple[str, ...]] = []
            for i, (name, count) in enumerate(fish_in_tier):
                observed_percentage = count / tier_total * 100
                weight_expected = weights[i] / weight_sum * 100
                expected_count = tier_total * weights[i] / weight_sum
                residual = count - expected_count

                if percentages:
                    model_percentage = percentages[i] / percentage_sum * 100
                    model_expected_count = tier_total * percentages[i] / percentage_sum
                    model_residual = count - model_expected_count
                    weight_rows.append((
                        name,
                        str(count),
                        f"{observed_percentage:.1f}%",
                        str(weights[i]),
                        f"{weight_expected:.1f}%",
                        f"{percentages[i]}%",
                        f"{model_percentage:.1f}%",
                        f"{model_residual:+.1f}",
                    ))
                else:
                    weight_rows.append((
                        name,
                        str(count),
                        f"{observed_percentage:.1f}%",
                        str(weights[i]),
                        f"{weight_expected:.1f}%",
                        "",
                        "",
                        f"{residual:+.1f}",
                    ))

            if percentages:
                headers = (
                    "Fish", "Count", "Observed %",
                    "Weight", "Weight %",
                    "Model %", "Model % (norm)", "Residual",
                )
            else:
                headers = (
                    "Fish", "Count", "Observed %",
                    "Weight", "Weight %",
                    "Model %", "Model % (norm)", "Residual",
                )

            weight_table = format_markdown_table(
                headers=headers,
                rows=weight_rows,
                right_aligned_columns={1, 2, 3, 4, 5, 6, 7},
            )
            sections.append(weight_table)

            weight_quality = (
                "excellent" if weight_p > 0.5
                else "good" if weight_p > 0.1
                else "acceptable" if weight_p > 0.05
                else "poor"
            )
            sections.extend([
                "",
                f"Weight fit: \u03c7\u00b2 = {weight_chi_squared:.2f},"
                f" df = {len(fish_in_tier) - 1},"
                f" p = {weight_p:.3f}"
                f" \u2014 {weight_quality}",
            ])

            if percentages:
                template_quality = (
                    "excellent" if template_p > 0.5
                    else "good" if template_p > 0.1
                    else "acceptable" if template_p > 0.05
                    else "poor"
                )
                template_display = "/".join(
                    f"{percentage}%" for percentage in template
                )
                sections.append(
                    f"Model fit ({template_display}):"
                    f" \u03c7\u00b2 = {template_chi_squared:.2f},"
                    f" p = {template_p:.3f}"
                    f" \u2014 {template_quality}",
                )

    return "\n".join(sections)


def main() -> None:
    for key, name in REGIONS.items():
        update_md(key, name)

    # Collect region counts (used by prices.md and comparison.md)
    region_counts: dict[str, Counter] = {}
    for region_key, region_name in REGIONS.items():
        log_path = SALES_DIR / f"{region_key}-log.md"
        if log_path.exists():
            counts = parse_log(log_path)
            if counts:
                region_counts[region_name] = counts

    # Write bundles.md
    bundles_md = SALES_DIR / "bundles.md"
    table = build_bundles_table()
    bundles_md.write_text(f"# Bundles\n\n{table}\n", encoding="utf-8")
    print(f"  bundles.md updated ({len(BUNDLES)} bundles)")

    # Write prices.md
    prices_md = SALES_DIR / "prices.md"
    prices_header = """# Fish Prices

## Pricing Tiers

| Location     | x      | xx     | xxx    |
|--------------|-------:|-------:|-------:|"""
    for location, tiers in TIER_PRICES.items():
        prices_header += f"\n| {location:<12} | ${tiers[1]:,} | ${tiers[2]:,} | ${tiers[3]:,} |"
    prices_header += (
        "\n\nGreen stars (x green) = Humane Labs tier."
        " Special fish have fixed prices.\n\n"
    )
    special_section = build_special_fish_section(region_counts)
    if special_section:
        prices_header += special_section + "\n\n"
    prices_header += "## All Fish\n\n"
    table = build_prices_table()
    prices_md.write_text(prices_header + table + "\n", encoding="utf-8")
    print(f"  prices.md updated ({len(PRICES)} fish)")

    # Write comparison.md
    comparison_table = build_comparison_table()
    if comparison_table:
        unlocked = detect_unlocked_locations()
        tier_note = (
            f"Detected tier: {len(unlocked)}"
            f" ({', '.join(unlocked)})."
        )
        bundle_details = build_bundle_details(region_counts)
        drop_rate_analysis = build_drop_rate_analysis(region_counts)
        bite_details = ", ".join(
            f"{loc} {SECONDS_WAITING_FOR_BITE[loc]}s"
            for loc in unlocked if loc in SECONDS_WAITING_FOR_BITE
        )
        reel_details = ", ".join(
            f"{loc} {SECONDS_REELING_IN.get(loc, SECONDS_REELING_IN_DEFAULT)}s"
            for loc in unlocked
        )
        time_note = (
            f"Bite wait by location: {bite_details}."
            f" Reel-in by location: {reel_details}."
        )
        estimated_note = "~ = estimated (not yet observed in catch data)"
        content = (
            f"# Location Comparison\n\n{tier_note}\n\n{time_note}\n\n"
            f"{estimated_note}\n\n{comparison_table}\n"
        )
        optimal_allocation = build_optimal_allocation(region_counts)
        if optimal_allocation:
            content += f"\n{optimal_allocation}\n"
        if bundle_details:
            content += f"\n{bundle_details}\n"
        if drop_rate_analysis:
            content += f"\n{drop_rate_analysis}\n"

        comparison_md = SALES_DIR / "comparison.md"
        comparison_md.write_text(content, encoding="utf-8")
        print(f"  comparison.md updated (tier {len(unlocked)})")

    # Generate visualizations
    from visualize_allocation import main as generate_visualizations
    generate_visualizations()


if __name__ == "__main__":
    main()
