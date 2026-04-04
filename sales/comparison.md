# Location Comparison

Detected tier: 3 (Alamo Sea, Land Act Dam, Roxwood).

Assuming 100s wait for bite + 15s reel-in = 115s per fish (31.3 fish/hour).

~ = estimated (not yet observed in catch data)

| Location     | Fish Caught | $/Fish (sales) | Available Bundles                                      | $/Fish (bundles) | $/Fish (total) |  $/Hour |
|--------------|------------:|---------------:|--------------------------------------------------------|-----------------:|---------------:|--------:|
| Alamo Sea    |         420 |         $1,472 | Gold Multizone #1~, Alamo Starter, Low Level Multizone |             $655 |     **$2,127** | $66,595 |
| Land Act Dam |         203 |         $1,670 | Gold Multizone #1~, Low Level Multizone                |             $393 |     **$2,063** | $64,583 |
| Roxwood      |          35 |         $1,794 | Gold Multizone #1~, Low Level Multizone                |             $371 |     **$2,166** | $67,796 |

## Optimal Allocation

Note: some bundle fish probabilities are estimated (~).

Optimal time split across locations to maximize total $/hour (considering both sale value and cross-location bundle completions):

| Location     | Time % | $/Fish (sales) | $/Hour (solo) |
|--------------|-------:|---------------:|--------------:|
| Alamo Sea    |    18% |         $1,472 |       $52,800 |
| Land Act Dam |    46% |         $1,670 |       $52,284 |
| Roxwood      |    36% |         $1,794 |       $56,169 |
| **Combined** |   100% |                |   **$61,225** |

Splitting across locations yields **$61,225**/hour vs **$56,169**/hour best solo (+$5,056/hour, +9.0%).

## Bundle Details

### Alamo Sea

| Bundle        | Fish                                     |   Bonus | Avg Fish to Complete | Avg Time | Bonus/Fish | Catch Rates                                                                              |
|---------------|------------------------------------------|--------:|---------------------:|---------:|-----------:|------------------------------------------------------------------------------------------|
| Alamo Starter | Morwhong, Southern Tuna, Silver Trevally | $10,000 |                   57 |  110 min |       $174 | Morwhong: 27/420 (6.4%) \| Southern Tuna: 9/420 (2.1%) \| Silver Trevally: 17/420 (4.0%) |

### Cross-Location

| Bundle              | Fish                             |   Bonus | Avg Fish to Complete | Avg Time | Bonus/Fish | Catch Rates                                                                                                          |
|---------------------|----------------------------------|--------:|---------------------:|---------:|-----------:|----------------------------------------------------------------------------------------------------------------------|
| Gold Multizone #1   | Bluefin Tuna, Musky, Dolphinfish | $12,750 |                  185 |  354 min |        $69 | Bluefin Tuna @ Alamo Sea: 3/420 (0.7%) \| Musky @ Land Act Dam: 11/203 (5.4%) \| Dolphinfish @ Roxwood: ~3.8% (est.) |
| Low Level Multizone | Scollop, Carp, Grenadier         | $11,000 |                   49 |   94 min |       $225 | Scollop @ Alamo Sea: 47/420 (11.2%) \| Carp @ Land Act Dam: 9/203 (4.4%) \| Grenadier @ Roxwood: 2/35 (5.7%)         |

## Drop Rate Analysis

### Tier Distribution

Tier drop rates are consistent across locations, suggesting a fixed game mechanic:

| Tier        | Alamo Sea | Land Act Dam | Roxwood | Average |
|-------------|----------:|-------------:|--------:|--------:|
| ★★★★ purple |      0.2% |         0.0% |    0.0% |    0.1% |
| ★★★         |      6.4% |        11.3% |   11.4% |    9.7% |
| ★★          |     26.4% |        27.6% |   25.7% |   26.6% |
| ★           |     65.5% |        61.1% |   62.9% |   63.1% |

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

#### Roxwood — ★★★ (2 fish, 4 observed)

| Fish          | Count | Observed % | Weight | Expected % | Residual |
|---------------|------:|-----------:|-------:|-----------:|---------:|
| King Mackerel |     2 |      50.0% |      1 |      50.0% |     +0.0 |
| Grenadier     |     2 |      50.0% |      1 |      50.0% |     +0.0 |

χ² = 0.00, df = 1, p = 1.000 — excellent fit

#### Roxwood — ★★ (6 fish, 9 observed)

| Fish         | Count | Observed % | Weight | Expected % | Residual |
|--------------|------:|-----------:|-------:|-----------:|---------:|
| Snapper      |     2 |      22.2% |      1 |      16.7% |     +0.5 |
| Gummy Shark  |     2 |      22.2% |      1 |      16.7% |     +0.5 |
| Silver Perch |     2 |      22.2% |      1 |      16.7% |     +0.5 |
| Amberjack    |     1 |      11.1% |      1 |      16.7% |     -0.5 |
| Brown Trout  |     1 |      11.1% |      1 |      16.7% |     -0.5 |
| Red Snapper  |     1 |      11.1% |      1 |      16.7% |     -0.5 |

χ² = 1.00, df = 5, p = 0.963 — excellent fit

#### Roxwood — ★ (7 fish, 22 observed)

| Fish               | Count | Observed % | Weight | Expected % | Residual |
|--------------------|------:|-----------:|-------:|-----------:|---------:|
| Grouper            |     8 |      36.4% |     10 |      35.7% |     +0.1 |
| Australian Herring |     4 |      18.2% |      3 |      10.7% |     +1.6 |
| Sand Whiting       |     3 |      13.6% |      3 |      10.7% |     +0.6 |
| Sandy Sprat        |     2 |       9.1% |      3 |      10.7% |     -0.4 |
| Ocean Perch        |     2 |       9.1% |      3 |      10.7% |     -0.4 |
| Dungeness Crab     |     2 |       9.1% |      3 |      10.7% |     -0.4 |
| Ocean Jacket       |     1 |       4.5% |      3 |      10.7% |     -1.4 |

χ² = 2.27, df = 6, p = 0.894 — excellent fit
