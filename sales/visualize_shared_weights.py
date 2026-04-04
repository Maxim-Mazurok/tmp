"""Experiment: test whether fish within each star tier share a universal weight
template across all locations.

For each tier, collects observed counts per-location, then tries all possible
weight vectors and computes a joint χ² (sum of per-location χ² values).
Compares joint fit vs independent fits.
"""

import math
import sys
from collections import Counter
from itertools import product
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from sales.stats import chi_squared_p_value, fit_integer_weights
from sales.update_sales import PRICES, REGIONS, SALES_DIR, parse_log


def collect_tier_data() -> dict[int, list[tuple[str, list[tuple[str, int]]]]]:
    """Collect fish counts per tier per location.

    Returns: {stars: [(region_name, [(fish_name, count), ...]), ...]}
    """
    tier_data: dict[int, list[tuple[str, list[tuple[str, int]]]]] = {
        1: [], 2: [], 3: [],
    }

    for region_key, region_name in REGIONS.items():
        log_path = SALES_DIR / f"{region_key}-log.md"
        if not log_path.exists():
            continue
        counts = parse_log(log_path)
        if not counts:
            continue

        tiers: dict[int, list[tuple[str, int]]] = {1: [], 2: [], 3: []}
        for fish_name, fish_count in counts.items():
            if fish_name in PRICES:
                _, star_count, _ = PRICES[fish_name]
                if star_count in tiers:
                    tiers[star_count].append((fish_name, fish_count))

        for stars, fish_list in tiers.items():
            if len(fish_list) >= 2:
                fish_list.sort(key=lambda pair: -pair[1])
                tier_data[stars].append((region_name, fish_list))

    return tier_data


def compute_chi_squared(
    observed: list[int],
    weights: list[int],
) -> tuple[float, float]:
    """Compute χ² and p-value for given observed counts and weights."""
    total = sum(observed)
    weight_sum = sum(weights)
    degrees_of_freedom = len(observed) - 1
    if degrees_of_freedom <= 0:
        return 0.0, 1.0

    expected = [total * weight / weight_sum for weight in weights]
    chi_squared = sum(
        (observed[i] - expected[i]) ** 2 / expected[i]
        for i in range(len(observed))
    )
    p_value = chi_squared_p_value(chi_squared, degrees_of_freedom)
    return chi_squared, p_value


def try_shared_weights(
    locations_data: list[tuple[str, list[tuple[str, int]]]],
    max_weight: int = 10,
) -> list[dict]:
    """Try all weight vectors and compute joint fit across locations.

    For each candidate weight vector, assigns weights to fish sorted by
    descending count (highest count gets highest weight).

    Locations with fewer fish than the max are assumed to have extra fish
    at the lowest weight (the last/smallest weight in the vector). Their
    observed counts stay as-is but the weight vector is truncated to match.
    """
    if len(locations_data) < 2:
        return []

    matching_locations = locations_data
    fish_count = max(len(fish_list) for _, fish_list in matching_locations)

    candidates = []

    def generate_weights(
        position: int,
        max_allowed: int,
        current: list[int],
    ) -> None:
        if position == fish_count:
            weights = list(current)
            common = math.gcd(*weights)
            simplified = tuple(weight // common for weight in weights)

            # Compute joint chi-squared across all locations
            total_chi_squared = 0.0
            total_degrees = 0
            per_location = []

            for region_name, fish_list in matching_locations:
                observed = [count for _, count in fish_list]
                location_fish_count = len(observed)
                # Use the first location_fish_count weights for this location
                location_weights = list(simplified[:location_fish_count])
                chi2, p_value = compute_chi_squared(observed, location_weights)
                total_chi_squared += chi2
                total_degrees += location_fish_count - 1
                per_location.append({
                    "region": region_name,
                    "chi_squared": chi2,
                    "p_value": p_value,
                    "fish_count": location_fish_count,
                })

            joint_p = chi_squared_p_value(total_chi_squared, total_degrees)
            distinct = len(set(simplified))

            candidates.append({
                "weights": simplified,
                "joint_chi_squared": total_chi_squared,
                "joint_p_value": joint_p,
                "joint_degrees": total_degrees,
                "per_location": per_location,
                "distinct_weights": distinct,
                "complexity": distinct - 1,
                "score": total_chi_squared + 2 * (distinct - 1),
                "passes": joint_p > 0.05,
            })
            return

        for weight in range(1, max_allowed + 1):
            generate_weights(position + 1, weight, current + [weight])

    generate_weights(0, max_weight, [])

    # Deduplicate by simplified weights
    seen = set()
    unique = []
    for candidate in candidates:
        key = candidate["weights"]
        if key not in seen:
            seen.add(key)
            unique.append(candidate)

    return unique, matching_locations


def main() -> None:
    tier_data = collect_tier_data()

    star_labels = {3: "★★★", 2: "★★", 1: "★"}

    figure = plt.figure(figsize=(18, 14))
    outer_grid = gridspec.GridSpec(3, 1, figure=figure, hspace=0.4)

    for tier_index, stars in enumerate([3, 2, 1]):
        locations_data = tier_data[stars]
        if len(locations_data) < 2:
            continue

        result = try_shared_weights(locations_data)
        if not result:
            continue
        candidates, matching_locations = result

        location_names = [name for name, _ in matching_locations]
        fish_counts = [len(fish_list) for _, fish_list in matching_locations]
        max_fish_count = max(fish_counts)

        # Get independent fits for comparison
        independent_fits = []
        for region_name, fish_list in matching_locations:
            observed = [count for _, count in fish_list]
            weights, chi2, p_value = fit_integer_weights(observed)
            independent_fits.append({
                "region": region_name,
                "weights": tuple(weights),
                "chi_squared": chi2,
                "p_value": p_value,
            })

        independent_total_chi2 = sum(f["chi_squared"] for f in independent_fits)
        independent_total_degrees = sum(
            len(fish_list) - 1 for _, fish_list in matching_locations
        )
        independent_joint_p = chi_squared_p_value(
            independent_total_chi2, independent_total_degrees,
        )

        # Best shared fit
        passing = [candidate for candidate in candidates if candidate["passes"]]
        if passing:
            passing.sort(key=lambda candidate: (
                candidate["score"], candidate["joint_chi_squared"],
            ))
            best_shared = passing[0]
        else:
            candidates.sort(key=lambda candidate: candidate["joint_chi_squared"])
            best_shared = candidates[0]

        # Create subplot row: landscape + comparison table
        inner_grid = gridspec.GridSpecFromSubplotSpec(
            1, 2, subplot_spec=outer_grid[tier_index],
            width_ratios=[2, 1], wspace=0.3,
        )

        # Left: landscape plot
        axis = figure.add_subplot(inner_grid[0])

        passing_candidates = [c for c in candidates if c["passes"]]
        failing_candidates = [c for c in candidates if not c["passes"]]

        if passing_candidates:
            max_complexity = max(c["complexity"] for c in passing_candidates)
            max_chi = max(c["joint_chi_squared"] for c in passing_candidates)
            y_margin = max(max_chi * 0.05, 0.1)
            axis.set_xlim(-0.5, max_complexity + 1)
            axis.set_ylim(-y_margin, max_chi + y_margin * 3)

        if failing_candidates:
            axis.scatter(
                [c["complexity"] for c in failing_candidates],
                [c["joint_chi_squared"] for c in failing_candidates],
                c="lightgray", s=15, alpha=0.3, label="p ≤ 0.05",
                zorder=1, clip_on=True,
            )

        if passing_candidates:
            p_values = [c["joint_p_value"] for c in passing_candidates]
            scatter = axis.scatter(
                [c["complexity"] for c in passing_candidates],
                [c["joint_chi_squared"] for c in passing_candidates],
                c=p_values, cmap="RdYlGn", vmin=0.05, vmax=1.0,
                s=40, alpha=0.8, label="p > 0.05",
                edgecolors="black", linewidths=0.5, zorder=2,
            )
            plt.colorbar(scatter, ax=axis, label="joint p-value", shrink=0.8)

        axis.scatter(
            [best_shared["complexity"]],
            [best_shared["joint_chi_squared"]],
            c="none", s=200, edgecolors="red", linewidths=2.5,
            marker="D", zorder=3,
            label=f"Best shared: {best_shared['weights']}",
        )

        # Annotate top 5
        top_passing = sorted(
            passing_candidates,
            key=lambda c: (c["score"], c["joint_chi_squared"]),
        )
        for i, candidate in enumerate(top_passing[:5]):
            weight_label = str(candidate["weights"])
            if len(weight_label) > 30:
                weight_label = weight_label[:27] + "..."
            axis.annotate(
                f"{weight_label}\n"
                f"joint χ²={candidate['joint_chi_squared']:.2f},"
                f" p={candidate['joint_p_value']:.3f}",
                xy=(candidate["complexity"], candidate["joint_chi_squared"]),
                xytext=(10, 10 + i * 18),
                textcoords="offset points", fontsize=6,
                arrowprops={"arrowstyle": "->", "color": "gray", "lw": 0.5},
            )

        tier_label = star_labels[stars]
        region_note = ", ".join(location_names)
        if len(set(fish_counts)) == 1:
            count_note = f"{fish_counts[0]} fish each"
        else:
            count_note = "/".join(str(c) for c in fish_counts) + " fish"
        axis.set_title(
            f"{tier_label} — Joint fit across {len(matching_locations)} locations"
            f" ({count_note})\n({region_note})",
            fontsize=10,
        )
        axis.set_xlabel("Complexity: distinct values - 1")
        axis.set_ylabel("Joint χ² (sum across locations)")
        axis.legend(fontsize=7, loc="upper right")

        # Right: comparison text
        text_axis = figure.add_subplot(inner_grid[1])
        text_axis.axis("off")

        comparison_lines = [f"{tier_label} Tier Comparison\n"]
        comparison_lines.append("Independent fits (per location):")
        for fit_info in independent_fits:
            comparison_lines.append(
                f"  {fit_info['region']}: {fit_info['weights']}"
                f"  χ²={fit_info['chi_squared']:.2f}  p={fit_info['p_value']:.3f}"
            )
        comparison_lines.append(
            f"  Joint:  χ²={independent_total_chi2:.2f}"
            f"  p={independent_joint_p:.3f}"
        )
        comparison_lines.append("")
        comparison_lines.append(
            f"Best shared: {best_shared['weights']}"
        )
        for location_info in best_shared["per_location"]:
            comparison_lines.append(
                f"  {location_info['region']}:"
                f"  χ²={location_info['chi_squared']:.2f}"
                f"  p={location_info['p_value']:.3f}"
            )
        comparison_lines.append(
            f"  Joint:  χ²={best_shared['joint_chi_squared']:.2f}"
            f"  p={best_shared['joint_p_value']:.3f}"
        )
        comparison_lines.append("")

        chi2_penalty = best_shared["joint_chi_squared"] - independent_total_chi2
        comparison_lines.append(
            f"χ² cost of sharing: +{chi2_penalty:.2f}"
        )
        if best_shared["passes"]:
            comparison_lines.append("✓ Shared weights are plausible")
        else:
            comparison_lines.append("✗ Shared weights rejected (p ≤ 0.05)")

        # Show per-location fish with shared weights
        comparison_lines.append("")
        comparison_lines.append("Fish assignments with shared weights:")
        for region_name, fish_list in matching_locations:
            location_fish_count = len(fish_list)
            location_weights = best_shared["weights"][:location_fish_count]
            comparison_lines.append(f"  {region_name} ({location_fish_count} fish):")
            total = sum(count for _, count in fish_list)
            weight_sum = sum(location_weights)
            for i, (fish_name, count) in enumerate(fish_list):
                weight = location_weights[i]
                expected_percentage = weight / weight_sum * 100
                observed_percentage = count / total * 100
                comparison_lines.append(
                    f"    w={weight} {fish_name}:"
                    f" {observed_percentage:.0f}% (exp {expected_percentage:.0f}%)"
                )
            if location_fish_count < len(best_shared["weights"]):
                extra = len(best_shared["weights"]) - location_fish_count
                lowest_weight = best_shared["weights"][-1]
                comparison_lines.append(
                    f"    (+ {extra} assumed fish at w={lowest_weight})"
                )

        text_axis.text(
            0.05, 0.95, "\n".join(comparison_lines),
            transform=text_axis.transAxes,
            fontsize=8, fontfamily="monospace",
            verticalalignment="top",
        )

    figure.suptitle(
        "Experiment: Shared Weight Templates Across Locations\n"
        "Can the same weight vector explain all locations within each tier?",
        fontsize=13, fontweight="bold",
    )

    output_path = SALES_DIR / "shared_weights_experiment.png"
    figure.savefig(output_path, dpi=100, bbox_inches="tight")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
