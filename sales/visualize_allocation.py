"""Visualize the fishing allocation optimization problem.

Generates figures showing:
1. Ternary heatmap of total $/hour across all allocations
2. Revenue decomposition: sales vs bundles along the optimal path
3. Bundle fill-rate bottleneck illustration
4. Competing forces: sales value vs bundle completions
5. min() envelope anatomy — rate lines and kink points per bundle
6. Full piecewise-linear objective decomposition (zoomed stacked)
7. Individual components (unstacked, own scales)
"""

from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

from constants import (
    BUNDLES,
    PRICES,
    REGIONS,
    SALES_DIR,
    fish_per_hour,
)
from parsing import parse_log
from update_sales import (
    BundleFishAssignment,
    _compute_revenue,
    _resolve_available_bundles,
)

OUTPUT_DIRECTORY = SALES_DIR / "figures"
OUTPUT_DIRECTORY.mkdir(exist_ok=True)


def _load_region_data() -> dict[str, Counter]:
    region_data: dict[str, Counter] = {}
    for region_key, region_name in REGIONS.items():
        log_path = SALES_DIR / f"{region_key}-log.md"
        if log_path.exists():
            counts = parse_log(log_path)
            if counts:
                region_data[region_name] = counts
    return region_data


def _compute_sale_values(
    region_data: dict[str, Counter],
) -> dict[str, float]:
    sale_values = {}
    for location, counts in region_data.items():
        total_fish = sum(counts.values())
        total_value = sum(
            counts[name] * PRICES[name][0]
            for name in counts
            if name in PRICES
        )
        sale_values[location] = total_value / total_fish
    return sale_values


# --- Ternary coordinate helpers ---

def _to_cartesian(fraction_a: float, fraction_b: float, fraction_c: float):
    """Convert barycentric (a, b, c) to 2D cartesian for equilateral triangle."""
    x = 0.5 * (2 * fraction_b + fraction_c)
    y = (np.sqrt(3) / 2) * fraction_c
    return x, y


def figure_1_ternary_heatmap(
    locations: list[str],
    sale_values: dict[str, float],
    bundles: list,
) -> None:
    """Ternary heatmap of total $/hour across all possible allocations."""
    granularity = 200
    x_points = []
    y_points = []
    revenue_values = []

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
            x, y = _to_cartesian(fraction_a, fraction_b, fraction_c)
            x_points.append(x)
            y_points.append(y)
            revenue_values.append(revenue)

    x_points = np.array(x_points)
    y_points = np.array(y_points)
    revenue_values = np.array(revenue_values)

    # Find optimal
    optimal_index = np.argmax(revenue_values)
    optimal_x = x_points[optimal_index]
    optimal_y = y_points[optimal_index]
    optimal_revenue = revenue_values[optimal_index]

    # Reconstruct optimal fractions for label
    best_a = (1.0 - optimal_x - optimal_y / np.sqrt(3))
    best_c = optimal_y * 2 / np.sqrt(3)
    best_b = 1.0 - best_a - best_c

    figure, axis = plt.subplots(1, 1, figsize=(10, 8.5))

    colormap = LinearSegmentedColormap.from_list(
        "revenue", ["#2c1810", "#8b4513", "#cd853f", "#ffd700", "#00ff88", "#00ffcc"],
    )
    scatter = axis.scatter(
        x_points, y_points, c=revenue_values, cmap=colormap,
        s=3, marker="s", edgecolors="none",
    )

    colorbar = plt.colorbar(scatter, ax=axis, shrink=0.7, pad=0.02)
    colorbar.set_label("$/Hour", fontsize=12)

    # Draw triangle edges
    triangle_x = [0, 1, 0.5, 0]
    triangle_y = [0, 0, np.sqrt(3) / 2, 0]
    axis.plot(triangle_x, triangle_y, "k-", linewidth=2)

    # Corner labels
    axis.text(
        0, -0.05, f"{locations[0]}\n(100%)",
        ha="center", va="top", fontsize=11, fontweight="bold",
    )
    axis.text(
        1, -0.05, f"{locations[1]}\n(100%)",
        ha="center", va="top", fontsize=11, fontweight="bold",
    )
    axis.text(
        0.5, np.sqrt(3) / 2 + 0.03, f"{locations[2]}\n(100%)",
        ha="center", va="bottom", fontsize=11, fontweight="bold",
    )

    # Mark optimal point
    axis.plot(
        optimal_x, optimal_y, marker="*", color="white",
        markersize=18, markeredgecolor="black", markeredgewidth=1.5, zorder=5,
    )
    axis.annotate(
        f"Optimal: ${optimal_revenue:,.0f}/hr\n"
        f"({best_a:.0%} / {best_b:.0%} / {best_c:.0%})",
        xy=(optimal_x, optimal_y),
        xytext=(optimal_x + 0.15, optimal_y + 0.08),
        fontsize=10, fontweight="bold",
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.9},
        arrowprops={"arrowstyle": "->", "color": "black", "lw": 1.5},
        zorder=6,
    )

    # Mark solo points
    for index, location in enumerate(locations):
        solo_fractions = {loc: (1.0 if loc == location else 0.0) for loc in locations}
        solo_revenue = _compute_revenue(solo_fractions, sale_values, bundles)
        if index == 0:
            solo_x, solo_y = _to_cartesian(1, 0, 0)
        elif index == 1:
            solo_x, solo_y = _to_cartesian(0, 1, 0)
        else:
            solo_x, solo_y = _to_cartesian(0, 0, 1)
        axis.plot(
            solo_x, solo_y, marker="o", color="red",
            markersize=8, markeredgecolor="black", zorder=5,
        )
        # Position labels to avoid overlap with corner labels
        if index == 0:
            text_x, text_y = solo_x - 0.12, solo_y + 0.08
        elif index == 1:
            text_x, text_y = solo_x + 0.12, solo_y + 0.08
        else:
            text_x, text_y = solo_x + 0.15, solo_y - 0.05
        axis.annotate(
            f"${solo_revenue:,.0f}/hr",
            xy=(solo_x, solo_y),
            xytext=(text_x, text_y),
            fontsize=9, color="red",
            arrowprops={"arrowstyle": "->", "color": "red", "lw": 1},
            zorder=6,
        )

    axis.set_xlim(-0.1, 1.1)
    axis.set_ylim(-0.15, np.sqrt(3) / 2 + 0.12)
    axis.set_aspect("equal")
    axis.axis("off")
    axis.set_title(
        "Revenue Surface: Total $/Hour by Location Allocation",
        fontsize=14, fontweight="bold", pad=15,
    )

    figure.tight_layout()
    output_path = OUTPUT_DIRECTORY / "1_ternary_heatmap.png"
    figure.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(figure)
    print(f"  Saved {output_path}")


def figure_2_revenue_decomposition(
    locations: list[str],
    sale_values: dict[str, float],
    bundles: list,
) -> None:
    """Show sales vs bundle revenue along a sweep from worst solo to optimal."""
    # Sweep from 100% best-solo location to optimal allocation
    granularity = 100
    best_revenue = -1.0
    best_fractions: dict[str, float] = {}

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
            rev = _compute_revenue(fractions, sale_values, bundles)
            if rev > best_revenue:
                best_revenue = rev
                best_fractions = fractions.copy()

    # Find best solo
    solo_revenues = {}
    for location in locations:
        solo = {loc: (1.0 if loc == location else 0.0) for loc in locations}
        solo_revenues[location] = _compute_revenue(solo, sale_values, bundles)
    best_solo_location = max(solo_revenues, key=lambda location: solo_revenues[location])
    best_solo_fractions = {
        loc: (1.0 if loc == best_solo_location else 0.0) for loc in locations
    }

    # Sweep along the line from best solo to optimal
    steps = 200
    time_axis = np.linspace(0, 1, steps)
    sales_revenue = []
    bundle_revenue = []
    total_revenue = []

    for time_step in time_axis:
        fractions = {
            loc: best_solo_fractions[loc] * (1 - time_step)
            + best_fractions[loc] * time_step
            for loc in locations
        }

        sale_part = sum(
            fish_per_hour(loc) * fractions[loc] * sale_values[loc] for loc in locations
        )
        total_part = _compute_revenue(fractions, sale_values, bundles)
        bundle_part = total_part - sale_part

        sales_revenue.append(sale_part)
        bundle_revenue.append(bundle_part)
        total_revenue.append(total_part)

    sales_revenue = np.array(sales_revenue)
    bundle_revenue = np.array(bundle_revenue)
    total_revenue = np.array(total_revenue)

    figure, (axis_top, axis_bottom) = plt.subplots(2, 1, figsize=(10, 8), height_ratios=[3, 1])

    # Top: stacked area
    axis_top.fill_between(
        time_axis * 100, 0, sales_revenue,
        alpha=0.7, color="#4a90d9", label="Sales revenue",
    )
    axis_top.fill_between(
        time_axis * 100, sales_revenue, total_revenue,
        alpha=0.7, color="#e8a838", label="Bundle revenue",
    )
    axis_top.plot(
        time_axis * 100, total_revenue,
        color="black", linewidth=2, label="Total",
    )

    # Mark endpoints
    axis_top.axvline(x=0, color="red", linestyle="--", alpha=0.5)
    axis_top.axvline(x=100, color="green", linestyle="--", alpha=0.5)

    axis_top.set_ylabel("$/Hour", fontsize=12)
    axis_top.set_title(
        f"Revenue Decomposition: Solo {best_solo_location} → Optimal Split",
        fontsize=13, fontweight="bold",
    )
    axis_top.legend(loc="upper left", fontsize=10)
    axis_top.set_xlim(0, 100)

    # Bottom: allocation fractions along the path
    for location_index, location in enumerate(locations):
        fractions_along_path = [
            best_solo_fractions[location] * (1 - time_step)
            + best_fractions[location] * time_step
            for time_step in time_axis
        ]
        colors = ["#e74c3c", "#2ecc71", "#3498db"]
        axis_bottom.plot(
            time_axis * 100, np.array(fractions_along_path) * 100,
            linewidth=2, color=colors[location_index], label=location,
        )

    axis_bottom.set_xlabel("Path from solo → optimal (%)", fontsize=11)
    axis_bottom.set_ylabel("Time at location (%)", fontsize=11)
    axis_bottom.legend(loc="center right", fontsize=9)
    axis_bottom.set_xlim(0, 100)
    axis_bottom.set_ylim(0, 105)

    figure.tight_layout()
    output_path = OUTPUT_DIRECTORY / "2_revenue_decomposition.png"
    figure.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(figure)
    print(f"  Saved {output_path}")


def figure_3_bundle_bottleneck(
    locations: list[str],
    sale_values: dict[str, float],
    bundles: list,
    region_data: dict[str, Counter],
) -> None:
    """Illustrate the min() bottleneck for a cross-location bundle."""
    # Find first cross-location bundle
    target_bundle = None
    for bundle_name, bonus, assignments in bundles:
        bundle_locations = {a["location"] for a in assignments}
        if len(bundle_locations) > 1:
            target_bundle = (bundle_name, bonus, assignments)
            break

    if target_bundle is None:
        print("  No cross-location bundle found, skipping figure 3")
        return

    bundle_name, bonus, assignments = target_bundle
    bundle_probabilities = [a["probability"] for a in assignments]

    # Sweep: vary the bottleneck location's fraction from 0 to balanced
    # Keep others proportional to their 1/p ratios
    balanced_fractions = {}
    total_inverse = sum(1.0 / p for p in bundle_probabilities)
    for index, assignment in enumerate(assignments):
        balanced_fractions[assignment["location"]] = (
            (1.0 / assignment["probability"]) / total_inverse
        )

    steps = 200

    figure, axis = plt.subplots(1, 1, figsize=(10, 6))

    # Show fill rates for each fish as we sweep allocation
    sweep_axis = np.linspace(0.01, 0.99, steps)
    colors = ["#e74c3c", "#2ecc71", "#3498db"]

    for fish_index, assignment in enumerate(assignments):
        fill_rates = []
        for fraction_for_this_fish_location in sweep_axis:
            remaining = 1.0 - fraction_for_this_fish_location
            other_total = sum(
                balanced_fractions[a["location"]]
                for other_index, a in enumerate(assignments)
                if other_index != fish_index
            )
            fractions = {}
            for other_index, other_assignment in enumerate(assignments):
                if other_index == fish_index:
                    fractions[other_assignment["location"]] = (
                        fraction_for_this_fish_location
                    )
                else:
                    fractions[other_assignment["location"]] = (
                        remaining * balanced_fractions[other_assignment["location"]]
                        / other_total
                    )
            rate = (
                fractions[assignment["location"]]
                * fish_per_hour(assignment["location"])
                * assignment["probability"]
            )
            fill_rates.append(rate)

        axis.plot(
            sweep_axis * 100, fill_rates,
            linewidth=2, color=colors[fish_index],
            label=f"{assignment['fish']} @ {assignment['location']}"
                  f" (p={assignment['probability']:.1%})",
        )

    # Show balanced point
    for fish_index, assignment in enumerate(assignments):
        balanced_rate = (
            balanced_fractions[assignment["location"]]
            * fish_per_hour(assignment["location"])
            * assignment["probability"]
        )
        balanced_x = balanced_fractions[assignment["location"]] * 100
        axis.plot(
            balanced_x, balanced_rate,
            marker="o", color=colors[fish_index], markersize=8, zorder=5,
        )

    # All balanced rates should be equal
    balanced_rate = (
        balanced_fractions[assignments[0]["location"]]
        * fish_per_hour(assignments[0]["location"])
        * assignments[0]["probability"]
    )
    axis.axhline(
        y=balanced_rate, color="gray", linestyle=":", alpha=0.5,
        label=f"Balanced rate ({balanced_rate:.2f} fish/hr)",
    )

    axis.set_xlabel(
        "Time % allocated to each fish's home location (others proportional)",
        fontsize=11,
    )
    axis.set_ylabel("Fill rate (bundle fish / hour)", fontsize=12)
    axis.set_title(
        f"Bundle Bottleneck: {bundle_name}\n"
        f"The bundle completes at the rate of the SLOWEST fish slot (min)",
        fontsize=13, fontweight="bold",
    )
    axis.legend(fontsize=10, loc="upper left")

    axis.annotate(
        "Bundle completion rate = min(all fill rates)\n"
        "→ Must balance time to equalize rates",
        xy=(50, balanced_rate),
        xytext=(55, balanced_rate * 1.8),
        fontsize=10,
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "#fff3cd", "alpha": 0.9},
        arrowprops={"arrowstyle": "->", "color": "black"},
    )

    figure.tight_layout()
    output_path = OUTPUT_DIRECTORY / "3_bundle_bottleneck.png"
    figure.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(figure)
    print(f"  Saved {output_path}")


def figure_4_competing_forces(
    locations: list[str],
    sale_values: dict[str, float],
    bundles: list,
) -> None:
    """Show the tug-of-war between sales (go to best location) and bundles (balance)."""
    best_sale_location = max(sale_values, key=lambda location: sale_values[location])

    cross_bundles = [
        (name, bonus, assignments)
        for name, bonus, assignments in bundles
        if len({a["location"] for a in assignments}) > 1
    ]

    if not cross_bundles:
        return

    biggest_bundle = max(cross_bundles, key=lambda bundle: bundle[1])
    _, _, biggest_assignments = biggest_bundle

    inverse_sum = sum(1.0 / a["probability"] for a in biggest_assignments)
    bundle_balanced = {
        a["location"]: (1.0 / a["probability"]) / inverse_sum
        for a in biggest_assignments
    }
    for loc in locations:
        if loc not in bundle_balanced:
            bundle_balanced[loc] = 0.0

    all_best_sale = {
        loc: (1.0 if loc == best_sale_location else 0.0) for loc in locations
    }

    steps = 200
    time_axis = np.linspace(0, 1, steps)
    sales_values_curve = []
    bundle_values_curve = []
    total_values_curve = []

    for time_step in time_axis:
        fractions = {
            loc: all_best_sale[loc] * (1 - time_step)
            + bundle_balanced[loc] * time_step
            for loc in locations
        }
        sale_part = sum(
            fish_per_hour(loc) * fractions[loc] * sale_values[loc] for loc in locations
        )
        total_part = _compute_revenue(fractions, sale_values, bundles)
        bundle_part = total_part - sale_part
        sales_values_curve.append(sale_part)
        bundle_values_curve.append(bundle_part)
        total_values_curve.append(total_part)

    figure, axis = plt.subplots(1, 1, figsize=(10, 6))

    axis.plot(
        time_axis * 100, sales_values_curve,
        linewidth=2.5, color="#4a90d9", label="Sales $/hr",
    )
    axis.plot(
        time_axis * 100, bundle_values_curve,
        linewidth=2.5, color="#e8a838", label="Bundle $/hr",
    )
    axis.plot(
        time_axis * 100, total_values_curve,
        linewidth=3, color="black", label="Total $/hr",
    )

    optimal_index = np.argmax(total_values_curve)
    axis.plot(
        time_axis[optimal_index] * 100, total_values_curve[optimal_index],
        marker="*", color="black", markersize=15, zorder=5,
    )
    axis.annotate(
        f"Best on this path:\n${total_values_curve[optimal_index]:,.0f}/hr",
        xy=(time_axis[optimal_index] * 100, total_values_curve[optimal_index]),
        xytext=(time_axis[optimal_index] * 100 - 25, total_values_curve[optimal_index] + 1500),
        fontsize=10, fontweight="bold",
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.9},
        arrowprops={"arrowstyle": "->", "color": "black", "lw": 1.5},
    )

    axis.annotate(
        "", xy=(5, sales_values_curve[0] - 500),
        xytext=(5, sales_values_curve[0] + 500),
        arrowprops={"arrowstyle": "<-", "color": "#4a90d9", "lw": 3},
    )
    axis.text(
        8, sales_values_curve[0],
        "Sales pull\n← best location",
        fontsize=9, color="#4a90d9", va="center",
    )

    axis.annotate(
        "", xy=(95, bundle_values_curve[-1] - 500),
        xytext=(95, bundle_values_curve[-1] + 500),
        arrowprops={"arrowstyle": "<-", "color": "#e8a838", "lw": 3},
    )
    axis.text(
        82, bundle_values_curve[-1] + 800,
        "Bundle pull\n→ balanced",
        fontsize=9, color="#e8a838", va="center",
    )

    axis.set_xlabel(
        f"← 100% {best_sale_location} (best sales)          "
        f"Bundle-balanced (best bundles) →",
        fontsize=11,
    )
    axis.set_ylabel("$/Hour", fontsize=12)
    axis.set_title(
        "Competing Forces: Sales Value vs Bundle Completions",
        fontsize=13, fontweight="bold",
    )
    axis.legend(fontsize=11, loc="center right")
    axis.set_xlim(0, 100)

    figure.tight_layout()
    output_path = OUTPUT_DIRECTORY / "4_competing_forces.png"
    figure.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(figure)
    print(f"  Saved {output_path}")


def _find_optimal_fractions(
    locations: list[str],
    sale_values: dict[str, float],
    bundles: list,
    granularity: int = 100,
) -> dict[str, float]:
    """Grid-search for the optimal allocation fractions."""
    best_revenue = -1.0
    best_fractions: dict[str, float] = {}
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
    return best_fractions


def _build_1d_sweep_path(
    sweep_location: str,
    other_locations: list[str],
    other_ratios: list[float],
    steps: int = 500,
) -> tuple[np.ndarray, list[dict[str, float]]]:
    """Build a 1D path parameterized by one location's fraction.

    Returns (sweep_values, list_of_fraction_dicts).
    The other locations share the remaining (1-f) proportionally.
    """
    ratio_sum = sum(other_ratios)
    normalized_ratios = [ratio / ratio_sum for ratio in other_ratios]
    sweep_values = np.linspace(0, 1, steps)
    fraction_list = []
    for fraction in sweep_values:
        point = {sweep_location: fraction}
        remaining = 1.0 - fraction
        for location, ratio in zip(other_locations, normalized_ratios):
            point[location] = remaining * ratio
        fraction_list.append(point)
    return sweep_values, fraction_list


def figure_5_min_envelope(
    locations: list[str],
    sale_values: dict[str, float],
    bundles: list,
) -> None:
    """Show the rate lines and min() envelope for each cross-location bundle.

    For each bundle, the individual rate lines f_loc(j) * r * p_j are straight
    lines. The min() of those lines creates the piecewise-linear envelope with
    visible kink points where the bottleneck switches from one fish to another.
    """
    cross_bundles = [
        (name, bonus, assignments)
        for name, bonus, assignments in bundles
        if len({a["location"] for a in assignments}) > 1
    ]
    if not cross_bundles:
        print("  No cross-location bundles, skipping figure 5")
        return

    # Build 1D sweep path using optimal allocation ratios
    optimal = _find_optimal_fractions(locations, sale_values, bundles)
    sweep_location = locations[0]
    other_locations = locations[1:]
    other_ratios = [optimal.get(loc, 0.01) for loc in other_locations]
    sweep_values, fraction_list = _build_1d_sweep_path(
        sweep_location, other_locations, other_ratios, steps=500,
    )

    subplot_count = len(cross_bundles)
    figure, axes = plt.subplots(
        subplot_count, 1,
        figsize=(12, 4.5 * subplot_count),
        squeeze=False,
    )

    line_colors = ["#e74c3c", "#2ecc71", "#3498db", "#9b59b6", "#f39c12"]
    line_dashes = [(8, 4), (8, 4, 2, 4), (2, 3), (5, 2, 5, 2, 2, 2), (12, 4)]
    line_markers = ["o", "s", "D", "^", "v"]

    for bundle_index, (bundle_name, bonus, assignments) in enumerate(cross_bundles):
        axis = axes[bundle_index, 0]

        # Compute individual rate lines and min envelope
        rate_curves: list[np.ndarray] = []
        for assignment in assignments:
            rates = np.array([
                fractions.get(assignment["location"], 0)
                * fish_per_hour(assignment["location"])
                * assignment["probability"]
                for fractions in fraction_list
            ])
            rate_curves.append(rates)

        rate_matrix = np.array(rate_curves)
        min_envelope = np.min(rate_matrix, axis=0)

        # Plot individual rate lines with distinct dashes + markers
        for fish_index, assignment in enumerate(assignments):
            color = line_colors[fish_index % len(line_colors)]
            dashes = line_dashes[fish_index % len(line_dashes)]
            marker = line_markers[fish_index % len(line_markers)]
            axis.plot(
                sweep_values * 100,
                rate_curves[fish_index],
                linewidth=2,
                linestyle="--",
                dashes=dashes,
                color=color,
                alpha=0.8,
                marker=marker,
                markersize=5,
                markevery=50,
                label=(
                    f"{assignment['fish']} @ {assignment['location']}"
                    f" (p={assignment['probability']:.1%})"
                ),
            )

        # Plot min() envelope (bold)
        axis.plot(
            sweep_values * 100,
            min_envelope,
            linewidth=3,
            color="black",
            label="min() envelope",
        )

        # Find and mark kink points (where bottleneck switches)
        bottleneck_index = np.argmin(rate_matrix, axis=0)
        kink_positions = np.where(np.diff(bottleneck_index) != 0)[0]
        for kink in kink_positions:
            kink_x = sweep_values[kink] * 100
            kink_y = min_envelope[kink]
            old_bottleneck = assignments[bottleneck_index[kink]]["fish"]
            new_bottleneck = assignments[bottleneck_index[kink + 1]]["fish"]
            axis.plot(
                kink_x, kink_y,
                marker="o", color="black", markersize=8, zorder=5,
            )
            axis.annotate(
                f"Kink: bottleneck switches\n"
                f"{old_bottleneck} → {new_bottleneck}",
                xy=(kink_x, kink_y),
                xytext=(kink_x + 8, kink_y + max(min_envelope) * 0.15),
                fontsize=9,
                bbox={
                    "boxstyle": "round,pad=0.3",
                    "facecolor": "#fff3cd",
                    "alpha": 0.9,
                },
                arrowprops={"arrowstyle": "->", "color": "black"},
            )

        # Shade the min region
        axis.fill_between(
            sweep_values * 100, 0, min_envelope,
            alpha=0.1, color="black",
        )

        # Mark where this bundle's min() envelope peaks
        bundle_optimal_index = np.argmax(min_envelope)
        bundle_optimal_x = sweep_values[bundle_optimal_index] * 100
        bundle_optimal_y = min_envelope[bundle_optimal_index]
        axis.axvline(
            x=bundle_optimal_x,
            color="green", linestyle=":", alpha=0.5,
            label=f"Bundle peak ({bundle_optimal_x:.0f}%)",
        )
        axis.plot(
            bundle_optimal_x, bundle_optimal_y,
            marker="*", color="green", markersize=12, zorder=5,
        )

        axis.set_ylabel("Fish catch rate (fish/hr)", fontsize=11)
        axis.set_title(
            f"{bundle_name} (bonus ${bonus:,}):  "
            f"rate lines and min() envelope",
            fontsize=12, fontweight="bold",
        )
        axis.legend(fontsize=9, loc="upper right")
        if bundle_index == subplot_count - 1:
            other_label = " / ".join(
                f"{loc} ∝ {ratio:.0%}" for loc, ratio in zip(other_locations, other_ratios)
            )
            axis.set_xlabel(
                f"% time at {sweep_location}"
                f"  (remaining split: {other_label})",
                fontsize=11,
            )

    figure.suptitle(
        "Piecewise-Linear Anatomy: rate lines → min() → bundle revenue",
        fontsize=14, fontweight="bold", y=1.01,
    )
    figure.tight_layout()
    output_path = OUTPUT_DIRECTORY / "5_min_envelope.png"
    figure.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(figure)
    print(f"  Saved {output_path}")


def figure_6_objective_decomposition(
    locations: list[str],
    sale_values: dict[str, float],
    bundles: list,
) -> dict | None:
    """Show the full objective decomposed into its piecewise-linear components.

    Along a 1D sweep, plots:
    - The linear sales component
    - Each bundle's min()*bonus contribution (each is piecewise-linear)
    - The total revenue (sum of all, also piecewise-linear)
    """
    optimal = _find_optimal_fractions(locations, sale_values, bundles)
    sweep_location = locations[0]
    other_locations = locations[1:]
    other_ratios = [optimal.get(loc, 0.01) for loc in other_locations]
    sweep_values, fraction_list = _build_1d_sweep_path(
        sweep_location, other_locations, other_ratios, steps=500,
    )

    # Compute sales component (linear)
    sales_curve = np.array([
        sum(
            fish_per_hour(loc) * fractions.get(loc, 0) * sale_values[loc]
            for loc in locations
        )
        for fractions in fraction_list
    ])

    # Compute each bundle's contribution individually
    bundle_curves: list[tuple[str, np.ndarray, bool]] = []
    for bundle_name, bonus, assignments in bundles:
        bundle_locations = {a["location"] for a in assignments}
        is_cross_location = len(bundle_locations) > 1
        curve = []
        for fractions in fraction_list:
            if len(bundle_locations) == 1:
                location = next(iter(bundle_locations))
                fraction = fractions.get(location, 0)
                bottleneck = min(a["probability"] for a in assignments)
                value = fraction * fish_per_hour(location) * bottleneck * bonus
            else:
                rates = [
                    fractions.get(a["location"], 0)
                    * fish_per_hour(a["location"])
                    * a["probability"]
                    for a in assignments
                ]
                value = min(rates) * bonus
            curve.append(value)
        bundle_curves.append((bundle_name, np.array(curve), is_cross_location))

    total_curve = sales_curve + sum(curve for _, curve, _ in bundle_curves)

    # Zoom: crop y-axis to show only the bundle "juice" on top
    y_min_zoom = float(np.min(sales_curve)) * 0.98

    figure, axis = plt.subplots(1, 1, figsize=(12, 7))

    # Stacked components (zoomed into the top)
    axis.fill_between(
        sweep_values * 100, y_min_zoom, sales_curve,
        alpha=0.4, color="#4a90d9", label="Sales (linear)",
    )
    axis.plot(
        sweep_values * 100, sales_curve,
        linewidth=1.5, color="#4a90d9", alpha=0.7,
    )

    cumulative = sales_curve.copy()
    bundle_colors_cross = ["#e8a838", "#e67e22", "#d35400", "#c0392b"]
    bundle_colors_single = ["#27ae60", "#2ecc71", "#1abc9c", "#16a085"]
    cross_index = 0
    single_index = 0

    for bundle_name, curve, is_cross_location in bundle_curves:
        if is_cross_location:
            color = bundle_colors_cross[cross_index % len(bundle_colors_cross)]
            cross_index += 1
        else:
            color = bundle_colors_single[single_index % len(bundle_colors_single)]
            single_index += 1

        new_cumulative = cumulative + curve
        axis.fill_between(
            sweep_values * 100, cumulative, new_cumulative,
            alpha=0.4, color=color,
            label=f"{bundle_name} ({'cross' if is_cross_location else 'local'})",
        )
        cumulative = new_cumulative

    axis.plot(
        sweep_values * 100, total_curve,
        linewidth=3, color="black", label="Total $/hr",
    )

    # Mark optimal
    optimal_fraction = optimal.get(sweep_location, 0) * 100
    optimal_index = np.argmin(np.abs(sweep_values * 100 - optimal_fraction))
    axis.plot(
        optimal_fraction, total_curve[optimal_index],
        marker="*", color="black", markersize=15, zorder=5,
    )
    axis.annotate(
        f"Optimal: ${total_curve[optimal_index]:,.0f}/hr\n"
        f"at {optimal_fraction:.0f}% {sweep_location}",
        xy=(optimal_fraction, total_curve[optimal_index]),
        xytext=(optimal_fraction + 15, total_curve[optimal_index] - 2000),
        fontsize=10, fontweight="bold",
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.9},
        arrowprops={"arrowstyle": "->", "color": "black", "lw": 1.5},
    )

    axis.set_ylim(bottom=y_min_zoom)
    other_label = " / ".join(
        f"{loc} ∝ {ratio:.0%}" for loc, ratio in zip(other_locations, other_ratios)
    )
    axis.set_xlabel(
        f"% time at {sweep_location}"
        f"  (remaining split: {other_label})",
        fontsize=11,
    )
    axis.set_ylabel("$/Hour", fontsize=12)
    axis.set_title(
        "Piecewise-Linear Objective: Stacked Components (zoomed)",
        fontsize=13, fontweight="bold",
    )
    axis.legend(fontsize=9, loc="upper right", ncols=2)

    figure.tight_layout()
    output_path = OUTPUT_DIRECTORY / "6_objective_decomposition.png"
    figure.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(figure)
    print(f"  Saved {output_path}")

    # --- Return computed data for figure 7 ---
    return {
        "sweep_values": sweep_values,
        "sweep_location": sweep_location,
        "other_locations": other_locations,
        "other_ratios": other_ratios,
        "sales_curve": sales_curve,
        "bundle_curves": bundle_curves,
        "optimal_fraction": optimal_fraction,
    }


def figure_7_individual_components(
    decomposition_data: dict,
) -> None:
    """Individual (unstacked) bundle components on their own scale."""
    sweep_values = decomposition_data["sweep_values"]
    sweep_location = decomposition_data["sweep_location"]
    other_locations = decomposition_data["other_locations"]
    other_ratios = decomposition_data["other_ratios"]
    sales_curve = decomposition_data["sales_curve"]
    bundle_curves = decomposition_data["bundle_curves"]
    optimal_fraction = decomposition_data["optimal_fraction"]

    bundle_colors_cross = ["#e8a838", "#e67e22", "#d35400", "#c0392b"]
    bundle_colors_single = ["#27ae60", "#2ecc71", "#1abc9c", "#16a085"]

    # Two subplots: sales on top (own scale), bundles on bottom (own scale)
    figure, (axis_sales, axis_bundles) = plt.subplots(
        2, 1, figsize=(12, 8), height_ratios=[1, 2],
    )

    # Sales component
    axis_sales.plot(
        sweep_values * 100, sales_curve,
        linewidth=2.5, color="#4a90d9", label="Sales (linear)",
    )
    axis_sales.axvline(
        x=optimal_fraction, color="green", linestyle=":", alpha=0.5,
        label=f"Optimal ({optimal_fraction:.0f}%)",
    )
    axis_sales.set_ylabel("$/Hour", fontsize=11)
    axis_sales.set_title(
        "Sales Component (linear in allocation)",
        fontsize=12, fontweight="bold",
    )
    axis_sales.legend(fontsize=9)

    # Bundle components (each on the same axes, but without sales dwarfing them)
    cross_index = 0
    single_index = 0
    for bundle_name, curve, is_cross_location in bundle_curves:
        if is_cross_location:
            color = bundle_colors_cross[cross_index % len(bundle_colors_cross)]
            cross_index += 1
            linestyle = "-"
            linewidth = 2.5
        else:
            color = bundle_colors_single[single_index % len(bundle_colors_single)]
            single_index += 1
            linestyle = "--"
            linewidth = 2
        axis_bundles.plot(
            sweep_values * 100, curve,
            linewidth=linewidth, color=color, linestyle=linestyle,
            label=f"{bundle_name} ({'cross' if is_cross_location else 'local'})",
        )

    axis_bundles.axvline(
        x=optimal_fraction, color="green", linestyle=":", alpha=0.5,
    )

    other_label = " / ".join(
        f"{loc} ∝ {ratio:.0%}" for loc, ratio in zip(other_locations, other_ratios)
    )
    axis_bundles.set_xlabel(
        f"% time at {sweep_location}"
        f"  (remaining split: {other_label})",
        fontsize=11,
    )
    axis_bundles.set_ylabel("$/Hour", fontsize=12)
    axis_bundles.set_title(
        "Bundle Components (unstacked) — piecewise-linear kinks visible",
        fontsize=12, fontweight="bold",
    )
    axis_bundles.legend(fontsize=9, loc="upper right", ncols=2)

    figure.tight_layout()
    output_path = OUTPUT_DIRECTORY / "7_individual_components.png"
    figure.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(figure)
    print(f"  Saved {output_path}")


def main() -> None:
    region_data = _load_region_data()
    locations = [
        name for name in ["Alamo Sea", "Land Act Dam", "Roxwood"]
        if name in region_data
    ]
    if len(locations) < 3:
        print(f"Need 3 locations, found {len(locations)}")
        return

    sale_values = _compute_sale_values(region_data)
    bundles = _resolve_available_bundles(region_data)

    print("Generating figures...")
    figure_1_ternary_heatmap(locations, sale_values, bundles)
    figure_2_revenue_decomposition(locations, sale_values, bundles)
    figure_3_bundle_bottleneck(locations, sale_values, bundles, region_data)
    figure_4_competing_forces(locations, sale_values, bundles)
    figure_5_min_envelope(locations, sale_values, bundles)
    decomposition_data = figure_6_objective_decomposition(locations, sale_values, bundles)
    if decomposition_data:
        figure_7_individual_components(decomposition_data)
    print("Done!")


if __name__ == "__main__":
    main()
