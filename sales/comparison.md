# Location Comparison

Detected tier: 3 (Alamo Sea, Dam, Roxwood).

Bite wait by location: Alamo Sea 90s, Dam 90s, Roxwood 100s. Reel-in by location: Alamo Sea 23s, Dam 27s, Roxwood 41s.

~ = estimated (not yet observed in catch data)

| Location  | Fish Caught | $/Fish observed | $/Fish model | Available Bundles                                     | $/Fish (bundles) | $/Fish total (obs) | $/Fish total (model) | $/Hour (model) |
|-----------|------------:|----------------:|-------------:|-------------------------------------------------------|-----------------:|-------------------:|---------------------:|---------------:|
| Alamo Sea |         420 |          $1,472 |       $1,404 | Gold Multizone #1, Alamo Starter, Low Level Multizone |             $655 |             $2,127 |           **$2,059** |        $65,607 |
| Dam       |         335 |          $1,664 |       $1,664 | Gold Multizone #1, Low Level Multizone                |             $369 |             $2,033 |           **$2,033** |        $62,556 |
| Roxwood   |         256 |          $1,826 |       $1,849 | Gold Multizone #1, Low Level Multizone                |             $257 |             $2,083 |           **$2,107** |        $53,784 |

## Optimal Allocation

Optimal time split across locations to maximize total $/hour (considering both sale value and cross-location bundle completions):

| Location     | Time % (obs) | $/Fish (obs) | $/Hour (obs) | Time % (model) | $/Fish (model) | $/Hour (model) |
|--------------|-------------:|-------------:|-------------:|---------------:|---------------:|---------------:|
| Alamo Sea    |          59% |       $1,472 |      $53,735 |            15% |         $1,404 |        $51,568 |
| Dam          |          19% |       $1,664 |      $51,206 |            39% |         $1,664 |        $51,206 |
| Roxwood      |          22% |       $1,826 |      $46,621 |            46% |         $1,849 |        $47,218 |
| **Combined** |         100% |              |  **$56,022** |           100% |                |    **$55,377** |

**Observed:** splitting yields **$56,022**/hour vs **$53,735**/hour best solo (+$2,288/hour, +4.3%).
**Model:** splitting yields **$55,377**/hour vs **$51,568**/hour best solo (+$3,809/hour, +7.4%).

## Bundle Details

### Alamo Sea

| Bundle        | Fish                                     |   Bonus | Avg Fish to Complete | Avg Time | Bonus/Fish | Catch Rates                                                                              |
|---------------|------------------------------------------|--------:|---------------------:|---------:|-----------:|------------------------------------------------------------------------------------------|
| Alamo Starter | Morwhong, Southern Tuna, Silver Trevally | $10,000 |                   57 |  108 min |       $174 | Morwhong: 27/420 (6.4%) \| Southern Tuna: 9/420 (2.1%) \| Silver Trevally: 17/420 (4.0%) |

### Cross-Location

| Bundle              | Fish                             |   Bonus | Avg Fish to Complete | Avg Time | Bonus/Fish | Catch Rates                                                                                                 |
|---------------------|----------------------------------|--------:|---------------------:|---------:|-----------:|-------------------------------------------------------------------------------------------------------------|
| Gold Multizone #1   | Bluefin Tuna, Musky, Dolphinfish | $12,750 |                  202 |  402 min |        $63 | Bluefin Tuna @ Alamo Sea: 3/420 (0.7%) \| Musky @ Dam: 17/335 (5.1%) \| Dolphinfish @ Roxwood: 6/256 (2.3%) |
| Low Level Multizone | Scollop, Carp, Grenadier         | $11,000 |                   56 |  118 min |       $196 | Scollop @ Alamo Sea: 47/420 (11.2%) \| Carp @ Dam: 14/335 (4.2%) \| Grenadier @ Roxwood: 11/256 (4.3%)      |

## Drop Rate Analysis

### Tier Distribution

Tier drop rates are consistent across locations, suggesting a fixed game mechanic:

| Tier        | Alamo Sea |   Dam | Roxwood | Average |
|-------------|----------:|------:|--------:|--------:|
| xxxx purple |      0.2% |  0.0% |    0.4% |    0.2% |
| xxx         |      6.4% | 10.1% |    9.0% |    8.5% |
| xx          |     26.4% | 28.1% |   30.9% |   28.4% |
| x           |     65.5% | 61.8% |   59.4% |   62.2% |

### Within-Tier Weights

Observed frequencies vs model (percentage template) per fish.
Model uses shared percentage templates across all locations (5% granularity).

#### Alamo Sea — xxx (3 fish, 27 observed)

| Fish            | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|-----------------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| Silver Trevally |    17 |      63.0% |      3 |    60.0% |     55% |          55.0% |     +2.2 |
| Great Barracuda |     7 |      25.9% |      1 |    20.0% |     30% |          30.0% |     -1.1 |
| Bluefin Tuna    |     3 |      11.1% |      1 |    20.0% |     15% |          15.0% |     -1.0 |

Weight fit: χ² = 1.58, df = 2, p = 0.454 — good
Model fit (55%/30%/15%): χ² = 0.73, p = 0.693 — excellent

#### Alamo Sea — xx (6 fish, 111 observed)

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

#### Alamo Sea — x (7 fish, 275 observed)

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

#### Dam — xxx (3 fish, 34 observed)

| Fish          | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|---------------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| Musky         |    17 |      50.0% |      2 |    50.0% |     55% |          55.0% |     -1.7 |
| Pike          |    10 |      29.4% |      1 |    25.0% |     30% |          30.0% |     -0.2 |
| Rainbow Trout |     7 |      20.6% |      1 |    25.0% |     15% |          15.0% |     +1.9 |

Weight fit: χ² = 0.53, df = 2, p = 0.767 — excellent
Model fit (55%/30%/15%): χ² = 0.87, p = 0.648 — excellent

#### Dam — xx (6 fish, 94 observed)

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

#### Dam — x (8 fish, 207 observed)

| Fish                 | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|----------------------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| Murray Cod           |    50 |      24.2% |      5 |    23.8% |     20% |          20.0% |     +8.6 |
| Banded Butterflyfish |    35 |      16.9% |      3 |    14.3% |     15% |          15.0% |     +3.9 |
| Triggerfish          |    28 |      13.5% |      3 |    14.3% |     15% |          15.0% |     -3.1 |
| Sand Whiting         |    26 |      12.6% |      3 |    14.3% |     15% |          15.0% |     -5.1 |
| Cod                  |    23 |      11.1% |      2 |     9.5% |     10% |          10.0% |     +2.3 |
| Escolar              |    19 |       9.2% |      2 |     9.5% |     10% |          10.0% |     -1.7 |
| Brook Trout          |    16 |       7.7% |      2 |     9.5% |     10% |          10.0% |     -4.7 |
| Black Bream          |    10 |       4.8% |      1 |     4.8% |      5% |           5.0% |     -0.3 |

Weight fit: χ² = 2.80, df = 7, p = 0.903 — excellent
Model fit (20%/15%/15%/15%/10%/10%/10%/5%): χ² = 4.88, p = 0.674 — excellent

#### Roxwood — xxx (3 fish, 23 observed)

| Fish          | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|---------------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| Grenadier     |    11 |      47.8% |      9 |    47.4% |     55% |          55.0% |     -1.7 |
| King Mackerel |     6 |      26.1% |      5 |    26.3% |     30% |          30.0% |     -0.9 |
| Dolphinfish   |     6 |      26.1% |      5 |    26.3% |     15% |          15.0% |     +2.5 |

Weight fit: χ² = 0.00, df = 2, p = 0.999 — excellent
Model fit (55%/30%/15%): χ² = 2.22, p = 0.330 — good

#### Roxwood — xx (6 fish, 79 observed)

| Fish         | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|--------------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| Snapper      |    19 |      24.1% |      7 |    21.2% |     25% |          25.0% |     -0.8 |
| Silver Perch |    16 |      20.3% |      7 |    21.2% |     20% |          20.0% |     +0.2 |
| Amberjack    |    16 |      20.3% |      7 |    21.2% |     20% |          20.0% |     +0.2 |
| Gummy Shark  |    12 |      15.2% |      4 |    12.1% |     15% |          15.0% |     +0.2 |
| Brown Trout  |    10 |      12.7% |      4 |    12.1% |     10% |          10.0% |     +2.1 |
| Red Snapper  |     6 |       7.6% |      4 |    12.1% |     10% |          10.0% |     -1.9 |

Weight fit: χ² = 2.34, df = 5, p = 0.801 — excellent
Model fit (25%/20%/20%/15%/10%/10%): χ² = 1.05, p = 0.958 — excellent

#### Roxwood — x (7 fish, 152 observed)

| Fish               | Count | Observed % | Weight | Weight % | Model % | Model % (norm) | Residual |
|--------------------|------:|-----------:|-------:|---------:|--------:|---------------:|---------:|
| Grouper            |    45 |      29.6% |      6 |    30.0% |     20% |          21.1% |    +13.0 |
| Dungeness Crab     |    27 |      17.8% |      3 |    15.0% |     15% |          15.8% |     +3.0 |
| Ocean Perch        |    25 |      16.4% |      3 |    15.0% |     15% |          15.8% |     +1.0 |
| Sandy Sprat        |    23 |      15.1% |      3 |    15.0% |     15% |          15.8% |     -1.0 |
| Australian Herring |    17 |      11.2% |      3 |    15.0% |     10% |          10.5% |     +1.0 |
| Ocean Jacket       |     9 |       5.9% |      1 |     5.0% |     10% |          10.5% |     -7.0 |
| Sand Whiting       |     6 |       3.9% |      1 |     5.0% |     10% |          10.5% |    -10.0 |

Weight fit: χ² = 3.07, df = 6, p = 0.801 — excellent
Model fit (20%/15%/15%/15%/10%/10%/10%/5%): χ² = 15.11, p = 0.019 — poor
