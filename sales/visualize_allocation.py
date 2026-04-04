"""Visualize the fishing allocation optimization problem.

Generates figures showing:
1. Ternary heatmap of total $/hour across all allocations
2. Revenue decomposition: sales vs bundles along the optimal path
3. Bundle fill-rate bottleneck illustration
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyArrowPatch

# Add parent to path so we can import the sales module
sys.path.insert(0, str(Path(__file__).parent.parent))

from sales.update_sales import (
    BUNDLES,
    FISH_PER_HOUR,
    PRICES,
    REGIONS,
    SALES_DIR,
    _compute_revenue,
    _estimate_fish_probability,
    _resolve_available_bundles,
    fish_location,
    parse_log,
)

OUTPUT_DIRECTORY = SALES_DIR / "figures"
OUTPUT_DIRECTORY.mkdir(exist_ok=True)


def _load_region_data() -> dict[str, "Counter"]:
    from collections import Counter

    region_data: dict[str, Counter] = {}
    for region_key, region_name in REGIONS.items():
        log_path = SALES_DIR / f"{region_key}-log.md"
        if log_path.exists():
            counts = parse_log(log_path)
            if counts:
                region_data[region_name] = counts
    return region_data


def _compute_sale_values(
    region_data: dict[str, "Counter"],
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
    fraction_labels = []

    for time_step in time_axis:
        fractions = {
            loc: best_solo_fractions[loc] * (1 - time_step)
            + best_fractions[loc] * time_step
            for loc in locations
        }

        sale_part = FISH_PER_HOUR * sum(
            fractions[loc] * sale_values[loc] for loc in locations
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
    region_data: dict[str, "Counter"],
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
    bundle_locations = [a["location"] for a in assignments]
    bundle_probabilities = [a["probability"] for a in assignments]
    bundle_fish_names = [a["fish"] for a in assignments]

    # Sweep: vary the bottleneck location's fraction from 0 to balanced
    # Keep others proportional to their 1/p ratios
    balanced_fractions = {}
    total_inverse = sum(1.0 / p for p in bundle_probabilities)
    for index, assignment in enumerate(assignments):
        balanced_fractions[assignment["location"]] = (
            (1.0 / assignment["probability"]) / total_inverse
        )

    steps = 200
    bottleneck_index = min(
        range(len(assignments)), key=lambda index: bundle_probabilities[index],
    )
    bottleneck_location = assignments[bottleneck_index]["location"]

    figure, axis = plt.subplots(1, 1, figsize=(10, 6))

    # Show fill rates for each fish as we sweep allocation
    sweep_axis = np.linspace(0.01, 0.99, steps)
    colors = ["#e74c3c", "#2ecc71", "#3498db"]

    for fish_index, assignment in enumerate(assignments):
        fill_rates = []
        for fraction_for_this_fish_location in sweep_axis:
            # Allocate fraction_for_this_fish_location to this fish's location,
            # distribute remaining proportionally among other locations
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
                * FISH_PER_HOUR
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
            * FISH_PER_HOUR
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
        * FISH_PER_HOUR
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

    # Add annotation explaining min()
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
    # Sweep between balanced-for-bundles and all-at-best-sale-location
    best_sale_location = max(sale_values, key=lambda location: sale_values[location])

    # Compute bundle-balanced fractions
    cross_bundles = [
        (name, bonus, assignments)
        for name, bonus, assignments in bundles
        if len({a["location"] for a in assignments}) > 1
    ]

    if not cross_bundles:
        return

    # Use the biggest cross-location bundle for balancing
    biggest_bundle = max(cross_bundles, key=lambda bundle: bundle[1])
    _, _, biggest_assignments = biggest_bundle

    inverse_sum = sum(1.0 / a["probability"] for a in biggest_assignments)
    bundle_balanced = {
        a["location"]: (1.0 / a["probability"]) / inverse_sum
        for a in biggest_assignments
    }
    # Fill in zero for locations not in this bundle
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
        sale_part = FISH_PER_HOUR * sum(
            fractions[loc] * sale_values[loc] for loc in locations
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

    # Mark the optimal along this path
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

    # Add arrows showing the forces
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
    print("Done!")


if __name__ == "__main__":
    main()
