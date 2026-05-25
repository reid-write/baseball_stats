"""Load at-bat records from MLB Statcast via pybaseball."""

import os
from datetime import date
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache"
GAME_CACHE_DIR = CACHE_DIR / "games"
os.environ.setdefault("PYBASEBALL_CACHE", str(CACHE_DIR / "pybaseball"))

from pybaseball import playerid_lookup, statcast, statcast_batter, statcast_single_game

from baseball_stats.at_bat import AtBat, runners_on_bases

HALF_MAP = {"Top": "Top", "Bot": "Bot"}

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


def season_date_range(season: int) -> tuple[str, str]:
    """Approximate MLB season window (spring through postseason)."""
    return f"{season}-03-01", f"{season}-11-15"


def lookup_batter_id(last_name: str, first_name: str = "") -> int:
    """Resolve a batter's MLBAM id from their name."""
    table = playerid_lookup(last_name, first_name)
    if table.empty:
        raise ValueError(f"No player found for {first_name} {last_name}".strip())
    return int(table.iloc[0]["key_mlbam"])


def _outs_on_play(event: str) -> int:
    return OUTS_ON_PLAY.get(event, 0)


def _outs_after(row, next_row) -> int | None:
    """Outs in the half-inning immediately after this plate appearance."""
    outs_before = int(row.outs_when_up)
    outs_after_play = min(3, outs_before + _outs_on_play(row.events))

    if next_row is None:
        return outs_after_play

    same_half_inning = (
        int(next_row.inning) == int(row.inning)
        and next_row.inning_topbot == row.inning_topbot
    )
    if same_half_inning:
        return int(next_row.outs_when_up)

    # Next batter is a new half-inning — use outs on this play, not 3
    return outs_after_play


def _load_game_events(game_pk: int) -> pd.DataFrame:
    """All Statcast events for one game (cached on disk)."""
    GAME_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = GAME_CACHE_DIR / f"{game_pk}.parquet"
    if path.exists():
        return pd.read_parquet(path)

    raw = statcast_single_game(game_pk)
    if raw is None or raw.empty:
        return pd.DataFrame()
    raw.to_parquet(path, index=False)
    return raw


def _next_at_bat_row(events: pd.DataFrame, row) -> pd.Series | None:
    """Next plate appearance in the same game (any batter)."""
    game = events[events["game_pk"] == row["game_pk"]]
    later = game[game["at_bat_number"] > row["at_bat_number"]]
    if later.empty:
        return None
    return later.iloc[0]


def _events_to_at_bats(events: pd.DataFrame) -> list[AtBat]:
    events = (
        events[events["events"].notna()]
        .sort_values(["game_pk", "at_bat_number"])
        .reset_index(drop=True)
    )

    after_cols = events.groupby("game_pk", sort=False)[["on_1b", "on_2b", "on_3b"]].shift(-1)
    after_cols.columns = ["after_on_1b", "after_on_2b", "after_on_3b"]
    events = pd.concat([events, after_cols], axis=1)

    at_bats: list[AtBat] = []
    for i in range(len(events)):
        row = events.iloc[i]
        next_row = _next_at_bat_row(events, row)

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
                outs_before=int(row.outs_when_up),
                outs_after=_outs_after(row, next_row),
                runs_scored=int(row.post_bat_score - row.bat_score),
                runners_before=runners_on_bases(row.on_1b, row.on_2b, row.on_3b),
                runners_after=runners_on_bases(
                    row.after_on_1b, row.after_on_2b, row.after_on_3b
                ),
            )
        )

    return at_bats


def _at_bats_to_df(at_bats: list[AtBat]) -> pd.DataFrame:
    rows = []
    for ab in at_bats:
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


def fetch_at_bats(start_date: str | date, end_date: str | date | None = None) -> list[AtBat]:
    """Pull all plate appearances in a calendar date range."""
    end = end_date if end_date is not None else start_date
    raw = statcast(str(start_date), str(end))
    return _events_to_at_bats(raw)


def fetch_at_bats_for_batter(
    batter_id: int,
    season: int,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
) -> list[AtBat]:
    """
    Pull all plate appearances for one batter in a season.

    Discovers games via Baseball Savant's batter search, then loads each full
    game so "next at-bat" means the next batter in the game (for outs and
    base state after the play).
    """
    if start_date is None and end_date is None:
        start_date, end_date = season_date_range(season)
    elif start_date is None or end_date is None:
        raise ValueError("Pass both start_date and end_date, or neither.")

    batter_raw = statcast_batter(str(start_date), str(end_date), batter_id)
    game_pks = sorted(batter_raw["game_pk"].dropna().unique())

    at_bats: list[AtBat] = []
    for game_pk in game_pks:
        game_events = _load_game_events(int(game_pk))
        if game_events.empty:
            continue
        at_bats.extend(_events_to_at_bats(game_events))

    return sorted(
        [ab for ab in at_bats if ab.batter_id == batter_id],
        key=lambda ab: (ab.game_date, ab.game_pk, ab.at_bat_number),
    )


def fetch_at_bats_df(start_date: str | date, end_date: str | date | None = None) -> pd.DataFrame:
    return _at_bats_to_df(fetch_at_bats(start_date, end_date))


def fetch_at_bats_for_batter_df(
    batter_id: int,
    season: int,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
) -> pd.DataFrame:
    return _at_bats_to_df(fetch_at_bats_for_batter(batter_id, season, start_date, end_date))
