"""Run all sales update and visualization scripts.

update_sales already calls visualize_allocation internally for main figures.
The other visualize_* scripts generate experimental analysis PNGs.
"""

from update_sales import main as update_sales
from update_time import main as update_time
from visualize_percentage_fit import main as visualize_percentage_fit
from visualize_shared_weights import main as visualize_shared_weights
from visualize_weights import main as visualize_weights


def main() -> None:
    print("Updating sales (includes allocation figures)...")
    update_sales()

    print("Updating time stats...")
    update_time()

    print("Generating percentage fit visualization...")
    visualize_percentage_fit()

    print("Generating shared weights visualization...")
    visualize_shared_weights()

    print("Generating weights visualization...")
    visualize_weights()

    print("Done.")


if __name__ == "__main__":
    main()
