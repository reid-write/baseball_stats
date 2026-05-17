# baseball_stats

At-bat level data for exploring batting statistics. Each record captures who batted, who pitched, the outcome, and which runners occupied which bases before and after the plate appearance.

## Structure

```
src/baseball_stats/
├── at_bat.py       # AtBat and Runner types
└── data/
    └── fetch.py    # Load plate appearances from Statcast
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Data model

Each `AtBat` has:

| Field | Description |
|-------|-------------|
| `batter_id` | Batter (MLBAM id) |
| `pitcher_id` | Pitcher (MLBAM id) |
| `outcome` | Result of the PA (e.g. `single`, `strikeout`, `walk`) |
| `outs_before`, `outs_after` | Outs in the inning before / after the PA (0–3) |
| `runs_scored` | Runs scored by the batting team on the play |
| `runners_before` | Runners on 1st / 2nd / 3rd before the PA |
| `runners_after` | Runners on each base after the PA |

Runners are `(player_id, base)` pairs where base is 1, 2, or 3.

## Usage

```python
from baseball_stats import fetch_at_bats

at_bats = fetch_at_bats("2024-04-01", "2024-04-07")
for ab in at_bats[:5]:
    print(ab.batter_id, ab.outcome, ab.runners_before, "→", ab.runners_after)
```

Or as a flat table:

```python
from baseball_stats.data.fetch import fetch_at_bats_df

df = fetch_at_bats_df("2024-04-01")
```

```bash
python scripts/sample_at_bats.py
```

## Source

[MLB Statcast](https://baseballsavant.mlb.com/) via [pybaseball](https://github.com/jldbc/pybaseball). Base state before each PA comes directly from Statcast; base state after is inferred from the next at-bat’s starting state in the same game (last PA of a game has no after-state).
