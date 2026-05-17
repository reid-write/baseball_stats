"""Load at-bat records from MLB Statcast via pybaseball."""

import os
from datetime import date
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache"
os.environ.setdefault("PYBASEBALL_CACHE", str(CACHE_DIR / "pybaseball"))

from pybaseball import statcast

from baseball_stats.at_bat import AtBat, runners_on_bases

HALF_MAP = {"Top": "Top", "Bot": "Bot"}

# Outs recorded on the play when the inning does not continue.
OUTS_ON_PLAY = {
    "strikeout": 1,
    "field_out": 1,
    "force_out": 1,
    "fielders_choice_out": 1,
    "sac_fly": 1,
    "sac_bunt": 1,
    "grounded_into_double_play": 2,
    "double_play": 2,
    "strikeout_double_play": 2,
}


def _outs_after(row, next_row) -> int | None:
    """Outs in the inning after this plate appearance."""
    outs_before = int(row.outs_when_up)

    if next_row is None:
        return min(3, outs_before + OUTS_ON_PLAY.get(row.events, 0))

    same_half_inning = (
        int(next_row.inning) == int(row.inning)
        and next_row.inning_topbot == row.inning_topbot
    )
    if same_half_inning:
        return int(next_row.outs_when_up)

    return 3


def fetch_at_bats(start_date: str | date, end_date: str | date | None = None) -> list[AtBat]:
    """
    Pull completed plate appearances for a date range.

    Statcast provides batter, pitcher, outcome, and runner ids on each base
    before the at-bat. End-of-at-bat base occupancy is taken from the next
    at-bat's starting state in the same game.
    """
    end = end_date if end_date is not None else start_date
    start_s = str(start_date)
    end_s = str(end)

    raw = statcast(start_s, end_s)
    events = (
        raw[raw["events"].notna()]
        .sort_values(["game_pk", "at_bat_number"])
        .reset_index(drop=True)
    )

    for base in ("on_1b", "on_2b", "on_3b"):
        events[f"after_{base}"] = events.groupby("game_pk", sort=False)[base].shift(-1)

    at_bats: list[AtBat] = []
    n = len(events)
    for i in range(n):
        row = events.iloc[i]
        next_row = events.iloc[i + 1] if i + 1 < n and events.iloc[i + 1]["game_pk"] == row["game_pk"] else None

        runs = int(row.post_bat_score - row.bat_score)
        outs_before = int(row.outs_when_up)
        outs_after = _outs_after(row, next_row)

        half = HALF_MAP.get(row.inning_topbot, row.inning_topbot)
        at_bats.append(
            AtBat(
                game_pk=int(row.game_pk),
                game_date=str(row.game_date)[:10],
                at_bat_number=int(row.at_bat_number),
                inning=int(row.inning),
                half=half,
                batter_id=int(row.batter),
                pitcher_id=int(row.pitcher),
                outcome=str(row.events),
                outs_before=outs_before,
                outs_after=outs_after,
                runs_scored=runs,
                runners_before=runners_on_bases(row.on_1b, row.on_2b, row.on_3b),
                runners_after=runners_on_bases(
                    row.after_on_1b, row.after_on_2b, row.after_on_3b
                ),
            )
        )

    return at_bats


def fetch_at_bats_df(start_date: str | date, end_date: str | date | None = None) -> pd.DataFrame:
    """Same data as fetch_at_bats, flattened to a DataFrame for inspection."""
    records = fetch_at_bats(start_date, end_date)
    rows = []
    for ab in records:
        before = {r.base: r.player_id for r in ab.runners_before}
        after = {r.base: r.player_id for r in ab.runners_after}
        rows.append(
            {
                "game_pk": ab.game_pk,
                "game_date": ab.game_date,
                "at_bat_number": ab.at_bat_number,
                "inning": ab.inning,
                "half": ab.half,
                "batter_id": ab.batter_id,
                "pitcher_id": ab.pitcher_id,
                "outcome": ab.outcome,
                "outs_before": ab.outs_before,
                "outs_after": ab.outs_after,
                "runs_scored": ab.runs_scored,
                "runner_1b_before": before.get(1),
                "runner_2b_before": before.get(2),
                "runner_3b_before": before.get(3),
                "runner_1b_after": after.get(1),
                "runner_2b_after": after.get(2),
                "runner_3b_after": after.get(3),
            }
        )
    return pd.DataFrame(rows)
