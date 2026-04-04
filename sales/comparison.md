# Location Comparison

Assuming 100s wait for bite + 15s reel-in = 115s per fish (31.3 fish/hour).

| Location     | Fish Caught | $/Fish (sales) | Available Bundles | $/Fish (bundles) | $/Fish (total) |  $/Hour |
|--------------|------------:|---------------:|-------------------|-----------------:|---------------:|--------:|
| Alamo Sea    |         417 |         $1,483 | Alamo Starter     |             $216 |     **$1,699** | $53,180 |
| Land Act Dam |         203 |         $1,670 | none              |               $0 |     **$1,670** | $52,284 |

## Bundle Details

### Alamo Sea

| Bundle        | Fish                                     |   Bonus | Avg Fish to Complete | Avg Time | Bonus/Fish | Catch Rates                                                                              |
|---------------|------------------------------------------|--------:|---------------------:|---------:|-----------:|------------------------------------------------------------------------------------------|
| Alamo Starter | Morwhong, Southern Tuna, Silver Trevally | $10,000 |                   57 |  109 min |       $175 | Morwhong: 27/417 (6.5%) \| Southern Tuna: 9/417 (2.2%) \| Silver Trevally: 17/417 (4.1%) |

## Drop Rate Analysis

### Tier Distribution

Tier drop rates are consistent across locations, suggesting a fixed game mechanic:

| Tier | Alamo Sea | Land Act Dam | Average |
|------|----------:|-------------:|--------:|
| ★★★  |      6.5% |        11.3% |    8.9% |
| ★★   |     26.6% |        27.6% |   27.1% |
| ★    |     65.9% |        61.1% |   63.5% |

### Within-Tier Weights

Fitted smallest integer weights per fish using χ² goodness-of-fit (p > 0.05 = acceptable).

#### Alamo Sea — ★★★ (3 fish, 27 observed)

| Fish            | Count | Observed % | Weight | Expected % | Residual |
|-----------------|------:|-----------:|-------:|-----------:|---------:|
| Silver Trevally |    17 |      63.0% |      3 |      60.0% |     +0.8 |
| Great Barracuda |     7 |      25.9% |      1 |      20.0% |     +1.6 |
| Bluefin Tuna    |     3 |      11.1% |      1 |      20.0% |     -2.4 |

χ² = 1.58, df = 2, p = 0.454 — good fit

#### Alamo Sea — ★★ (6 fish, 111 observed)

| Fish             | Count | Observed % | Weight | Expected % | Residual |
|------------------|------:|-----------:|-------:|-----------:|---------:|
| Southern Garfish |    30 |      27.0% |      5 |      23.8% |     +3.6 |
| Trout            |    25 |      22.5% |      5 |      23.8% |     -1.4 |
| Blue Warehou     |    24 |      21.6% |      5 |      23.8% |     -2.4 |
| Golden Perch     |    12 |      10.8% |      2 |       9.5% |     +1.4 |
| Snow Crab        |    11 |       9.9% |      2 |       9.5% |     +0.4 |
| Southern Tuna    |     9 |       8.1% |      2 |       9.5% |     -1.6 |

χ² = 1.23, df = 5, p = 0.942 — excellent fit

#### Alamo Sea — ★ (7 fish, 275 observed)

| Fish      | Count | Observed % | Weight | Expected % | Residual |
|-----------|------:|-----------:|-------:|-----------:|---------:|
| Albacore  |    63 |      22.9% |      7 |      22.6% |     +0.9 |
| Scollop   |    47 |      17.1% |      5 |      16.1% |     +2.6 |
| Halibut   |    43 |      15.6% |      5 |      16.1% |     -1.4 |
| Broadbill |    42 |      15.3% |      5 |      16.1% |     -2.4 |
| Morwhong  |    27 |       9.8% |      3 |       9.7% |     +0.4 |
| Flathead  |    27 |       9.8% |      3 |       9.7% |     +0.4 |
| Redfish   |    26 |       9.5% |      3 |       9.7% |     -0.6 |

χ² = 0.36, df = 6, p = 0.999 — excellent fit

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
