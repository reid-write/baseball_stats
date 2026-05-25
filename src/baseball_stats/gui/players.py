"""Player name index for GUI type-ahead search."""

from pathlib import Path

import pandas as pd
from pybaseball import chadwick_register

CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache"
PLAYERS_CACHE = CACHE_DIR / "players.parquet"


def load_player_index() -> pd.DataFrame:
    """Load MLB player names and ids (cached locally after first fetch)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if PLAYERS_CACHE.exists():
        df = pd.read_parquet(PLAYERS_CACHE)
    else:
        df = chadwick_register()
        df = df.dropna(subset=["key_mlbam"]).copy()
        df["key_mlbam"] = df["key_mlbam"].astype(int)
        df["label"] = df["name_last"] + ", " + df["name_first"]
        df.to_parquet(PLAYERS_CACHE, index=False)

    return df


def search_players(
    query: str,
    players: pd.DataFrame,
    season: int | None = None,
    limit: int = 20,
) -> list[str]:
    """
    Return player labels matching query, ranked by relevance.

    Filters to players active in `season` when provided.
    """
    q = query.strip().lower()
    if not q:
        return []

    pool = players
    if season is not None:
        pool = pool[
            (pool["mlb_played_first"] <= season) & (pool["mlb_played_last"] >= season)
        ]

    last = pool["name_last"].str.lower()
    first = pool["name_first"].str.lower()
    label = pool["label"].str.lower()

    mask = last.str.startswith(q) | first.str.startswith(q) | label.str.contains(q, regex=False)
    if not mask.any():
        mask = last.str.contains(q, regex=False) | first.str.contains(q, regex=False) | label.str.contains(q, regex=False)

    hits = pool.loc[mask].copy()
    if hits.empty:
        return []

    hits["_rank"] = (~last[mask].str.startswith(q)).astype(int)
    hits = hits.sort_values(["_rank", "name_last", "name_first"]).head(limit)
    return hits["label"].tolist()


def label_to_id(label: str, players: pd.DataFrame) -> int | None:
    row = players.loc[players["label"] == label]
    if row.empty:
        return None
    return int(row.iloc[0]["key_mlbam"])
