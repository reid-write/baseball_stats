"""Entry widget with a type-ahead suggestion list (works on macOS)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk


class AutocompleteEntry(ttk.Frame):
    """Text field that shows matching suggestions in a popup list below."""

    def __init__(
        self,
        master: tk.Misc,
        get_suggestions: Callable[[str], list[str]],
        width: int = 40,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self.get_suggestions = get_suggestions
        self.var = tk.StringVar()
        self._suggestions: list[str] = []
        self._popup: tk.Toplevel | None = None
        self._listbox: tk.Listbox | None = None

        self.entry = ttk.Entry(self, textvariable=self.var, width=width)
        self.entry.pack(fill=tk.X)
        self.entry.bind("<KeyRelease>", self._on_key)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self.var.trace_add("write", self._on_text_changed)

    def get(self) -> str:
        return self.var.get()

    def set(self, value: str) -> None:
        self.var.set(value)

    def focus(self) -> None:
        self.entry.focus_set()

    def bind_select(self, callback: Callable[[], None]) -> None:
        self._select_callback = callback

    def _on_text_changed(self, *_args) -> None:
        self.after_idle(self._refresh_suggestions)

    def _on_key(self, event: tk.Event) -> str | None:
        if self._popup and self._listbox and event.keysym in ("Up", "Down", "Return", "Escape"):
            return self._navigate(event.keysym)
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return None
        self.after_idle(self._refresh_suggestions)
        return None

    def _navigate(self, keysym: str) -> str | None:
        assert self._listbox is not None
        size = self._listbox.size()
        if size == 0:
            return "break" if keysym == "Return" else None

        cur = self._listbox.curselection()
        idx = cur[0] if cur else -1

        if keysym == "Down":
            idx = min(idx + 1, size - 1)
            self._listbox.selection_clear(0, tk.END)
            self._listbox.selection_set(idx)
            self._listbox.activate(idx)
            self._listbox.see(idx)
        elif keysym == "Up":
            idx = max(idx - 1, 0) if idx >= 0 else 0
            self._listbox.selection_clear(0, tk.END)
            self._listbox.selection_set(idx)
            self._listbox.activate(idx)
            self._listbox.see(idx)
        elif keysym == "Return":
            if cur or idx >= 0:
                pick = idx if idx >= 0 else cur[0]
                self._apply(self._listbox.get(pick))
            self._hide_popup()
        elif keysym == "Escape":
            self._hide_popup()

        return "break"

    def _on_focus_out(self, _event: tk.Event) -> None:
        self.after(200, self._hide_if_focus_lost)

    def _hide_if_focus_lost(self) -> None:
        focus = self.focus_get()
        if focus is self.entry:
            return
        if self._listbox is not None and focus is self._listbox:
            return
        self._hide_popup()

    def _refresh_suggestions(self) -> None:
        text = self.var.get()
        self._suggestions = self.get_suggestions(text)
        if not self._suggestions:
            self._hide_popup()
            return
        self._show_popup(self._suggestions)

    def _show_popup(self, suggestions: list[str]) -> None:
        if self._popup is None:
            self._popup = tk.Toplevel(self)
            self._popup.wm_overrideredirect(True)
            self._popup.attributes("-topmost", True)
            self._listbox = tk.Listbox(
                self._popup,
                height=min(8, len(suggestions)),
                activestyle="dotbox",
                exportselection=False,
            )
            self._listbox.pack()
            self._listbox.bind("<ButtonRelease-1>", self._on_click)
            self._listbox.bind("<Double-Button-1>", self._on_click)

        assert self._listbox is not None
        self._listbox.config(height=min(8, len(suggestions)))
        self._listbox.delete(0, tk.END)
        for item in suggestions:
            self._listbox.insert(tk.END, item)

        self.entry.update_idletasks()
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()
        w = max(self.entry.winfo_width(), 280)
        self._popup.geometry(f"{w}x{min(8, len(suggestions)) * 22}+{x}+{y}")
        self._popup.deiconify()

    def _hide_popup(self) -> None:
        if self._popup is not None:
            self._popup.withdraw()

    def _on_click(self, _event: tk.Event) -> None:
        if self._listbox is None:
            return
        cur = self._listbox.curselection()
        if cur:
            self._apply(self._listbox.get(cur[0]))
        self._hide_popup()
        self.entry.focus_set()

    def _apply(self, value: str) -> None:
        self.var.set(value)
        if hasattr(self, "_select_callback"):
            self._select_callback()
