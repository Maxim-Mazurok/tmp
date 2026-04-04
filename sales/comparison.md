# Location Comparison

Detected tier: 3 (Alamo Sea, Land Act Dam, Roxwood).

Assuming 100s wait for bite + 15s reel-in = 115s per fish (31.3 fish/hour).

~ = estimated (not yet observed in catch data)

| Location     | Fish Caught | $/Fish observed | $/Fish model | Available Bundles                                     | $/Fish (bundles) | $/Fish total (obs) | $/Fish total (model) | $/Hour (model) |
|--------------|------------:|----------------:|-------------:|-------------------------------------------------------|-----------------:|-------------------:|---------------------:|---------------:|
| Alamo Sea    |         420 |          $1,472 |       $1,404 | Gold Multizone #1, Alamo Starter, Low Level Multizone |             $655 |             $2,127 |           **$2,059** |        $64,466 |
| Land Act Dam |         203 |          $1,670 |       $1,670 | Gold Multizone #1, Low Level Multizone                |             $393 |             $2,063 |           **$2,063** |        $64,583 |
| Roxwood      |          78 |          $1,785 |       $1,862 | Gold Multizone #1, Low Level Multizone                |             $196 |             $1,980 |           **$2,058** |        $64,418 |

## Optimal Allocation

Optimal time split across locations to maximize total $/hour (considering both sale value and cross-location bundle completions):

| Location     | Time % (obs) | $/Fish (obs) | $/Hour (obs) | Time % (model) | $/Fish (model) | $/Hour (model) |
|--------------|-------------:|-------------:|-------------:|---------------:|---------------:|---------------:|
| Alamo Sea    |          16% |       $1,472 |      $52,800 |            16% |         $1,404 |        $50,671 |
| Land Act Dam |          39% |       $1,670 |      $52,284 |            39% |         $1,670 |        $52,284 |
| Roxwood      |          45% |       $1,785 |      $55,866 |            45% |         $1,862 |        $58,298 |
| **Combined** |         100% |              |  **$60,389** |           100% |                |    **$61,143** |

**Observed:** splitting yields **$60,389**/hour vs **$55,866**/hour best solo (+$4,523/hour, +8.1%).
**Model:** splitting yields **$61,143**/hour vs **$58,298**/hour best solo (+$2,845/hour, +4.9%).

## Bundle Details

### Alamo Sea

| Bundle        | Fish                                     |   Bonus | Avg Fish to Complete | Avg Time | Bonus/Fish | Catch Rates                                                                              |
|---------------|------------------------------------------|--------:|---------------------:|---------:|-----------:|------------------------------------------------------------------------------------------|
| Alamo Starter | Morwhong, Southern Tuna, Silver Trevally | $10,000 |                   57 |  110 min |       $174 | Morwhong: 27/420 (6.4%) \| Southern Tuna: 9/420 (2.1%) \| Silver Trevally: 17/420 (4.0%) |

### Cross-Location

| Bundle              | Fish                             |   Bonus | Avg Fish to Complete | Avg Time | Bonus/Fish | Catch Rates                                                                                                         |
|---------------------|----------------------------------|--------:|---------------------:|---------:|-----------:|---------------------------------------------------------------------------------------------------------------------|
| Gold Multizone #1   | Bluefin Tuna, Musky, Dolphinfish | $12,750 |                  236 |  453 min |        $54 | Bluefin Tuna @ Alamo Sea: 3/420 (0.7%) \| Musky @ Land Act Dam: 11/203 (5.4%) \| Dolphinfish @ Roxwood: 1/78 (1.3%) |
| Low Level Multizone | Scollop, Carp, Grenadier         | $11,000 |                   57 |  110 min |       $191 | Scollop @ Alamo Sea: 47/420 (11.2%) \| Carp @ Land Act Dam: 9/203 (4.4%) \| Grenadier @ Roxwood: 3/78 (3.8%)        |

## Drop Rate Analysis

### Tier Distribution

Tier drop rates are consistent across locations, suggesting a fixed game mechanic:

| Tier        | Alamo Sea | Land Act Dam | Roxwood | Average |
|-------------|----------:|-------------:|--------:|--------:|
| ★★★★ purple |      0.2% |         0.0% |    0.0% |    0.1% |
| ★★★         |      6.4% |        11.3% |   10.3% |    9.3% |
| ★★          |     26.4% |        27.6% |   29.5% |   27.8% |
| ★           |     65.5% |        61.1% |   60.3% |   62.3% |

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

#### Roxwood — ★★★ (3 fish, 8 observed)

| Fish          | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|---------------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| King Mackerel |     4 |      50.0% |      1 |    33.3% |     55% |          55.0% |     -0.4 |
| Grenadier     |     3 |      37.5% |      1 |    33.3% |     30% |          30.0% |     +0.6 |
| Dolphinfish   |     1 |      12.5% |      1 |    33.3% |     15% |          15.0% |     -0.2 |

Weight fit: χ² = 1.75, df = 2, p = 0.417 — good
Model fit (55%/30%/15%): χ² = 0.22, p = 0.896 — excellent

#### Roxwood — ★★ (6 fish, 23 observed)

| Fish         | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|--------------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| Snapper      |     5 |      21.7% |      9 |    19.1% |     25% |          25.0% |     -0.8 |
| Amberjack    |     5 |      21.7% |      9 |    19.1% |     20% |          20.0% |     +0.4 |
| Brown Trout  |     5 |      21.7% |      9 |    19.1% |     20% |          20.0% |     +0.4 |
| Gummy Shark  |     4 |      17.4% |      9 |    19.1% |     15% |          15.0% |     +0.5 |
| Silver Perch |     3 |      13.0% |      9 |    19.1% |     10% |          10.0% |     +0.7 |
| Red Snapper  |     1 |       4.3% |      2 |     4.3% |     10% |          10.0% |     -1.3 |

Weight fit: χ² = 0.73, df = 5, p = 0.981 — excellent
Model fit (25%/20%/20%/15%/10%/10%): χ² = 1.20, p = 0.945 — excellent

#### Roxwood — ★ (7 fish, 47 observed)

| Fish               | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|--------------------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| Grouper            |    14 |      29.8% |     10 |    23.8% |     20% |          21.1% |     +4.1 |
| Sandy Sprat        |    11 |      23.4% |     10 |    23.8% |     15% |          15.8% |     +3.6 |
| Dungeness Crab     |     8 |      17.0% |     10 |    23.8% |     15% |          15.8% |     +0.6 |
| Australian Herring |     4 |       8.5% |      3 |     7.1% |     15% |          15.8% |     -3.4 |
| Sand Whiting       |     4 |       8.5% |      3 |     7.1% |     10% |          10.5% |     -0.9 |
| Ocean Jacket       |     3 |       6.4% |      3 |     7.1% |     10% |          10.5% |     -1.9 |
| Ocean Perch        |     3 |       6.4% |      3 |     7.1% |     10% |          10.5% |     -1.9 |

Weight fit: χ² = 1.94, df = 6, p = 0.925 — excellent
Model fit (20%/15%/15%/15%/10%/10%/10%/5%): χ² = 6.77, p = 0.343 — good
