#!/usr/bin/env python3
"""Desktop GUI: search a player and season, view at-bat table."""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import pandas as pd

# pybaseball cache before import
_ROOT = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("PYBASEBALL_CACHE", os.path.join(_ROOT, "data", "cache", "pybaseball"))

from baseball_stats.data.fetch import fetch_at_bats_for_batter_df
from baseball_stats.gui.autocomplete import AutocompleteEntry
from baseball_stats.gui.players import label_to_id, load_player_index, search_players

TABLE_COLUMNS = [
    ("game_date", "Date", 90),
    ("inning", "Inn", 40),
    ("half", "Half", 45),
    ("outs_before", "Outs", 45),
    ("outs_after", "Outs+", 45),
    ("outcome", "Outcome", 110),
    ("runs_scored", "R", 35),
    ("pitcher_id", "Pitcher", 70),
    ("runner_1b_before", "1B", 55),
    ("runner_2b_before", "2B", 55),
    ("runner_3b_before", "3B", 55),
    ("runner_1b_after", "1B+", 55),
    ("runner_2b_after", "2B+", 55),
    ("runner_3b_after", "3B+", 55),
]


class AtBatViewerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Baseball At-Bat Viewer")
        self.root.geometry("1100x600")
        self.root.minsize(800, 400)

        self.players: pd.DataFrame | None = None
        self._id_by_label: dict[str, int] = {}

        self._build_widgets()
        self._load_players_async()

    def _build_widgets(self) -> None:
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Player").grid(row=0, column=0, sticky=tk.W, padx=(0, 6))
        self.player_search = AutocompleteEntry(
            top,
            get_suggestions=self._player_suggestions,
            width=42,
        )
        self.player_search.grid(row=0, column=1, sticky=tk.EW, padx=(0, 16))

        ttk.Label(top, text="Season").grid(row=0, column=2, sticky=tk.W, padx=(0, 6))
        self.year_var = tk.StringVar(value="2024")
        self.year_spin = ttk.Spinbox(
            top,
            from_=1960,
            to=2030,
            textvariable=self.year_var,
            width=8,
        )
        self.year_spin.grid(row=0, column=3, padx=(0, 16))

        self.load_btn = ttk.Button(top, text="Load at-bats", command=self._on_load)
        self.load_btn.grid(row=0, column=4)
        self.load_btn.state(["disabled"])

        top.columnconfigure(1, weight=1)

        self.status_var = tk.StringVar(value="Loading player list…")
        ttk.Label(self.root, textvariable=self.status_var, padding=(10, 0)).pack(anchor=tk.W)

        table_frame = ttk.Frame(self.root, padding=10)
        table_frame.pack(fill=tk.BOTH, expand=True)

        cols = [c[0] for c in TABLE_COLUMNS]
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=20)
        for col_id, heading, width in TABLE_COLUMNS:
            self.tree.heading(col_id, text=heading)
            self.tree.column(col_id, width=width, minwidth=35, stretch=False)

        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

    def _season(self) -> int | None:
        try:
            return int(self.year_var.get().strip())
        except ValueError:
            return None

    def _player_suggestions(self, query: str) -> list[str]:
        if self.players is None:
            return []
        return search_players(query, self.players, season=self._season())

    def _resolve_batter_id(self) -> int | None:
        if self.players is None:
            return None

        text = self.player_search.get().strip()
        if not text:
            return None

        batter_id = label_to_id(text, self.players)
        if batter_id is not None:
            return batter_id

        season = self._season()
        matches = search_players(text, self.players, season=season, limit=5)
        if len(matches) == 1:
            self.player_search.set(matches[0])
            return label_to_id(matches[0], self.players)

        if len(matches) > 1:
            messagebox.showwarning(
                "Ambiguous name",
                "Several players match. Pick one from the suggestions dropdown.",
            )
        else:
            messagebox.showwarning("Not found", f"No player matching “{text}”.")
        return None

    def _load_players_async(self) -> None:
        def work() -> None:
            try:
                df = load_player_index()
                self._id_by_label = dict(zip(df["label"], df["key_mlbam"]))
                self.root.after(0, lambda: self._players_ready(df))
            except Exception as exc:
                self.root.after(0, lambda: self._players_failed(exc))

        threading.Thread(target=work, daemon=True).start()

    def _players_ready(self, df: pd.DataFrame) -> None:
        self.players = df
        self.load_btn.state(["!disabled"])
        self.status_var.set(f"Ready — {len(df):,} players loaded. Type a name to search.")

    def _players_failed(self, exc: Exception) -> None:
        self.status_var.set("Failed to load player list.")
        messagebox.showerror("Error", f"Could not load players:\n{exc}")

    def _on_load(self) -> None:
        season = self._season()
        if season is None:
            messagebox.showwarning("Invalid year", "Enter a valid season year (e.g. 2024).")
            return

        batter_id = self._resolve_batter_id()
        if batter_id is None:
            return

        self.load_btn.state(["disabled"])
        self.status_var.set(f"Fetching {self.player_search.get()} — {season}… (may take a minute)")

        def work() -> None:
            try:
                df = fetch_at_bats_for_batter_df(batter_id, season)
                self.root.after(0, lambda: self._show_table(df, season))
            except Exception as exc:
                self.root.after(0, lambda: self._load_failed(exc))

        threading.Thread(target=work, daemon=True).start()

    def _show_table(self, df: pd.DataFrame, season: int) -> None:
        self.tree.delete(*self.tree.get_children())
        cols = [c[0] for c in TABLE_COLUMNS]

        for _, row in df.iterrows():
            values = []
            for col in cols:
                val = row.get(col, "")
                if pd.isna(val):
                    val = ""
                values.append(val)
            self.tree.insert("", tk.END, values=values)

        name = self.player_search.get()
        self.status_var.set(f"{name} — {season}: {len(df)} plate appearances")
        self.load_btn.state(["!disabled"])

    def _load_failed(self, exc: Exception) -> None:
        self.status_var.set("Load failed.")
        self.load_btn.state(["!disabled"])
        messagebox.showerror("Error", f"Could not load at-bats:\n{exc}")

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    AtBatViewerApp().run()


if __name__ == "__main__":
    main()
