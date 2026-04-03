# Location Comparison

Assuming 100s wait for bite + 15s reel-in = 115s per fish (31.3 fish/hour).

| Location     | Fish Caught | $/Fish (sales) | Available Bundles | $/Fish (bundles) | $/Fish (total) |  $/Hour |
|--------------|------------:|---------------:|-------------------|-----------------:|---------------:|--------:|
| Alamo Sea    |         147 |         $1,491 | Alamo Starter     |             $272 |     **$1,763** | $55,187 |
| Land Act Dam |         139 |         $1,661 | none              |               $0 |     **$1,661** | $52,001 |

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
| ★★★  |      8.2% |        10.1% |    9.1% |
| ★★   |     29.3% |        27.3% |   28.3% |
| ★    |     62.6% |        62.6% |   62.6% |

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

#### Land Act Dam — ★★★ (3 fish, 14 observed)

| Fish          | Count | Observed % | Weight | Expected % | Residual |
|---------------|------:|-----------:|-------:|-----------:|---------:|
| Musky         |     7 |      50.0% |      1 |      33.3% |     +2.3 |
| Pike          |     4 |      28.6% |      1 |      33.3% |     -0.7 |
| Rainbow Trout |     3 |      21.4% |      1 |      33.3% |     -1.7 |

χ² = 1.86, df = 2, p = 0.395 — good fit

#### Land Act Dam — ★★ (6 fish, 38 observed)

| Fish            | Count | Observed % | Weight | Expected % | Residual |
|-----------------|------:|-----------:|-------:|-----------:|---------:|
| Atlantic Salmon |     7 |      18.4% |      1 |      16.7% |     +0.7 |
| Wahoo           |     7 |      18.4% |      1 |      16.7% |     +0.7 |
| Carp            |     7 |      18.4% |      1 |      16.7% |     +0.7 |
| Sturgeon        |     6 |      15.8% |      1 |      16.7% |     -0.3 |
| Trevella        |     6 |      15.8% |      1 |      16.7% |     -0.3 |
| Trumpetfish     |     5 |      13.2% |      1 |      16.7% |     -1.3 |

χ² = 0.53, df = 5, p = 0.991 — excellent fit

#### Land Act Dam — ★ (8 fish, 87 observed)

| Fish             | Count | Observed % | Weight | Expected % | Residual |
|------------------|------:|-----------:|-------:|-----------:|---------:|
| Murray Cod       |    19 |      21.8% |      5 |      20.0% |     +1.6 |
| Sand Whiting     |    17 |      19.5% |      5 |      20.0% |     -0.4 |
| Banded Butterfly |    16 |      18.4% |      5 |      20.0% |     -1.4 |
| Triggerfish      |     8 |       9.2% |      2 |       8.0% |     +1.0 |
| Black Bream      |     7 |       8.0% |      2 |       8.0% |     +0.0 |
| Escolar          |     7 |       8.0% |      2 |       8.0% |     +0.0 |
| Brook Trout      |     7 |       8.0% |      2 |       8.0% |     +0.0 |
| Cod              |     6 |       6.9% |      2 |       8.0% |     -1.0 |

χ² = 0.56, df = 7, p = 0.999 — excellent fit
