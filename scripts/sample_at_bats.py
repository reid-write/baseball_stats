#!/usr/bin/env python3
"""Print a few at-bats to verify base-state fields."""

from baseball_stats.data.fetch import fetch_at_bats_df

if __name__ == "__main__":
    df = fetch_at_bats_df("2024-04-01", "2024-04-01")
    cols = [
        "batter_id",
        "pitcher_id",
        "outcome",
        "outs_before",
        "outs_after",
        "runs_scored",
        "runner_1b_before",
        "runner_2b_before",
        "runner_3b_before",
        "runner_1b_after",
        "runner_2b_after",
        "runner_3b_after",
    ]
    print(df[cols].head(10).to_string(index=False))
