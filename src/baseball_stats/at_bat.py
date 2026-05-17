"""One plate appearance: who was involved and where runners stood."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Runner:
    player_id: int
    base: int  # 1, 2, or 3


@dataclass(frozen=True)
class AtBat:
    game_pk: int
    game_date: str
    at_bat_number: int
    inning: int
    half: str  # "Top" or "Bot"

    batter_id: int
    pitcher_id: int
    outcome: str

    outs_before: int
    outs_after: int | None  # None for the last plate appearance of a game

    runs_scored: int

    runners_before: tuple[Runner, ...]
    runners_after: tuple[Runner, ...]


def runners_on_bases(on_1b, on_2b, on_3b) -> tuple[Runner, ...]:
    """Build runner list from Statcast on_1b / on_2b / on_3b columns (MLBAM ids)."""
    runners = []
    for base, occupant in ((1, on_1b), (2, on_2b), (3, on_3b)):
        if pd.notna(occupant):
            runners.append(Runner(player_id=int(occupant), base=base))
    return tuple(runners)
