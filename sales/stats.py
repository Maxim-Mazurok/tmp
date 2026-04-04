"""Statistical helpers: chi-squared goodness-of-fit and integer weight fitting."""

import math


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


def chi_squared_p_value(statistic: float, degrees_of_freedom: int) -> float:
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
            p_value = chi_squared_p_value(chi_squared, degrees_of_freedom)
            candidates.append((total_weight, weights, chi_squared, p_value))
            return

        for weight in range(1, max_allowed + 1):
            search(group_index + 1, weight, current_group_weights + [weight])

    search(0, max_weight, [])

    passing = [candidate for candidate in candidates if candidate[3] > 0.05]
    if passing:
        # AIC-like scoring: balance fit quality vs complexity.
        # Complexity = distinct_weights - 1
        # Penalizes variety of weights, not magnitude.
        # (3,1,1) and (2,1,1) have the same complexity.
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


def fit_percentage_template(
    observed_counts: list[int],
    template: tuple[int, ...],
) -> tuple[list[int], float, float]:
    """Fit a percentage template to observed data.

    Assigns template percentages to fish sorted by descending count.
    Returns (assigned_percentages, chi_squared, p_value).
    If the template has more slots than observed fish, only the first N
    entries are used (renormalized).
    """
    fish_count = len(observed_counts)
    total = sum(observed_counts)
    degrees_of_freedom = fish_count - 1

    percentages = list(template[:fish_count])
    percentage_sum = sum(percentages)

    expected = [total * percentage / percentage_sum for percentage in percentages]
    chi_squared_value = sum(
        (observed_counts[i] - expected[i]) ** 2 / expected[i]
        for i in range(fish_count)
        if expected[i] > 0
    )
    p_value = chi_squared_p_value(chi_squared_value, degrees_of_freedom)

    return percentages, chi_squared_value, p_value
