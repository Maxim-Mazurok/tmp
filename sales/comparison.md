# Location Comparison

Detected tier: 3 (Alamo Sea, Land Act Dam, Roxwood).

Bite wait by location: Alamo Sea 80s, Land Act Dam 90s, Roxwood 100s. Reel-in: 15s.

~ = estimated (not yet observed in catch data)

| Location     | Fish Caught | $/Fish observed | $/Fish model | Available Bundles                                     | $/Fish (bundles) | $/Fish total (obs) | $/Fish total (model) | $/Hour (model) |
|--------------|------------:|----------------:|-------------:|-------------------------------------------------------|-----------------:|-------------------:|---------------------:|---------------:|
| Alamo Sea    |         420 |          $1,472 |       $1,404 | Gold Multizone #1, Alamo Starter, Low Level Multizone |             $655 |             $2,127 |           **$2,059** |        $78,038 |
| Land Act Dam |         203 |          $1,670 |       $1,670 | Gold Multizone #1, Low Level Multizone                |             $393 |             $2,063 |           **$2,063** |        $70,733 |
| Roxwood      |         172 |          $1,804 |       $1,871 | Gold Multizone #1, Low Level Multizone                |             $205 |             $2,009 |           **$2,077** |        $65,005 |

## Optimal Allocation

Optimal time split across locations to maximize total $/hour (considering both sale value and cross-location bundle completions):

| Location     | Time % (obs) | $/Fish (obs) | $/Hour (obs) | Time % (model) | $/Fish (model) | $/Hour (model) |
|--------------|-------------:|-------------:|-------------:|---------------:|---------------:|---------------:|
| Alamo Sea    |          63% |       $1,472 |      $63,916 |            60% |         $1,404 |        $61,339 |
| Land Act Dam |          14% |       $1,670 |      $57,264 |            15% |         $1,670 |        $57,264 |
| Roxwood      |          23% |       $1,804 |      $56,475 |            25% |         $1,871 |        $58,574 |
| **Combined** |         100% |              |  **$65,710** |           100% |                |    **$64,610** |

**Observed:** splitting yields **$65,710**/hour vs **$63,916**/hour best solo (+$1,795/hour, +2.8%).
**Model:** splitting yields **$64,610**/hour vs **$61,339**/hour best solo (+$3,271/hour, +5.3%).

## Bundle Details

### Alamo Sea

| Bundle        | Fish                                     |   Bonus | Avg Fish to Complete | Avg Time | Bonus/Fish | Catch Rates                                                                              |
|---------------|------------------------------------------|--------:|---------------------:|---------:|-----------:|------------------------------------------------------------------------------------------|
| Alamo Starter | Morwhong, Southern Tuna, Silver Trevally | $10,000 |                   57 |   91 min |       $174 | Morwhong: 27/420 (6.4%) \| Southern Tuna: 9/420 (2.1%) \| Silver Trevally: 17/420 (4.0%) |

### Cross-Location

| Bundle              | Fish                             |   Bonus | Avg Fish to Complete | Avg Time | Bonus/Fish | Catch Rates                                                                                                          |
|---------------------|----------------------------------|--------:|---------------------:|---------:|-----------:|----------------------------------------------------------------------------------------------------------------------|
| Gold Multizone #1   | Bluefin Tuna, Musky, Dolphinfish | $12,750 |                  201 |  336 min |        $63 | Bluefin Tuna @ Alamo Sea: 3/420 (0.7%) \| Musky @ Land Act Dam: 11/203 (5.4%) \| Dolphinfish @ Roxwood: 4/172 (2.3%) |
| Low Level Multizone | Scollop, Carp, Grenadier         | $11,000 |                   66 |  120 min |       $167 | Scollop @ Alamo Sea: 47/420 (11.2%) \| Carp @ Land Act Dam: 9/203 (4.4%) \| Grenadier @ Roxwood: 5/172 (2.9%)        |

## Drop Rate Analysis

### Tier Distribution

Tier drop rates are consistent across locations, suggesting a fixed game mechanic:

| Tier        | Alamo Sea | Land Act Dam | Roxwood | Average |
|-------------|----------:|-------------:|--------:|--------:|
| ★★★★ purple |      0.2% |         0.0% |    0.0% |    0.1% |
| ★★★         |      6.4% |        11.3% |    8.7% |    8.8% |
| ★★          |     26.4% |        27.6% |   32.6% |   28.9% |
| ★           |     65.5% |        61.1% |   58.7% |   61.8% |

### Within-Tier Weights

Observed frequencies vs model (percentage template) per fish.
Model uses shared percentage templates across all locations (5% granularity).

#### Alamo Sea — ★★★ (3 fish, 27 observed)

| Fish            | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|-----------------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| Silver Trevally |    17 |      63.0% |      3 |    60.0% |     55% |          55.0% |     +2.2 |
| Great Barracuda |     7 |      25.9% |      1 |    20.0% |     30% |          30.0% |     -1.1 |
| Bluefin Tuna    |     3 |      11.1% |      1 |    20.0% |     15% |          15.0% |     -1.0 |

Weight fit: χ² = 1.58, df = 2, p = 0.454 — good
Model fit (55%/30%/15%): χ² = 0.73, p = 0.693 — excellent

#### Alamo Sea — ★★ (6 fish, 111 observed)

| Fish             | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|------------------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| Southern Garfish |    30 |      27.0% |      5 |    23.8% |     25% |          25.0% |     +2.2 |
| Trout            |    25 |      22.5% |      5 |    23.8% |     20% |          20.0% |     +2.8 |
| Blue Warehou     |    24 |      21.6% |      5 |    23.8% |     20% |          20.0% |     +1.8 |
| Golden Perch     |    12 |      10.8% |      2 |     9.5% |     15% |          15.0% |     -4.6 |
| Snow Crab        |    11 |       9.9% |      2 |     9.5% |     10% |          10.0% |     -0.1 |
| Southern Tuna    |     9 |       8.1% |      2 |     9.5% |     10% |          10.0% |     -2.1 |

Weight fit: χ² = 1.23, df = 5, p = 0.942 — excellent
Model fit (25%/20%/20%/15%/10%/10%): χ² = 2.38, p = 0.795 — excellent

#### Alamo Sea — ★ (7 fish, 275 observed)

| Fish      | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|-----------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| Albacore  |    63 |      22.9% |      7 |    22.6% |     20% |          21.1% |     +5.1 |
| Scollop   |    47 |      17.1% |      5 |    16.1% |     15% |          15.8% |     +3.6 |
| Halibut   |    43 |      15.6% |      5 |    16.1% |     15% |          15.8% |     -0.4 |
| Broadbill |    42 |      15.3% |      5 |    16.1% |     15% |          15.8% |     -1.4 |
| Morwhong  |    27 |       9.8% |      3 |     9.7% |     10% |          10.5% |     -1.9 |
| Flathead  |    27 |       9.8% |      3 |     9.7% |     10% |          10.5% |     -1.9 |
| Redfish   |    26 |       9.5% |      3 |     9.7% |     10% |          10.5% |     -2.9 |

Weight fit: χ² = 0.36, df = 6, p = 0.999 — excellent
Model fit (20%/15%/15%/15%/10%/10%/10%/5%): χ² = 1.36, p = 0.968 — excellent

#### Land Act Dam — ★★★ (3 fish, 23 observed)

| Fish          | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|---------------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| Musky         |    11 |      47.8% |      7 |    41.2% |     55% |          55.0% |     -1.7 |
| Pike          |     8 |      34.8% |      7 |    41.2% |     30% |          30.0% |     +1.1 |
| Rainbow Trout |     4 |      17.4% |      3 |    17.6% |     15% |          15.0% |     +0.5 |

Weight fit: χ² = 0.48, df = 2, p = 0.788 — excellent
Model fit (55%/30%/15%): χ² = 0.48, p = 0.787 — excellent

#### Land Act Dam — ★★ (6 fish, 56 observed)

| Fish            | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|-----------------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| Atlantic Salmon |    12 |      21.4% |      1 |    16.7% |     25% |          25.0% |     -2.0 |
| Trevella        |    10 |      17.9% |      1 |    16.7% |     20% |          20.0% |     -1.2 |
| Wahoo           |     9 |      16.1% |      1 |    16.7% |     20% |          20.0% |     -2.2 |
| Sturgeon        |     9 |      16.1% |      1 |    16.7% |     15% |          15.0% |     +0.6 |
| Carp            |     9 |      16.1% |      1 |    16.7% |     10% |          10.0% |     +3.4 |
| Trumpetfish     |     7 |      12.5% |      1 |    16.7% |     10% |          10.0% |     +1.4 |

Weight fit: χ² = 1.43, df = 5, p = 0.921 — excellent
Model fit (25%/20%/20%/15%/10%/10%): χ² = 3.30, p = 0.653 — excellent

#### Land Act Dam — ★ (8 fish, 124 observed)

| Fish             | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|------------------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| Murray Cod       |    32 |      25.8% |      7 |    25.9% |     20% |          20.0% |     +7.2 |
| Banded Butterfly |    21 |      16.9% |      4 |    14.8% |     15% |          15.0% |     +2.4 |
| Sand Whiting     |    19 |      15.3% |      4 |    14.8% |     15% |          15.0% |     +0.4 |
| Triggerfish      |    14 |      11.3% |      4 |    14.8% |     15% |          15.0% |     -4.6 |
| Cod              |    11 |       8.9% |      2 |     7.4% |     10% |          10.0% |     -1.4 |
| Black Bream      |    10 |       8.1% |      2 |     7.4% |     10% |          10.0% |     -2.4 |
| Escolar          |    10 |       8.1% |      2 |     7.4% |     10% |          10.0% |     -2.4 |
| Brook Trout      |     7 |       5.6% |      2 |     7.4% |      5% |           5.0% |     +0.8 |

Weight fit: χ² = 2.46, df = 7, p = 0.930 — excellent
Model fit (20%/15%/15%/15%/10%/10%/10%/5%): χ² = 4.74, p = 0.692 — excellent

#### Roxwood — ★★★ (3 fish, 15 observed)

| Fish          | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|---------------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| King Mackerel |     6 |      40.0% |      1 |    33.3% |     55% |          55.0% |     -2.2 |
| Grenadier     |     5 |      33.3% |      1 |    33.3% |     30% |          30.0% |     +0.5 |
| Dolphinfish   |     4 |      26.7% |      1 |    33.3% |     15% |          15.0% |     +1.8 |

Weight fit: χ² = 0.40, df = 2, p = 0.819 — excellent
Model fit (55%/30%/15%): χ² = 2.03, p = 0.362 — good

#### Roxwood — ★★ (6 fish, 56 observed)

| Fish         | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|--------------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| Snapper      |    15 |      26.8% |      9 |    23.1% |     25% |          25.0% |     +1.0 |
| Silver Perch |    12 |      21.4% |      9 |    23.1% |     20% |          20.0% |     +0.8 |
| Amberjack    |    12 |      21.4% |      9 |    23.1% |     20% |          20.0% |     +0.8 |
| Gummy Shark  |     7 |      12.5% |      4 |    10.3% |     15% |          15.0% |     -1.4 |
| Brown Trout  |     7 |      12.5% |      4 |    10.3% |     10% |          10.0% |     +1.4 |
| Red Snapper  |     3 |       5.4% |      4 |    10.3% |     10% |          10.0% |     -2.6 |

Weight fit: χ² = 2.33, df = 5, p = 0.802 — excellent
Model fit (25%/20%/20%/15%/10%/10%): χ² = 1.98, p = 0.852 — excellent

#### Roxwood — ★ (7 fish, 101 observed)

| Fish               | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|--------------------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| Grouper            |    35 |      34.7% |      9 |    33.3% |     20% |          21.1% |    +13.7 |
| Dungeness Crab     |    17 |      16.8% |      4 |    14.8% |     15% |          15.8% |     +1.1 |
| Sandy Sprat        |    15 |      14.9% |      4 |    14.8% |     15% |          15.8% |     -0.9 |
| Ocean Perch        |    13 |      12.9% |      4 |    14.8% |     15% |          15.8% |     -2.9 |
| Australian Herring |     9 |       8.9% |      2 |     7.4% |     10% |          10.5% |     -1.6 |
| Sand Whiting       |     6 |       5.9% |      2 |     7.4% |     10% |          10.5% |     -4.6 |
| Ocean Jacket       |     6 |       5.9% |      2 |     7.4% |     10% |          10.5% |     -4.6 |

Weight fit: χ² = 1.48, df = 6, p = 0.961 — excellent
Model fit (20%/15%/15%/15%/10%/10%/10%/5%): χ² = 13.83, p = 0.032 — poor
