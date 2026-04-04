# Location Comparison

Assuming 100s wait for bite + 15s reel-in = 115s per fish (31.3 fish/hour).

| Location     | Fish Caught | $/Fish (sales) | Available Bundles | $/Fish (bundles) | $/Fish (total) |  $/Hour |
|--------------|------------:|---------------:|-------------------|-----------------:|---------------:|--------:|
| Alamo Sea    |         147 |         $1,491 | Alamo Starter     |             $272 |     **$1,763** | $55,187 |
| Land Act Dam |         203 |         $1,670 | none              |               $0 |     **$1,670** | $52,284 |

## Bundle Details

### Alamo Sea

| Bundle        | Fish                                     |   Bonus | Avg Fish to Complete | Avg Time | Bonus/Fish | Catch Rates                                                                            |
|---------------|------------------------------------------|--------:|---------------------:|---------:|-----------:|----------------------------------------------------------------------------------------|
| Alamo Starter | Morwhong, Southern Tuna, Silver Trevally | $10,000 |                   46 |   89 min |       $216 | Morwhong: 9/147 (6.1%) \| Southern Tuna: 4/147 (2.7%) \| Silver Trevally: 8/147 (5.4%) |

## Drop Rate Analysis

### Tier Distribution

Tier drop rates are consistent across locations, suggesting a fixed game mechanic:

| Tier | Alamo Sea | Land Act Dam | Average |
|------|----------:|-------------:|--------:|
| ★★★  |      8.2% |        11.3% |    9.7% |
| ★★   |     29.3% |        27.6% |   28.4% |
| ★    |     62.6% |        61.1% |   61.8% |

### Within-Tier Weights

Fitted smallest integer weights per fish using χ² goodness-of-fit (p > 0.05 = acceptable).

#### Alamo Sea — ★★★ (2 fish, 12 observed)

| Fish            | Count | Observed % | Weight | Expected % | Residual |
|-----------------|------:|-----------:|-------:|-----------:|---------:|
| Silver Trevally |     8 |      66.7% |      1 |      50.0% |     +2.0 |
| Great Barracuda |     4 |      33.3% |      1 |      50.0% |     -2.0 |

χ² = 1.33, df = 1, p = 0.248 — good fit

#### Alamo Sea — ★★ (6 fish, 43 observed)

| Fish             | Count | Observed % | Weight | Expected % | Residual |
|------------------|------:|-----------:|-------:|-----------:|---------:|
| Blue Warehou     |    14 |      32.6% |      4 |      30.8% |     +0.8 |
| Trout            |    12 |      27.9% |      4 |      30.8% |     -1.2 |
| Southern Garfish |     7 |      16.3% |      2 |      15.4% |     +0.4 |
| Snow Crab        |     4 |       9.3% |      1 |       7.7% |     +0.7 |
| Southern Tuna    |     4 |       9.3% |      1 |       7.7% |     +0.7 |
| Golden Perch     |     2 |       4.7% |      1 |       7.7% |     -1.3 |

χ² = 0.99, df = 5, p = 0.963 — excellent fit

#### Alamo Sea — ★ (7 fish, 92 observed)

| Fish      | Count | Observed % | Weight | Expected % | Residual |
|-----------|------:|-----------:|-------:|-----------:|---------:|
| Broadbill |    26 |      28.3% |      8 |      27.6% |     +0.6 |
| Albacore  |    17 |      18.5% |      5 |      17.2% |     +1.1 |
| Scollop   |    17 |      18.5% |      5 |      17.2% |     +1.1 |
| Halibut   |    12 |      13.0% |      5 |      17.2% |     -3.9 |
| Morwhong  |     9 |       9.8% |      2 |       6.9% |     +2.7 |
| Redfish   |     6 |       6.5% |      2 |       6.9% |     -0.3 |
| Flathead  |     5 |       5.4% |      2 |       6.9% |     -1.3 |

χ² = 2.53, df = 6, p = 0.865 — excellent fit

#### Land Act Dam — ★★★ (3 fish, 23 observed)

| Fish          | Count | Observed % | Weight | Expected % | Residual |
|---------------|------:|-----------:|-------:|-----------:|---------:|
| Musky         |    11 |      47.8% |      7 |      41.2% |     +1.5 |
| Pike          |     8 |      34.8% |      7 |      41.2% |     -1.5 |
| Rainbow Trout |     4 |      17.4% |      3 |      17.6% |     -0.1 |

χ² = 0.48, df = 2, p = 0.788 — excellent fit

#### Land Act Dam — ★★ (6 fish, 56 observed)

| Fish            | Count | Observed % | Weight | Expected % | Residual |
|-----------------|------:|-----------:|-------:|-----------:|---------:|
| Atlantic Salmon |    12 |      21.4% |      1 |      16.7% |     +2.7 |
| Trevella        |    10 |      17.9% |      1 |      16.7% |     +0.7 |
| Wahoo           |     9 |      16.1% |      1 |      16.7% |     -0.3 |
| Sturgeon        |     9 |      16.1% |      1 |      16.7% |     -0.3 |
| Carp            |     9 |      16.1% |      1 |      16.7% |     -0.3 |
| Trumpetfish     |     7 |      12.5% |      1 |      16.7% |     -2.3 |

χ² = 1.43, df = 5, p = 0.921 — excellent fit

#### Land Act Dam — ★ (8 fish, 124 observed)

| Fish             | Count | Observed % | Weight | Expected % | Residual |
|------------------|------:|-----------:|-------:|-----------:|---------:|
| Murray Cod       |    32 |      25.8% |      7 |      25.9% |     -0.1 |
| Banded Butterfly |    21 |      16.9% |      4 |      14.8% |     +2.6 |
| Sand Whiting     |    19 |      15.3% |      4 |      14.8% |     +0.6 |
| Triggerfish      |    14 |      11.3% |      4 |      14.8% |     -4.4 |
| Cod              |    11 |       8.9% |      2 |       7.4% |     +1.8 |
| Black Bream      |    10 |       8.1% |      2 |       7.4% |     +0.8 |
| Escolar          |    10 |       8.1% |      2 |       7.4% |     +0.8 |
| Brook Trout      |     7 |       5.6% |      2 |       7.4% |     -2.2 |

χ² = 2.46, df = 7, p = 0.930 — excellent fit
