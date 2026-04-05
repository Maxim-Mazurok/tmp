# Location Comparison

Detected tier: 3 (Alamo Sea, Dam, Roxwood).

Bite wait by location: Alamo Sea 90s, Dam 90s, Roxwood 100s. Reel-in by location: Alamo Sea 15s, Dam 25s, Roxwood 30s.

~ = estimated (not yet observed in catch data)

| Location  | Fish Caught | $/Fish observed | $/Fish model | Available Bundles                                     | $/Fish (bundles) | $/Fish total (obs) | $/Fish total (model) | $/Hour (model) |
|-----------|------------:|----------------:|-------------:|-------------------------------------------------------|-----------------:|-------------------:|---------------------:|---------------:|
| Alamo Sea |         420 |          $1,472 |       $1,404 | Gold Multizone #1, Alamo Starter, Low Level Multizone |             $655 |             $2,127 |           **$2,059** |        $70,606 |
| Dam       |         335 |          $1,664 |       $1,664 | Gold Multizone #1, Low Level Multizone                |             $369 |             $2,033 |           **$2,033** |        $63,644 |
| Roxwood   |         172 |          $1,804 |       $1,871 | Gold Multizone #1, Low Level Multizone                |             $205 |             $2,009 |           **$2,077** |        $57,504 |

## Optimal Allocation

Optimal time split across locations to maximize total $/hour (considering both sale value and cross-location bundle completions):

| Location     | Time % (obs) | $/Fish (obs) | $/Hour (obs) | Time % (model) | $/Fish (model) | $/Hour (model) |
|--------------|-------------:|-------------:|-------------:|---------------:|---------------:|---------------:|
| Alamo Sea    |          63% |       $1,472 |      $57,829 |            61% |         $1,404 |        $55,497 |
| Dam          |          14% |       $1,664 |      $52,096 |            15% |         $1,664 |        $52,096 |
| Roxwood      |          23% |       $1,804 |      $49,959 |            24% |         $1,871 |        $51,816 |
| **Combined** |         100% |              |  **$59,119** |           100% |                |    **$58,133** |

**Observed:** splitting yields **$59,119**/hour vs **$57,829**/hour best solo (+$1,291/hour, +2.2%).
**Model:** splitting yields **$58,133**/hour vs **$55,497**/hour best solo (+$2,636/hour, +4.8%).

## Bundle Details

### Alamo Sea

| Bundle        | Fish                                     |   Bonus | Avg Fish to Complete | Avg Time | Bonus/Fish | Catch Rates                                                                              |
|---------------|------------------------------------------|--------:|---------------------:|---------:|-----------:|------------------------------------------------------------------------------------------|
| Alamo Starter | Morwhong, Southern Tuna, Silver Trevally | $10,000 |                   57 |  101 min |       $174 | Morwhong: 27/420 (6.4%) \| Southern Tuna: 9/420 (2.1%) \| Silver Trevally: 17/420 (4.0%) |

### Cross-Location

| Bundle              | Fish                             |   Bonus | Avg Fish to Complete | Avg Time | Bonus/Fish | Catch Rates                                                                                                 |
|---------------------|----------------------------------|--------:|---------------------:|---------:|-----------:|-------------------------------------------------------------------------------------------------------------|
| Gold Multizone #1   | Bluefin Tuna, Musky, Dolphinfish | $12,750 |                  203 |  376 min |        $63 | Bluefin Tuna @ Alamo Sea: 3/420 (0.7%) \| Musky @ Dam: 17/335 (5.1%) \| Dolphinfish @ Roxwood: 4/172 (2.3%) |
| Low Level Multizone | Scollop, Carp, Grenadier         | $11,000 |                   67 |  136 min |       $164 | Scollop @ Alamo Sea: 47/420 (11.2%) \| Carp @ Dam: 14/335 (4.2%) \| Grenadier @ Roxwood: 5/172 (2.9%)       |

## Drop Rate Analysis

### Tier Distribution

Tier drop rates are consistent across locations, suggesting a fixed game mechanic:

| Tier        | Alamo Sea |   Dam | Roxwood | Average |
|-------------|----------:|------:|--------:|--------:|
| ★★★★ purple |      0.2% |  0.0% |    0.0% |    0.1% |
| ★★★         |      6.4% | 10.1% |    8.7% |    8.4% |
| ★★          |     26.4% | 28.1% |   32.6% |   29.0% |
| ★           |     65.5% | 61.8% |   58.7% |   62.0% |

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

#### Dam — ★★★ (3 fish, 34 observed)

| Fish          | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|---------------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| Musky         |    17 |      50.0% |      2 |    50.0% |     55% |          55.0% |     -1.7 |
| Pike          |    10 |      29.4% |      1 |    25.0% |     30% |          30.0% |     -0.2 |
| Rainbow Trout |     7 |      20.6% |      1 |    25.0% |     15% |          15.0% |     +1.9 |

Weight fit: χ² = 0.53, df = 2, p = 0.767 — excellent
Model fit (55%/30%/15%): χ² = 0.87, p = 0.648 — excellent

#### Dam — ★★ (6 fish, 94 observed)

| Fish            | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|-----------------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| Atlantic Salmon |    23 |      24.5% |      8 |    22.2% |     25% |          25.0% |     -0.5 |
| Trevella        |    19 |      20.2% |      8 |    22.2% |     20% |          20.0% |     +0.2 |
| Trumpetfish     |    16 |      17.0% |      5 |    13.9% |     20% |          20.0% |     -2.8 |
| Carp            |    14 |      14.9% |      5 |    13.9% |     15% |          15.0% |     -0.1 |
| Wahoo           |    12 |      12.8% |      5 |    13.9% |     10% |          10.0% |     +2.6 |
| Sturgeon        |    10 |      10.6% |      5 |    13.9% |     10% |          10.0% |     +0.6 |

Weight fit: χ² = 1.92, df = 5, p = 0.861 — excellent
Model fit (25%/20%/20%/15%/10%/10%): χ² = 1.19, p = 0.946 — excellent

#### Dam — ★ (8 fish, 207 observed)

| Fish             | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|------------------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| Murray Cod       |    50 |      24.2% |      5 |    23.8% |     20% |          20.0% |     +8.6 |
| Banded Butterfly |    35 |      16.9% |      3 |    14.3% |     15% |          15.0% |     +3.9 |
| Triggerfish      |    28 |      13.5% |      3 |    14.3% |     15% |          15.0% |     -3.1 |
| Sand Whiting     |    26 |      12.6% |      3 |    14.3% |     15% |          15.0% |     -5.1 |
| Cod              |    23 |      11.1% |      2 |     9.5% |     10% |          10.0% |     +2.3 |
| Escolar          |    19 |       9.2% |      2 |     9.5% |     10% |          10.0% |     -1.7 |
| Brook Trout      |    16 |       7.7% |      2 |     9.5% |     10% |          10.0% |     -4.7 |
| Black Bream      |    10 |       4.8% |      1 |     4.8% |      5% |           5.0% |     -0.3 |

Weight fit: χ² = 2.80, df = 7, p = 0.903 — excellent
Model fit (20%/15%/15%/15%/10%/10%/10%/5%): χ² = 4.88, p = 0.674 — excellent

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
