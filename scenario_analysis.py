from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

import pandas as pd


@dataclass
class Scenario:
    name: str
    sku: str
    service: str
    excluded_roles: list[str] = field(default_factory=list)
    excluded_privileges: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def add_nodes(self, node_ids: list[str]) -> None:
        for node_id in node_ids:
            kind, label = node_id.split(":", 1)
            target = self.excluded_roles if kind == "role" else self.excluded_privileges
            if label not in target:
                target.append(label)
        self.excluded_roles.sort()
        self.excluded_privileges.sort()


def scenario_impact(frame: pd.DataFrame, scenario: Scenario | None = None) -> dict[str, int]:
    """Return the access-based user impact after scenario exclusions."""
    baseline_users = set(frame["USER_LOGIN_HASH"].astype(str)) if not frame.empty else set()
    if scenario is None:
        return {"in_scope": len(baseline_users), "removed": 0, "affected": 0}
    excluded = frame[
        frame["ROLE_CODE"].isin(scenario.excluded_roles)
        | frame["PRIVILEGE"].isin(scenario.excluded_privileges)
    ]
    remaining = frame.drop(excluded.index)
    remaining_users = set(remaining["USER_LOGIN_HASH"].astype(str))
    return {
        "in_scope": len(remaining_users),
        "removed": len(baseline_users - remaining_users),
        "affected": int(excluded["USER_LOGIN_HASH"].nunique()),
    }


class ScenarioLibrary:
    def __init__(self) -> None:
        self.scenarios: list[Scenario] = []
        self.storage_dir = (
            Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
            / "SaaS Network Viewer"
            / "scenarios"
        )

    def for_sku(self, sku: str, service: str) -> list[Scenario]:
        return [item for item in self.scenarios if item.sku == sku and item.service == service]

    @staticmethod
    def _filename(name: str) -> str:
        cleaned = "".join("_" if char in '<>:"/\\|?*' else char for char in name).strip(" .")
        return f"{cleaned or 'Untitled scenario'}.json"

    def save_scenario(self, scenario: Scenario) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        path = self.storage_dir / self._filename(scenario.name)
        path.write_text(json.dumps(asdict(scenario), indent=2), encoding="utf-8")

    def load_saved(self) -> None:
        self.scenarios = []
        if not self.storage_dir.exists():
            return
        for path in self.storage_dir.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.scenarios.append(Scenario(**payload))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue


class ScenarioPicker(tk.Toplevel):
    """Modal picker that prevents users having to retype an existing name."""
    def __init__(
        self, parent: tk.Misc, scenarios: list[Scenario], *, x_root: int | None = None,
        y_root: int | None = None
    ) -> None:
        super().__init__(parent)
        self.title("Choose scenario")
        self.resizable(False, False)
        self.result: str | None = None
        self.scenarios = scenarios
        self.choice_var = tk.StringVar(value="Create new scenario…")
        self.name_var = tk.StringVar()
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Add the selected exclusions to").grid(row=0, column=0, sticky="w")
        self.choice = ttk.Combobox(body, textvariable=self.choice_var, state="readonly", width=42)
        self.choice["values"] = [item.name for item in scenarios] + ["Create new scenario…"]
        self.choice.grid(row=1, column=0, sticky="ew", pady=(2, 10))
        ttk.Label(body, text="New scenario name (only when creating a new scenario)").grid(row=2, column=0, sticky="w")
        name_entry = ttk.Entry(body, textvariable=self.name_var, width=45)
        name_entry.grid(row=3, column=0, sticky="ew", pady=(2, 12))
        name_entry.bind("<KeyRelease>", lambda _event: self.choice_var.set("Create new scenario…"))
        buttons = ttk.Frame(body)
        buttons.grid(row=4, column=0, sticky="e")
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Use scenario", command=self._accept).pack(side="right", padx=(0, 6))
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.transient(parent)
        self.update_idletasks()
        if x_root is not None and y_root is not None:
            width, height = self.winfo_reqwidth(), self.winfo_reqheight()
            x = min(x_root + 8, self.winfo_screenwidth() - width - 12)
            y = min(y_root + 8, self.winfo_screenheight() - height - 36)
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.grab_set()
        name_entry.focus_set()

    def _accept(self) -> None:
        choice = self.choice_var.get()
        if choice == "Create new scenario…":
            choice = self.name_var.get().strip()
            if not choice:
                messagebox.showwarning("Scenario name required", "Enter a name for the new scenario.", parent=self)
                return
        self.result = choice
        self.destroy()


class ScenarioEditor(tk.Toplevel):
    def __init__(self, parent: tk.Misc, scenario: Scenario, on_changed) -> None:
        super().__init__(parent)
        self.title(f"Edit scenario — {scenario.name}")
        self.geometry("760x440")
        self.minsize(600, 300)
        self.scenario, self.on_changed = scenario, on_changed
        ttk.Label(self, text="Remove exclusions that should no longer apply.", padding=10).pack(anchor="w")
        self.tree = ttk.Treeview(self, columns=("type", "name"), show="headings", selectmode="extended")
        self.tree.heading("type", text="Type")
        self.tree.heading("name", text="Excluded role or privilege")
        self.tree.column("type", width=110, stretch=False)
        self.tree.column("name", width=600, stretch=True)
        self.tree.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        buttons = ttk.Frame(self, padding=(10, 0, 10, 10))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Remove selected exclusions", command=self.remove_selected).pack(side="left")
        ttk.Button(buttons, text="Close", command=self.destroy).pack(side="right")
        self.fill()

    def fill(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for value in self.scenario.excluded_roles:
            self.tree.insert("", "end", iid=f"role:{value}", values=("Role", value))
        for value in self.scenario.excluded_privileges:
            self.tree.insert("", "end", iid=f"privilege:{value}", values=("Privilege", value))

    def remove_selected(self) -> None:
        for node_id in self.tree.selection():
            kind, value = node_id.split(":", 1)
            target = self.scenario.excluded_roles if kind == "role" else self.scenario.excluded_privileges
            if value in target:
                target.remove(value)
        self.fill()
        self.on_changed()

class ScenarioReport(tk.Toplevel):
    """Independent window for comparing baseline and saved scenarios."""
    def __init__(self, parent: tk.Misc, library: ScenarioLibrary, frame: pd.DataFrame, sku: str, service: str) -> None:
        super().__init__(parent)
        self.title("Scenario analysis report")
        self.geometry("1050x620")
        self.minsize(820, 480)
        self.library, self.frame, self.sku, self.service = library, frame.copy(), sku, service
        self.available = self.library.for_sku(sku, service)
        self.selection_vars = [tk.StringVar(), tk.StringVar()]
        self._build()
        self.refresh()

    def _build(self) -> None:
        head = ttk.Frame(self, padding=10)
        head.pack(fill="x")
        ttk.Label(head, text="Scenario analysis report", font=("Segoe UI", 15, "bold")).pack(side="left")
        ttk.Label(head, text=f"{self.sku} | {self.service}").pack(side="left", padx=14)
        ttk.Button(head, text="Reload saved scenarios", command=self.reload_saved).pack(side="right")
        ttk.Button(head, text="Edit selected scenario…", command=self.edit_selected).pack(side="right", padx=6)

        chooser = ttk.LabelFrame(self, text="Compare with the unrestricted baseline", padding=8)
        chooser.pack(fill="x", padx=10, pady=(0, 8))
        for index, variable in enumerate(self.selection_vars, start=1):
            ttk.Label(chooser, text=f"Scenario {index}").grid(row=0, column=(index - 1) * 2, sticky="w")
            combo = ttk.Combobox(chooser, textvariable=variable, state="readonly", width=42)
            combo.grid(row=1, column=(index - 1) * 2, padx=(0, 12), sticky="ew")
            combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
            setattr(self, f"combo_{index}", combo)
        ttk.Button(chooser, text="Refresh", command=self.refresh).grid(row=1, column=4, sticky="w")
        chooser.columnconfigure(0, weight=1)
        chooser.columnconfigure(2, weight=1)

        self.summary = ttk.Treeview(self, columns=("metric", "baseline", "first", "second"), show="headings", height=5)
        for column, heading, width in (("metric", "Measure", 285), ("baseline", "Baseline", 150), ("first", "Scenario 1", 220), ("second", "Scenario 2", 220)):
            self.summary.heading(column, text=heading)
            self.summary.column(column, width=width, anchor="w" if column == "metric" else "e", stretch=column == "metric")
        self.summary.pack(fill="x", padx=10)

        details = ttk.LabelFrame(self, text="Scenario exclusions", padding=7)
        details.pack(fill="both", expand=True, padx=10, pady=10)
        self.detail_tree = ttk.Treeview(details, columns=("scenario", "roles", "privileges"), show="headings")
        for column, heading, width in (("scenario", "Scenario", 200), ("roles", "Excluded roles", 370), ("privileges", "Excluded privileges", 370)):
            self.detail_tree.heading(column, text=heading)
            self.detail_tree.column(column, width=width, anchor="w", stretch=True)
        self.detail_tree.pack(fill="both", expand=True)
        ttk.Label(self, text="‘Estimated required licences’ is the remaining number of users with at least one non-excluded assignment. Confirm contractual licensing rules separately.").pack(anchor="w", padx=12, pady=(0, 8))

    def _selected(self, index: int) -> Scenario | None:
        name = self.selection_vars[index].get()
        return next((item for item in self.available if item.name == name), None)

    def refresh(self) -> None:
        self.available = self.library.for_sku(self.sku, self.service)
        names = [item.name for item in self.available]
        for index, variable in enumerate(self.selection_vars, start=1):
            combo = getattr(self, f"combo_{index}")
            combo["values"] = names
            if variable.get() not in names:
                variable.set("")
        scenarios = [self._selected(0), self._selected(1)]
        self.summary.heading("first", text=scenarios[0].name if scenarios[0] else "Scenario 1")
        self.summary.heading("second", text=scenarios[1].name if scenarios[1] else "Scenario 2")
        baseline = scenario_impact(self.frame)
        impacts = [scenario_impact(self.frame, item) if item else None for item in scenarios]
        self.summary.delete(*self.summary.get_children())
        metrics = (
            ("Estimated required licences (in-scope users)", "in_scope"),
            ("Users affected by exclusions", "affected"),
            ("Estimated licences reduced (users removed from scope)", "removed"),
        )
        for label, key in metrics:
            self.summary.insert("", "end", values=(label, f"{baseline[key]:,}", *(f"{item[key]:,}" if item else "—" for item in impacts)))
        self.detail_tree.delete(*self.detail_tree.get_children())
        for scenario in scenarios:
            if scenario:
                self.detail_tree.insert("", "end", values=(scenario.name, ", ".join(scenario.excluded_roles) or "—", ", ".join(scenario.excluded_privileges) or "—"))

    def edit_selected(self) -> None:
        scenario = self._selected(0) or self._selected(1)
        if scenario is None:
            messagebox.showinfo("Choose a scenario", "Select a scenario in either comparison list first.", parent=self)
            return
        ScenarioEditor(self, scenario, self._scenario_changed)

    def _scenario_changed(self) -> None:
        scenario = self._selected(0) or self._selected(1)
        if scenario:
            self.library.save_scenario(scenario)
        self.refresh()

    def reload_saved(self) -> None:
        self.library.load_saved()
        self.refresh()
