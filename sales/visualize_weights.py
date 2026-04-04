"""Visualize the weight-fitting landscape for fish drop rate analysis.

For each location/tier, shows all candidate weight vectors with their χ² and
p-values, highlighting the selected fit and near-optimal alternatives.
"""

import math
import sys
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from sales.stats import chi_squared_p_value
from sales.update_sales import PRICES, REGIONS, SALES_DIR, parse_log


def get_all_candidates(
    observed_counts: list[int],
    max_weight: int = 10,
) -> list[dict]:
    """Get all candidate weight vectors with their fit statistics."""
    fish_count = len(observed_counts)
    total = sum(observed_counts)
    degrees_of_freedom = fish_count - 1

    indexed = sorted(enumerate(observed_counts), key=lambda pair: -pair[1])
    groups: list[tuple[int, list[int]]] = []
    for original_index, count in indexed:
        if groups and count == groups[-1][0]:
            groups[-1][1].append(original_index)
        else:
            groups.append((count, [original_index]))

    group_count = len(groups)
    group_sizes = [len(indices) for _, indices in groups]
    candidates: list[dict] = []

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
            p_value = chi_squared_p_value(chi_squared, degrees_of_freedom)
            distinct_weights = len(set(weights))
            common = math.gcd(*weights)
            simplified = tuple(weight // common for weight in weights)

            max_weight_value = max(simplified)
            complexity = distinct_weights - 1
            score = chi_squared + 2 * complexity
            candidates.append({
                "weights": simplified,
                "total_weight": total_weight // common,
                "complexity": complexity,
                "chi_squared": chi_squared,
                "p_value": p_value,
                "score": score,
                "distinct_weights": distinct_weights,
                "max_weight": max_weight_value,
                "passes": p_value > 0.05,
            })
            return

        for weight in range(1, max_allowed + 1):
            search(group_index + 1, weight, current_group_weights + [weight])

    search(0, max_weight, [])

    # Deduplicate by simplified weights
    seen = set()
    unique = []
    for candidate in candidates:
        key = candidate["weights"]
        if key not in seen:
            seen.add(key)
            unique.append(candidate)

    return unique


def plot_tier_landscape(
    region_name: str,
    stars: int,
    fish_names: list[str],
    observed_counts: list[int],
    axis: plt.Axes,
) -> None:
    """Plot the weight-fitting landscape for a single tier."""
    candidates = get_all_candidates(observed_counts)
    if not candidates:
        return

    passing = [candidate for candidate in candidates if candidate["passes"]]
    if not passing:
        return
    passing.sort(key=lambda candidate: (candidate["score"], candidate["total_weight"]))
    best = passing[0]

    failing = [candidate for candidate in candidates if not candidate["passes"]]

    # Set axis limits to fit passing candidates, letting grey overflow
    if passing:
        max_complexity = max(candidate["complexity"] for candidate in passing)
        max_chi = max(candidate["chi_squared"] for candidate in passing)
        axis.set_xlim(-0.5, max_complexity + 1)
        y_margin = max(max_chi * 0.05, 0.1)
        axis.set_ylim(-y_margin, max_chi + y_margin * 3)

    # Plot failing candidates (may be clipped)
    if failing:
        axis.scatter(
            [candidate["complexity"] for candidate in failing],
            [candidate["chi_squared"] for candidate in failing],
            c="lightgray",
            s=15,
            alpha=0.3,
            label="p ≤ 0.05",
            zorder=1,
            clip_on=True,
        )

    # Plot passing candidates colored by p-value
    if passing:
        p_values = [candidate["p_value"] for candidate in passing]
        scatter = axis.scatter(
            [candidate["complexity"] for candidate in passing],
            [candidate["chi_squared"] for candidate in passing],
            c=p_values,
            cmap="RdYlGn",
            vmin=0.05,
            vmax=1.0,
            s=40,
            alpha=0.8,
            label="p > 0.05",
            edgecolors="black",
            linewidths=0.5,
            zorder=2,
        )
        plt.colorbar(scatter, ax=axis, label="p-value", shrink=0.8)

    # Highlight the selected best
    axis.scatter(
        [best["complexity"]],
        [best["chi_squared"]],
        c="none",
        s=200,
        edgecolors="red",
        linewidths=2.5,
        marker="D",
        zorder=3,
        label=f"Selected: {best['weights']}",
    )

    # Annotate top 5 passing candidates (sorted by score)
    passing_sorted = sorted(passing, key=lambda c: (c["score"], c["total_weight"]))
    for i, candidate in enumerate(passing_sorted[:5]):
        weight_label = str(candidate["weights"])
        if len(weight_label) > 30:
            weight_label = weight_label[:27] + "..."
        distinct = candidate["distinct_weights"]
        max_weight = candidate["max_weight"]
        axis.annotate(
            f"{weight_label}\n"
            f"χ²={candidate['chi_squared']:.2f}, p={candidate['p_value']:.3f}\n"
            f"d={distinct}, max={max_weight}",
            xy=(candidate["complexity"], candidate["chi_squared"]),
            xytext=(10, 10 + i * 18),
            textcoords="offset points",
            fontsize=6,
            arrowprops={"arrowstyle": "->", "color": "gray", "lw": 0.5},
        )

    star_label = "★" * stars
    tier_total = sum(observed_counts)
    axis.set_title(
        f"{region_name} — {star_label}"
        f" ({len(fish_names)} fish, {tier_total} obs)",
        fontsize=10,
    )
    axis.set_xlabel("Complexity: distinct values - 1")
    axis.set_ylabel("χ² statistic (lower = better fit)")
    axis.legend(fontsize=7, loc="upper right")


def main() -> None:
    # Collect all tiers with enough data
    panels: list[tuple[str, int, list[str], list[int]]] = []

    for region_key, region_name in REGIONS.items():
        log_path = SALES_DIR / f"{region_key}-log.md"
        if not log_path.exists():
            continue
        counts = parse_log(log_path)
        if not counts:
            continue

        tiers: dict[int, list[tuple[str, int]]] = {1: [], 2: [], 3: [], 4: []}
        for fish_name, fish_count in counts.items():
            if fish_name in PRICES:
                _price, star_count, _color = PRICES[fish_name]
                if star_count in tiers:
                    tiers[star_count].append((fish_name, fish_count))

        for star_count in [3, 2, 1]:
            fish_in_tier = tiers[star_count]
            if len(fish_in_tier) < 2:
                continue
            fish_in_tier.sort(key=lambda pair: -pair[1])
            names = [name for name, _ in fish_in_tier]
            observed = [count for _, count in fish_in_tier]
            panels.append((region_name, star_count, names, observed))

    if not panels:
        print("No tiers with enough data to visualize.")
        return

    columns = min(3, len(panels))
    rows = math.ceil(len(panels) / columns)
    figure, axes = plt.subplots(
        rows, columns,
        figsize=(7 * columns, 5 * rows),
        squeeze=False,
    )

    for index, (region_name, stars, names, observed) in enumerate(panels):
        row = index // columns
        column = index % columns
        plot_tier_landscape(region_name, stars, names, observed, axes[row][column])

    # Hide unused subplots
    for index in range(len(panels), rows * columns):
        row = index // columns
        column = index % columns
        axes[row][column].set_visible(False)

    figure.suptitle(
        "Weight-Fitting Landscape: χ² vs Complexity\n"
        "Each dot is a candidate weight vector. Green = good fit, red = marginal.",
        fontsize=12,
        fontweight="bold",
    )
    figure.tight_layout()
    output_path = SALES_DIR / "weight_landscape.png"
    figure.savefig(output_path, dpi=100, bbox_inches="tight")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
