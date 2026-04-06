"""Run all sales update and visualization scripts.

update_sales already calls visualize_allocation internally for main figures.
The other visualize_* scripts generate experimental analysis PNGs.
"""

import sys
from pathlib import Path

# Add weights dir so we can import extract_weights
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "weights"))

from extract_weights import main as extract_fish_weights
from update_sales import main as update_sales
from update_time import main as update_time
from value_per_gram import main as update_weights
from visualize_percentage_fit import main as visualize_percentage_fit
from visualize_shared_weights import main as visualize_shared_weights
from visualize_weights import main as visualize_weights


def main() -> None:
    print("Extracting fish weights from screenshots...")
    extract_fish_weights()

    print("Updating sales (includes allocation figures)...")
    update_sales()

    print("Updating time stats...")
    update_time()

    print("Updating fish value-per-gram analysis...")
    update_weights()

    print("Generating percentage fit visualization...")
    visualize_percentage_fit()

    print("Generating shared weights visualization...")
    visualize_shared_weights()

    print("Generating weights visualization...")
    visualize_weights()

    print("Done.")


if __name__ == "__main__":
    main()
