"""Data constants for the fishing sales analysis."""

from pathlib import Path
from typing import TypedDict

SALES_DIR = Path(__file__).parent

REGIONS = {
    "alamo": "Alamo Sea",
    "dam": "Dam",
    "roxwood": "Roxwood",
    "ocean": "Ocean",
    "cave": "Cave",
    "humane-labs": "Humane Labs",
}


class BundleInfo(TypedDict):
    fish: list[str]
    bonus: int


BUNDLES: dict[str, BundleInfo] = {
    "Bronze Multizone #1": {"fish": ["Dutch Fish", "Ocean Perch", "Broadbill"], "bonus": 10750},
    "Bronze Multizone #2": {"fish": ["Brook Trout", "Pufferfish", "Green Eel"], "bonus": 11000},
    "Silver Multizone #1": {"fish": ["Swordfish", "Blue Warehou", "Stingray"], "bonus": 12500},
    "Silver Multizone #2": {"fish": ["Trevella", "Red Snapper", "Oreo Dory"], "bonus": 12250},
    "Gold Multizone #1": {"fish": ["Bluefin Tuna", "Musky", "Dolphinfish"], "bonus": 12750},
    "Gold Multizone #2": {"fish": ["Blue Marlin", "Blobfish", "Whale Shark"], "bonus": 15000},
    "Alamo Starter": {"fish": ["Morwhong", "Southern Tuna", "Silver Trevally"], "bonus": 10000},
    "Low Level Multizone": {"fish": ["Scollop", "Carp", "Grenadier"], "bonus": 11000},
}

# Fish prices: name -> (price, star_count, star_color)
# star_color: "" for regular, "green" for green, "purple" for purple
PRICES: dict[str, tuple[int, int, str]] = {
    "Whale Shark": (2850, 3, "green"),
    "Greenback Flounder": (2350, 2, ""),
    "Flathead": (1350, 1, ""),
    "Dolphinfish": (2350, 3, ""),
    "Silver Perch": (2000, 2, ""),
    "Orange Roughy": (2150, 1, "green"),
    "Mulloway": (2150, 1, "green"),
    "Snapper": (2000, 2, ""),
    "Blackfin Tuna": (2150, 1, "green"),
    "Oreo Dory": (2350, 2, ""),
    "Ling": (2350, 2, ""),
    "Atlantic Wolffish": (2150, 1, "green"),
    "Archerfish": (2500, 2, "green"),
    "Dover Sole": (2500, 2, "green"),
    "Boarfish": (1850, 1, ""),
    "Flounder": (2000, 1, ""),
    "Shortfin Batfish": (1850, 1, ""),
    "King Whiting": (2650, 3, ""),
    "Black Marlin": (2500, 3, ""),
    "Sockeye Salmon": (2150, 1, "green"),
    "Escolar": (1500, 1, ""),
    "Snow Crab": (1650, 2, ""),
    "Wahoo": (1850, 2, ""),
    "Chadfin": (8150, 0, ""),
    "John Dory": (2500, 2, "green"),
    "Green Eel": (2000, 1, ""),
    "Toadfish": (2000, 1, ""),
    "Sailfish": (2850, 3, "green"),
    "Dungeness Crab": (1650, 1, ""),
    "Southern Tuna": (1650, 2, ""),
    "Murray Cod": (1500, 1, ""),
    "Atlantic Salmon": (1850, 2, ""),
    "Gummy Shark": (2000, 2, ""),
    "Australian Herring": (1650, 1, ""),
    "Morwhong": (1350, 1, ""),
    "Yellow Tail": (2150, 2, ""),
    "Anglerfish": (2650, 3, ""),
    "Viperfish": (2000, 1, ""),
    "Australian Anchovy": (1850, 1, ""),
    "Sculpin": (2000, 1, ""),
    "Trout": (1650, 2, ""),
    "Yellowfin Tuna": (2850, 3, "green"),
    "Pollock": (1850, 1, ""),
    "Sand Whiting": (1500, 1, ""),
    "Great Barracuda": (2000, 3, ""),
    "Ocean Jacket": (1650, 1, ""),
    "Stingray": (2150, 2, ""),
    "Swordfish": (2500, 2, "green"),
    "Tiger Flathead": (2000, 1, ""),
    "Pufferfish": (1850, 1, ""),
    "Sturgeon": (1850, 2, ""),
    "Southern Garfish": (1650, 2, ""),
    "Cavefish": (2350, 2, ""),
    "Blue Marlin": (2500, 3, ""),
    "Blobfish": (2650, 3, ""),
    "Gemfish": (2500, 2, "green"),
    "Speckled Sea Trout": (2150, 2, ""),
    "Sunfish": (2500, 3, ""),
    "Snake Eel": (2350, 2, ""),
    "3 Eyed Fish": (10_000, 4, "purple"),
    "Silver Trevally": (2000, 3, ""),
    "Trumpetfish": (1850, 2, ""),
    "Red Snapper": (2000, 2, ""),
    "Black Bream": (1500, 1, ""),
    "Salmon": (2150, 2, ""),
    "Clownfish": (1650, 1, ""),
    "Sandy Sprat": (1350, 1, ""),
    "Triggerfish": (1500, 1, ""),
    "Dutch Fish": (2150, 1, "green"),
    "Ocean Perch": (1650, 1, ""),
    "Scollop": (1350, 1, ""),
    "King Mackerel": (2350, 3, ""),
    "Blue Tang": (2150, 1, "green"),
    "Pufferfish w/ Carrot": (10_000, 4, "purple"),
    "Rainbow Trout": (2150, 3, ""),
    "Haddock": (1850, 1, ""),
    "Albacore": (1350, 1, ""),
    "Brown Trout": (2000, 2, ""),
    "Bluefin Tuna": (2000, 3, ""),
    "Blue Warehou": (1650, 2, ""),
    "Lion Fish": (1850, 1, ""),
    "Banded Butterfly": (1500, 1, ""),
    "Baby Pufferfish": (10_000, 4, "purple"),
    "Bluehead Wrasse": (2150, 1, "green"),
    "Carp": (1850, 2, ""),
    "Amberjack": (2150, 2, ""),
    "Barramundi": (1650, 1, ""),
    "Hogfish": (2500, 2, "green"),
    "Catfish": (2000, 1, ""),
    "Brook Trout": (1500, 1, ""),
    "Pike": (2150, 3, ""),
    "Blue Crab": (2000, 1, ""),
    "Halibut": (1350, 1, ""),
    "Broadbill": (1350, 1, ""),
    "Musky": (2150, 3, ""),
    "Grouper": (1650, 1, ""),
    "Grenadier": (2350, 3, ""),
    "Redfish": (1350, 1, ""),
    "Brown Eel": (2350, 2, ""),
    "Trevella": (1850, 2, ""),
    "Australian Pilchard": (1850, 1, ""),
    "Cod": (1500, 1, ""),
    "Golden Perch": (1650, 2, ""),
}

TIER_PRICES = {
    "Alamo Sea":    {1: 1350, 2: 1650, 3: 2000},
    "Dam": {1: 1500, 2: 1850, 3: 2150},
    "Roxwood":      {1: 1650, 2: 2000, 3: 2350},
    "Ocean":        {1: 1850, 2: 2150, 3: 2500},
    "Cave":         {1: 2000, 2: 2350, 3: 2650},
    "Humane Labs":  {1: 2150, 2: 2500, 3: 2850},
}

# Manual notes for special fish sightings (weather, etc.)
SPECIAL_FISH_NOTES: dict[str, str] = {
    "3 Eyed Fish": "heavy storm",
}

# Time per fish (seconds) – bite wait varies by location
SECONDS_WAITING_FOR_BITE: dict[str, int] = {
    "Alamo Sea": 90,
    "Dam": 90,
    "Roxwood": 100,
}
SECONDS_WAITING_FOR_BITE_DEFAULT = 100  # for unknown locations
SECONDS_REELING_IN: dict[str, int] = {
    "Alamo Sea": 15,
    "Dam": 115 - SECONDS_WAITING_FOR_BITE["Dam"],
    "Roxwood": 30,
}
SECONDS_REELING_IN_DEFAULT = 30  # for unknown locations


def seconds_per_fish(location: str) -> int:
    """Total seconds per fish at a given location."""
    waiting = SECONDS_WAITING_FOR_BITE.get(location, SECONDS_WAITING_FOR_BITE_DEFAULT)
    reeling = SECONDS_REELING_IN.get(location, SECONDS_REELING_IN_DEFAULT)
    return waiting + reeling


def fish_per_hour(location: str) -> float:
    """Fish catchable per hour at a given location."""
    return 3600 / seconds_per_fish(location)

# Reverse lookup: fish name -> list of bundle names
FISH_BUNDLES: dict[str, list[str]] = {}
for _bundle_name, _bundle_info in BUNDLES.items():
    for _fish_name in _bundle_info["fish"]:
        FISH_BUNDLES.setdefault(_fish_name, []).append(_bundle_name)

LOCATION_ORDER = list(REGIONS.values())

# Best-fit drop rate percentage templates per star tier.
# Derived from joint percentage fitting across all observed locations.
# Each tuple sums to 100 and uses 5% step granularity.
# Fish are assigned in descending order of observed frequency.
# Locations with fewer fish than the template use the first N entries.
TIER_DROP_PERCENTAGES: dict[int, tuple[int, ...]] = {
    3: (55, 30, 15),                     # ★★★: 3 fish
    2: (25, 20, 20, 15, 10, 10),         # ★★:  6 fish
    1: (20, 15, 15, 15, 10, 10, 10, 5),  # ★:   7-8 fish
}
