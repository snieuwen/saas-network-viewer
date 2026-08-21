from __future__ import annotations

from collections.abc import Iterable
import tkinter as tk
from tkinter import ttk

import pandas as pd


ASSIGNMENT_COLUMNS = ("USER_LOGIN_HASH", "ROLE_CODE", "PRIVILEGE")


def clean_assignments(frame: pd.DataFrame) -> pd.DataFrame:
    """Return the distinct user/role/privilege relationships used by all user views."""
    if frame.empty:
        return pd.DataFrame(columns=ASSIGNMENT_COLUMNS)
    return frame.loc[:, ASSIGNMENT_COLUMNS].drop_duplicates().copy()


def scenario_exclusion_mask(frame: pd.DataFrame, scenario: object | None) -> pd.Series:
    """Identify rows excluded by a scenario using the application's three exclusion types."""
    if frame.empty or scenario is None:
        return pd.Series(False, index=frame.index, dtype=bool)
    roles = getattr(scenario, "excluded_roles", [])
    privileges = getattr(scenario, "excluded_privileges", [])
    pairs = {
        (str(item.get("privilege", "")), str(item.get("role", "")))
        for item in getattr(scenario, "excluded_privilege_roles", [])
        if item.get("privilege") and item.get("role")
    }
    mask = frame["ROLE_CODE"].isin(roles) | frame["PRIVILEGE"].isin(privileges)
    if pairs:
        mask |= pd.Series(
            zip(frame["PRIVILEGE"].astype(str), frame["ROLE_CODE"].astype(str)),
            index=frame.index,
        ).isin(pairs)
    return mask


def scenario_user_summary(frame: pd.DataFrame, scenario: object | None = None) -> pd.DataFrame:
    """Summarise baseline and scenario assignment counts for every user."""
    clean = clean_assignments(frame)
    columns = (
        "USER",
        "ROLES",
        "PRIVILEGES",
        "RELATIONSHIPS",
        "EXCLUDED",
        "REMAINING",
        "STATUS",
    )
    if clean.empty:
        return pd.DataFrame(columns=columns)
    baseline = clean.groupby("USER_LOGIN_HASH").agg(
        ROLES=("ROLE_CODE", "nunique"),
        PRIVILEGES=("PRIVILEGE", "nunique"),
        RELATIONSHIPS=("ROLE_CODE", "size"),
    )
    excluded_mask = scenario_exclusion_mask(clean, scenario)
    excluded = clean[excluded_mask].groupby("USER_LOGIN_HASH").size()
    baseline["EXCLUDED"] = excluded.reindex(baseline.index, fill_value=0).astype(int)
    baseline["REMAINING"] = baseline["RELATIONSHIPS"] - baseline["EXCLUDED"]
    baseline["STATUS"] = "Unaffected"
    baseline.loc[baseline["EXCLUDED"].gt(0), "STATUS"] = "Affected"
    baseline.loc[baseline["REMAINING"].eq(0), "STATUS"] = "Removed from scope"
    return (
        baseline.reset_index(names="USER")
        .loc[:, columns]
        .sort_values(["EXCLUDED", "RELATIONSHIPS", "USER"], ascending=[False, False, True], kind="stable")
        .reset_index(drop=True)
    )


def selection_user_summary(
    filtered_frame: pd.DataFrame,
    selected_node_ids: Iterable[str],
    *,
    total_frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return users who hold every selected role and privilege, with context counts."""
    clean = clean_assignments(filtered_frame)
    selected = list(dict.fromkeys(str(value) for value in selected_node_ids))
    roles = {value.split(":", 1)[1] for value in selected if value.startswith("role:")}
    privileges = {
        value.split(":", 1)[1] for value in selected if value.startswith("privilege:")
    }
    columns = (
        "USER",
        "MATCHING_ROLES",
        "MATCHING_PRIVILEGES",
        "MATCHING_RELATIONSHIPS",
        "TOTAL_ROLES",
        "TOTAL_PRIVILEGES",
        "TOTAL_RELATIONSHIPS",
    )
    if clean.empty or not selected:
        return pd.DataFrame(columns=columns)
    users: set[str] | None = None
    for role in roles:
        node_users = set(clean.loc[clean["ROLE_CODE"].eq(role), "USER_LOGIN_HASH"].astype(str))
        users = node_users if users is None else users & node_users
    for privilege in privileges:
        node_users = set(clean.loc[clean["PRIVILEGE"].eq(privilege), "USER_LOGIN_HASH"].astype(str))
        users = node_users if users is None else users & node_users
    users = users or set()
    if not users:
        return pd.DataFrame(columns=columns)
    selected_rows = clean[clean["USER_LOGIN_HASH"].astype(str).isin(users)]
    touching = selected_rows[
        selected_rows["ROLE_CODE"].isin(roles) | selected_rows["PRIVILEGE"].isin(privileges)
    ]
    matching = selected_rows.groupby("USER_LOGIN_HASH").agg(
        MATCHING_ROLES=("ROLE_CODE", lambda values: len(set(values.astype(str)) & roles)),
        MATCHING_PRIVILEGES=(
            "PRIVILEGE", lambda values: len(set(values.astype(str)) & privileges)
        ),
    )
    matching["MATCHING_RELATIONSHIPS"] = touching.groupby("USER_LOGIN_HASH").size().reindex(
        matching.index, fill_value=0
    )
    totals_clean = clean_assignments(total_frame if total_frame is not None else filtered_frame)
    totals = totals_clean[totals_clean["USER_LOGIN_HASH"].astype(str).isin(users)].groupby(
        "USER_LOGIN_HASH"
    ).agg(
        TOTAL_ROLES=("ROLE_CODE", "nunique"),
        TOTAL_PRIVILEGES=("PRIVILEGE", "nunique"),
        TOTAL_RELATIONSHIPS=("ROLE_CODE", "size"),
    )
    result = matching.join(totals, how="left").reset_index(names="USER")
    return result.loc[:, columns].sort_values(
        ["MATCHING_RELATIONSHIPS", "TOTAL_RELATIONSHIPS", "USER"],
        ascending=[False, False, True],
        kind="stable",
    ).reset_index(drop=True)


def user_assignment_rows(
    frame: pd.DataFrame, user: str, scenario: object | None = None
) -> pd.DataFrame:
    """Return one user's assignments and the reason/status under a scenario."""
    clean = clean_assignments(frame)
    rows = clean[clean["USER_LOGIN_HASH"].astype(str).eq(str(user))].copy()
    if rows.empty:
        return pd.DataFrame(columns=("ROLE_CODE", "PRIVILEGE", "STATUS", "REASON"))
    mask = scenario_exclusion_mask(rows, scenario)
    roles = set(getattr(scenario, "excluded_roles", [])) if scenario else set()
    privileges = set(getattr(scenario, "excluded_privileges", [])) if scenario else set()
    pairs = {
        (str(item.get("privilege", "")), str(item.get("role", "")))
        for item in getattr(scenario, "excluded_privilege_roles", [])
    } if scenario else set()

    def reason(row: pd.Series) -> str:
        if row["ROLE_CODE"] in roles:
            return "Role excluded"
        if row["PRIVILEGE"] in privileges:
            return "Privilege excluded"
        if (str(row["PRIVILEGE"]), str(row["ROLE_CODE"])) in pairs:
            return "Privilege excluded from role"
        return ""

    rows["STATUS"] = mask.map({True: "Excluded", False: "Remaining"})
    rows["REASON"] = rows.apply(reason, axis=1)
    return rows.loc[:, ("ROLE_CODE", "PRIVILEGE", "STATUS", "REASON")].sort_values(
        ["STATUS", "ROLE_CODE", "PRIVILEGE"], kind="stable"
    ).reset_index(drop=True)


class UserAssignmentDialog(tk.Toplevel):
    """Show the complete assignment-level explanation for one hashed user."""

    def __init__(
        self,
        parent: tk.Misc,
        frame: pd.DataFrame,
        user: str,
        scenarios: list[object | None],
    ) -> None:
        super().__init__(parent)
        self.title(f"User assignments — {user}")
        self.geometry("1050x600")
        self.minsize(760, 420)
        ttk.Label(
            self,
            text=f"User (hashed): {user}",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 6))
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        choices = [("Baseline", None)] + [
            (str(getattr(scenario, "name", "Scenario")), scenario)
            for scenario in scenarios
            if scenario is not None
        ]
        scenario_tabs: list[ttk.Frame] = []
        for label, scenario in choices:
            tab = ttk.Frame(notebook)
            tab.rowconfigure(1, weight=1)
            tab.columnconfigure(0, weight=1)
            notebook.add(tab, text=label)
            if scenario is not None:
                scenario_tabs.append(tab)
            assignments = user_assignment_rows(frame, user, scenario)
            excluded = int(assignments["STATUS"].eq("Excluded").sum())
            remaining = int(assignments["STATUS"].ne("Excluded").sum())
            if scenario is None:
                summary = f"Baseline — {remaining:,} assignment(s); no scenario exclusions applied."
            else:
                user_status = (
                    "Removed from scope" if remaining == 0 else "Affected" if excluded else "Unaffected"
                )
                summary = (
                    f"{label} — {excluded:,} excluded, {remaining:,} remaining · "
                    f"User status: {user_status}"
                )
            ttk.Label(tab, text=summary, font=("Segoe UI", 10, "bold")).grid(
                row=0, column=0, columnspan=2, sticky="w", pady=(0, 5)
            )
            tree = ttk.Treeview(
                tab,
                columns=("ROLE", "PRIVILEGE", "STATUS", "REASON"),
                show="headings",
            )
            for column, heading, width in (
                ("ROLE", "Role", 300),
                ("PRIVILEGE", "Privilege", 390),
                ("STATUS", "Status", 100),
                ("REASON", "Reason", 190),
            ):
                tree.heading(column, text=heading, anchor="w")
                tree.column(column, width=width, anchor="w", stretch=column in {"ROLE", "PRIVILEGE"})
            y_scroll = ttk.Scrollbar(tab, orient="vertical", command=tree.yview)
            x_scroll = ttk.Scrollbar(tab, orient="horizontal", command=tree.xview)
            tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
            tree.grid(row=1, column=0, sticky="nsew")
            y_scroll.grid(row=1, column=1, sticky="ns")
            x_scroll.grid(row=2, column=0, sticky="ew")
            for row in assignments.itertuples(index=False):
                status = "Baseline" if scenario is None else row.STATUS
                tree.insert("", "end", values=(row.ROLE_CODE, row.PRIVILEGE, status, row.REASON))
        if scenario_tabs:
            notebook.select(scenario_tabs[-1])


class UserExplorer(tk.Toplevel):
    """Search and compare user-level access for the selected SKU."""

    def __init__(
        self,
        parent: tk.Misc,
        frame: pd.DataFrame,
        scenarios: list[object],
        *,
        on_focus_user=None,
    ) -> None:
        super().__init__(parent)
        self.title("User explorer")
        self.geometry("1120x660")
        self.minsize(820, 480)
        self.frame = frame.copy()
        self.scenarios = list(scenarios)
        self.on_focus_user = on_focus_user
        self.search_var = tk.StringVar()
        self.scenario_var = tk.StringVar(value="Baseline")
        self.status_var = tk.StringVar(value="All users")
        self.current = pd.DataFrame()
        self._build()
        self.refresh()

    def _build(self) -> None:
        head = ttk.Frame(self, padding=10)
        head.pack(fill="x")
        ttk.Label(head, text="User explorer", font=("Segoe UI", 15, "bold")).pack(side="left")
        ttk.Label(head, text="Search hashed user ID").pack(side="left", padx=(24, 5))
        search = ttk.Entry(head, textvariable=self.search_var, width=26)
        search.pack(side="left")
        ttk.Label(head, text="Scenario").pack(side="left", padx=(18, 5))
        scenario = ttk.Combobox(
            head,
            textvariable=self.scenario_var,
            values=["Baseline", *(str(getattr(item, "name", "")) for item in self.scenarios)],
            state="readonly",
            width=24,
        )
        scenario.pack(side="left")
        ttk.Label(head, text="Status").pack(side="left", padx=(18, 5))
        status = ttk.Combobox(
            head,
            textvariable=self.status_var,
            values=("All users", "Affected", "Removed from scope", "Unaffected"),
            state="readonly",
            width=19,
        )
        status.pack(side="left")
        search.bind("<KeyRelease>", lambda _event: self.refresh())
        scenario.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
        status.bind("<<ComboboxSelected>>", lambda _event: self.refresh())

        body = ttk.Frame(self, padding=(10, 0, 10, 10))
        body.pack(fill="both", expand=True)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        columns = ("USER", "ROLES", "PRIVILEGES", "RELATIONSHIPS", "EXCLUDED", "REMAINING", "STATUS")
        self.tree = ttk.Treeview(body, columns=columns, show="headings")
        for column, heading, width in (
            ("USER", "User (hashed)", 290),
            ("ROLES", "Roles", 80),
            ("PRIVILEGES", "Privileges", 90),
            ("RELATIONSHIPS", "Relationships", 105),
            ("EXCLUDED", "Excluded", 90),
            ("REMAINING", "Remaining", 90),
            ("STATUS", "Status", 150),
        ):
            self.tree.heading(column, text=heading, command=lambda c=column: self.sort(c), anchor="w")
            self.tree.column(column, width=width, anchor="w" if column in {"USER", "STATUS"} else "e")
        y_scroll = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(body, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<Double-1>", lambda _event: self.open_selected())
        actions = ttk.Frame(self, padding=(10, 0, 10, 10))
        actions.pack(fill="x")
        self.count_var = tk.StringVar()
        ttk.Label(actions, textvariable=self.count_var).pack(side="left")
        ttk.Button(actions, text="View assignments…", command=self.open_selected).pack(side="right")
        ttk.Button(actions, text="Focus user in network", command=self.focus_selected).pack(side="right", padx=6)

    def selected_scenario(self) -> object | None:
        name = self.scenario_var.get()
        return next((item for item in self.scenarios if getattr(item, "name", "") == name), None)

    def refresh(self) -> None:
        current = scenario_user_summary(self.frame, self.selected_scenario())
        query = self.search_var.get().strip()
        if query:
            current = current[current["USER"].str.contains(query, case=False, regex=False, na=False)]
        status = self.status_var.get()
        if status != "All users":
            current = current[current["STATUS"].eq(status)]
        self.current = current.reset_index(drop=True)
        self._fill()

    def _fill(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for row in self.current.itertuples(index=False):
            self.tree.insert(
                "", "end", iid=str(row.USER),
                values=(row.USER, f"{row.ROLES:,}", f"{row.PRIVILEGES:,}", f"{row.RELATIONSHIPS:,}",
                        f"{row.EXCLUDED:,}", f"{row.REMAINING:,}", row.STATUS),
            )
        self.count_var.set(f"{len(self.current):,} users shown")

    def sort(self, column: str) -> None:
        if self.current.empty:
            return
        numeric = column not in {"USER", "STATUS"}
        state = getattr(self, "_sort_state", ("EXCLUDED", True))
        descending = not state[1] if state[0] == column else numeric
        self._sort_state = (column, descending)
        self.current = self.current.sort_values(
            [column, "USER"] if column != "USER" else ["USER"],
            ascending=[not descending, True] if column != "USER" else [not descending],
            kind="stable",
        )
        self._fill()

    def selected_user(self) -> str | None:
        selection = self.tree.selection()
        return str(selection[0]) if selection else None

    def open_selected(self) -> None:
        user = self.selected_user()
        if user:
            UserAssignmentDialog(self, self.frame, user, [self.selected_scenario()])

    def focus_selected(self) -> None:
        user = self.selected_user()
        if user and self.on_focus_user:
            self.on_focus_user(user)
            self.destroy()
