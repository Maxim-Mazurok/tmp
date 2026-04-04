"""Experiment: test whether fish drop rates use nice round percentages.

For each tier, tries percentage templates (multiples of 5% and 10%) summing
to 100% and computes joint χ² across all locations. Compares with arbitrary
integer weight fits.

The hypothesis: the game defines drop rates as simple percentage values
(e.g., 20%, 15%, 10%) rather than abstract integer weights.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

sys.path.insert(0, str(Path(__file__).parent.parent))

from sales.stats import chi_squared_p_value, fit_integer_weights
from sales.visualize_shared_weights import collect_tier_data, compute_chi_squared


def enumerate_percentage_vectors(
    fish_count: int,
    step: int,
) -> list[tuple[int, ...]]:
    """Generate all non-increasing percentage tuples summing to 100.

    Each entry is a multiple of `step` and >= `step`.
    """
    results: list[tuple[int, ...]] = []

    def recurse(
        remaining_sum: int,
        remaining_count: int,
        max_value: int,
        current: list[int],
    ) -> None:
        if remaining_count == 0:
            if remaining_sum == 0:
                results.append(tuple(current))
            return
        min_value = step
        upper = min(max_value, remaining_sum - (remaining_count - 1) * min_value)
        for value in range(upper, min_value - 1, -step):
            recurse(
                remaining_sum - value,
                remaining_count - 1,
                value,
                current + [value],
            )

    recurse(100, fish_count, 100, [])
    return results


def compute_joint_fit(
    percentage_vector: tuple[int, ...],
    locations_data: list[tuple[str, list[tuple[str, int]]]],
) -> dict:
    """Compute joint χ² for a percentage vector across all locations.

    Locations with fewer fish than the template use the first N entries
    as weights (renormalized implicitly by the χ² computation).
    """
    total_chi_squared = 0.0
    total_degrees = 0
    per_location = []

    for region_name, fish_list in locations_data:
        observed = [count for _, count in fish_list]
        location_fish_count = len(observed)
        location_weights = list(percentage_vector[:location_fish_count])
        chi_squared, p_value = compute_chi_squared(observed, location_weights)
        total_chi_squared += chi_squared
        total_degrees += location_fish_count - 1
        per_location.append({
            "region": region_name,
            "chi_squared": chi_squared,
            "p_value": p_value,
            "fish_count": location_fish_count,
        })

    joint_p_value = chi_squared_p_value(total_chi_squared, total_degrees)

    return {
        "percentages": percentage_vector,
        "joint_chi_squared": total_chi_squared,
        "joint_p_value": joint_p_value,
        "joint_degrees": total_degrees,
        "per_location": per_location,
        "passes": joint_p_value > 0.05,
    }


def format_percentages(percentages: tuple[int, ...]) -> str:
    """Format a percentage vector as a compact string."""
    return "/".join(f"{percentage}%" for percentage in percentages)


def main() -> None:
    tier_data = collect_tier_data()
    star_labels = {3: "★★★", 2: "★★", 1: "★"}
    step_sizes = [10, 5]
    step_labels = {10: "10% step", 5: "5% step"}
    step_colors = {10: "#e74c3c", 5: "#3498db"}

    figure = plt.figure(figsize=(20, 22))
    outer_grid = gridspec.GridSpec(3, 1, figure=figure, hspace=0.35)

    for tier_index, stars in enumerate([3, 2, 1]):
        locations_data = tier_data[stars]
        if len(locations_data) < 2:
            continue

        max_fish_count = max(len(fish_list) for _, fish_list in locations_data)
        location_names = [name for name, _ in locations_data]
        fish_counts = [len(fish_list) for _, fish_list in locations_data]

        # Get independent weight-based fits for comparison
        independent_fits = []
        for region_name, fish_list in locations_data:
            observed = [count for _, count in fish_list]
            weights, chi_squared, p_value = fit_integer_weights(observed)
            independent_fits.append({
                "region": region_name,
                "weights": tuple(weights),
                "chi_squared": chi_squared,
                "p_value": p_value,
            })

        # Try percentage vectors at each step size
        step_results: dict[int, list[dict]] = {}
        step_best: dict[int, dict] = {}

        for step in step_sizes:
            vectors = enumerate_percentage_vectors(max_fish_count, step)
            candidates = [
                compute_joint_fit(vector, locations_data)
                for vector in vectors
            ]

            step_results[step] = candidates

            passing = [candidate for candidate in candidates if candidate["passes"]]
            if passing:
                passing.sort(key=lambda candidate: candidate["joint_chi_squared"])
                step_best[step] = passing[0]
            else:
                candidates.sort(key=lambda candidate: candidate["joint_chi_squared"])
                step_best[step] = candidates[0]

        # Create subplot row: scatter + comparison
        inner_grid = gridspec.GridSpecFromSubplotSpec(
            1, 2, subplot_spec=outer_grid[tier_index],
            width_ratios=[1.5, 1], wspace=0.35,
        )

        # Left: scatter plot of all candidates by step size
        axis = figure.add_subplot(inner_grid[0])

        for step in step_sizes:
            candidates = step_results[step]
            passing = [candidate for candidate in candidates if candidate["passes"]]
            failing = [candidate for candidate in candidates if not candidate["passes"]]

            if failing:
                axis.scatter(
                    [step] * len(failing),
                    [candidate["joint_chi_squared"] for candidate in failing],
                    c="lightgray", s=15, alpha=0.3, zorder=1,
                )

            if passing:
                p_values = [candidate["joint_p_value"] for candidate in passing]
                scatter = axis.scatter(
                    [step] * len(passing),
                    [candidate["joint_chi_squared"] for candidate in passing],
                    c=p_values, cmap="RdYlGn", vmin=0.05, vmax=1.0,
                    s=35, alpha=0.7, edgecolors="black", linewidths=0.3,
                    zorder=2, label=f"{step_labels[step]} ({len(passing)} pass)"
                    if step == step_sizes[0] else None,
                )

            # Mark the best
            best = step_best[step]
            axis.scatter(
                [step], [best["joint_chi_squared"]],
                c="none", s=250, edgecolors=step_colors[step], linewidths=2.5,
                marker="D", zorder=3,
                label=f"Best {step_labels[step]}: {format_percentages(best['percentages'])}",
            )

        # Set axis labels
        all_passing = []
        for step in step_sizes:
            all_passing.extend(
                candidate for candidate in step_results[step]
                if candidate["passes"]
            )
        if all_passing:
            max_chi = max(candidate["joint_chi_squared"] for candidate in all_passing)
            y_margin = max(max_chi * 0.05, 0.1)
            axis.set_ylim(-y_margin, max_chi + y_margin * 3)

        axis.set_xticks(step_sizes)
        axis.set_xticklabels([step_labels[step] for step in step_sizes])
        axis.set_xlabel("Percentage granularity")
        axis.set_ylabel("Joint χ² (sum across locations)")

        tier_label = star_labels[stars]
        if len(set(fish_counts)) == 1:
            count_note = f"{fish_counts[0]} fish each"
        else:
            count_note = "/".join(str(count) for count in fish_counts) + " fish"
        axis.set_title(
            f"{tier_label} — Percentage fit across {len(locations_data)} locations"
            f" ({count_note})\n({', '.join(location_names)})",
            fontsize=10,
        )
        axis.legend(fontsize=7, loc="upper right")

        # Right: comparison text
        text_axis = figure.add_subplot(inner_grid[1])
        text_axis.axis("off")

        lines = [f"{tier_label} Tier — Percentage vs Weights\n"]

        # Independent weight fits
        lines.append("Independent weight fits (per location):")
        for fit_info in independent_fits:
            percentage_strings = []
            weight_sum = sum(fit_info["weights"])
            for weight in fit_info["weights"]:
                percentage_strings.append(f"{weight / weight_sum * 100:.1f}%")
            lines.append(
                f"  {fit_info['region']}: {fit_info['weights']}"
                f" → {'/'.join(percentage_strings)}"
            )
            lines.append(
                f"    χ²={fit_info['chi_squared']:.2f}  p={fit_info['p_value']:.3f}"
            )

        # Best at each step size
        for step in step_sizes:
            best = step_best[step]
            lines.append("")
            lines.append(f"Best {step_labels[step]}: {format_percentages(best['percentages'])}")
            total_candidates = len(step_results[step])
            total_passing = sum(
                1 for candidate in step_results[step] if candidate["passes"]
            )
            lines.append(
                f"  ({total_passing}/{total_candidates} candidates pass at p>0.05)"
            )
            for location_info in best["per_location"]:
                lines.append(
                    f"  {location_info['region']}:"
                    f" χ²={location_info['chi_squared']:.2f}"
                    f" p={location_info['p_value']:.3f}"
                )
            lines.append(
                f"  Joint: χ²={best['joint_chi_squared']:.2f}"
                f" p={best['joint_p_value']:.3f}"
            )

        # Fish assignments for best 5% fit
        best_fine = step_best[5]
        lines.append("")
        lines.append(f"Fish at {format_percentages(best_fine['percentages'])}:")
        for region_name, fish_list in locations_data:
            location_fish_count = len(fish_list)
            location_percentages = best_fine["percentages"][:location_fish_count]
            percentage_sum = sum(location_percentages)
            total = sum(count for _, count in fish_list)
            lines.append(f"  {region_name}:")
            for i, (fish_name, count) in enumerate(fish_list):
                percentage = location_percentages[i]
                expected = percentage / percentage_sum * 100
                observed = count / total * 100
                lines.append(
                    f"    {percentage}% {fish_name}:"
                    f" {observed:.0f}% (exp {expected:.0f}%)"
                )
            if location_fish_count < len(best_fine["percentages"]):
                extra = len(best_fine["percentages"]) - location_fish_count
                lowest = best_fine["percentages"][-1]
                lines.append(f"    (+ {extra} assumed at {lowest}%)")

        text_axis.text(
            0.02, 0.98, "\n".join(lines),
            transform=text_axis.transAxes,
            fontsize=7, fontfamily="monospace",
            verticalalignment="top",
        )

    figure.suptitle(
        "Experiment: Round-Percentage Drop Rate Templates\n"
        "Does the game use nice multiples of 5% or 10% for drop rates?",
        fontsize=13, fontweight="bold",
    )

    output_path = Path(__file__).parent / "percentage_fit_experiment.png"
    figure.savefig(output_path, dpi=100, bbox_inches="tight")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
