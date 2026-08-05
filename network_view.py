from __future__ import annotations

import math
import os
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pandas as pd

from access_analysis import build_network_data


KIND_LABELS = {"role": "Roles", "privilege": "Privileges"}
KIND_COLOURS = {"role": "#F2B134", "privilege": "#63B995"}
MINIMUM_NODE_LIMIT = 10
DEFAULT_ROLE_LIMIT = 30
DEFAULT_PRIVILEGE_LIMIT = 30
DEFAULT_RELATIONSHIP_LIMIT = 30
DEFAULT_MINIMUM_SHARED = 1


class NetworkView(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.frame = pd.DataFrame()
        self.workbook_info: dict[str, object] = {}
        self.source_path = Path()
        self.nodes = pd.DataFrame()
        self.edges = pd.DataFrame()
        self.expanded_nodes = pd.DataFrame()
        self.expanded_edges = pd.DataFrame()
        self.expansion_added_nodes = 0
        self.expansion_connection_count = 0
        self.positions: dict[str, tuple[float, float]] = {}
        self.node_items: dict[int, str] = {}
        self.edge_items: dict[int, tuple[str, str, int]] = {}
        self.neighbours: dict[str, set[str]] = {}
        self.key_nodes: set[str] = set()
        self.selected_node: str | None = None
        self.hover_item: tuple[str, object] | None = None
        self.current_details = pd.DataFrame()
        self.max_node_weight = 1
        self.max_edge_weight = 1
        self.zoom_factor = 1.0
        self.search_job: str | None = None
        self.empty_message = "Select a SKU to display its network."

        self.roles_var = tk.StringVar(value=str(DEFAULT_ROLE_LIMIT))
        self.privileges_var = tk.StringVar(value=str(DEFAULT_PRIVILEGE_LIMIT))
        self.min_shared_var = tk.StringVar(value=str(DEFAULT_MINIMUM_SHARED))
        self.relationships_var = tk.StringVar(value=str(DEFAULT_RELATIONSHIP_LIMIT))
        self.role_search_var = tk.StringVar()
        self.privilege_search_var = tk.StringVar()
        self.role_total_var = tk.StringVar(value="0 visible")
        self.privilege_total_var = tk.StringVar(value="0 visible")
        self.network_summary_var = tk.StringVar(value="No network loaded")
        self.filter_error_var = tk.StringVar()
        self.detail_var = tk.StringVar(value="Select a node to inspect its relationships.")
        self.selection_users_var = tk.StringVar(value="Users matching current filters: —")
        self.detail_scope_var = tk.StringVar(value="visible")
        self.expand_selected_var = tk.BooleanVar(value=True)
        self.focus_mode_var = tk.BooleanVar(value=False)

        self._build_controls()
        self._build_canvas()
        self._build_details()
        self.after(500, self._set_initial_sash)

    def _build_controls(self) -> None:
        filters = ttk.LabelFrame(self, text="Network filters", padding=(8, 6))
        filters.pack(fill="x", pady=(0, 6))
        for column in (1, 5):
            filters.columnconfigure(column, weight=1)

        ttk.Label(filters, text="Search roles").grid(row=0, column=0, sticky="w")
        role_search = ttk.Entry(filters, textvariable=self.role_search_var)
        role_search.grid(row=0, column=1, sticky="ew", padx=(5, 12))
        ttk.Label(filters, text="Maximum roles").grid(row=0, column=2, sticky="w")
        role_limit = ttk.Spinbox(
            filters,
            from_=MINIMUM_NODE_LIMIT,
            to=100000,
            textvariable=self.roles_var,
            width=5,
            command=self.schedule_refresh,
        )
        role_limit.grid(row=0, column=3, sticky="w", padx=(5, 18))
        self.role_limit_spinbox = role_limit

        ttk.Label(filters, text="Search privileges").grid(row=0, column=4, sticky="w")
        privilege_search = ttk.Entry(filters, textvariable=self.privilege_search_var)
        privilege_search.grid(row=0, column=5, sticky="ew", padx=(5, 12))
        ttk.Label(filters, text="Maximum privileges").grid(row=0, column=6, sticky="w")
        privilege_limit = ttk.Spinbox(
            filters,
            from_=MINIMUM_NODE_LIMIT,
            to=100000,
            textvariable=self.privileges_var,
            width=5,
            command=self.schedule_refresh,
        )
        privilege_limit.grid(row=0, column=7, sticky="w", padx=(5, 0))
        self.privilege_limit_spinbox = privilege_limit

        ttk.Label(filters, text="Minimum shared users").grid(row=1, column=0, sticky="w", pady=(7, 0))
        minimum_shared = ttk.Spinbox(
            filters,
            from_=1,
            to=100000,
            textvariable=self.min_shared_var,
            width=8,
            command=self.schedule_refresh,
        )
        minimum_shared.grid(row=1, column=1, sticky="w", padx=(5, 12), pady=(7, 0))
        ttk.Label(filters, text="Maximum relationships").grid(row=1, column=2, sticky="w", pady=(7, 0))
        relationship_limit = ttk.Spinbox(
            filters,
            from_=1,
            to=500,
            textvariable=self.relationships_var,
            width=6,
            command=self.schedule_refresh,
        )
        relationship_limit.grid(row=1, column=3, sticky="w", padx=(5, 18), pady=(7, 0))
        ttk.Button(filters, text="Apply filters", command=self.refresh).grid(
            row=1, column=4, sticky="w", pady=(7, 0)
        )
        ttk.Button(filters, text="Reset filters", command=self.reset_filters).grid(
            row=1, column=5, sticky="w", padx=(5, 18), pady=(7, 0)
        )
        ttk.Checkbutton(
            filters,
            text="Show only selected node's connections",
            variable=self.focus_mode_var,
            command=self._selection_options_changed,
        ).grid(row=1, column=6, columnspan=2, sticky="w", pady=(7, 0))
        ttk.Checkbutton(
            filters,
            text="Show all connections for selected node",
            variable=self.expand_selected_var,
            command=self._selection_options_changed,
        ).grid(row=2, column=4, columnspan=4, sticky="e", pady=(4, 0))
        ttk.Label(filters, textvariable=self.network_summary_var).grid(
            row=3, column=4, columnspan=4, sticky="e", padx=(10, 0), pady=(4, 0)
        )
        ttk.Label(filters, textvariable=self.filter_error_var, style="Error.TLabel").grid(
            row=4, column=0, columnspan=8, sticky="w", pady=(4, 0)
        )
        ttk.Label(filters, textvariable=self.role_total_var).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )
        ttk.Label(filters, textvariable=self.privilege_total_var).grid(
            row=2, column=2, columnspan=2, sticky="w", pady=(4, 0)
        )

        for widget in (role_search, privilege_search):
            widget.bind("<Escape>", lambda _event: self.reset_filters())
        for widget in (role_limit, privilege_limit, minimum_shared, relationship_limit):
            widget.bind("<Return>", lambda _event: self.refresh())
            widget.bind("<FocusOut>", lambda _event: self.refresh())
        self.role_search_var.trace_add("write", lambda *_: self.schedule_refresh())
        self.privilege_search_var.trace_add("write", lambda *_: self.schedule_refresh())

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(0, 5))
        role_swatch = tk.Canvas(actions, width=14, height=14, highlightthickness=0)
        role_swatch.create_oval(2, 2, 12, 12, fill=KIND_COLOURS["role"], outline="")
        role_swatch.pack(side="left", padx=(0, 3))
        ttk.Label(actions, text="Roles").pack(side="left")
        privilege_swatch = tk.Canvas(actions, width=14, height=14, highlightthickness=0)
        privilege_swatch.create_rectangle(2, 2, 12, 12, fill=KIND_COLOURS["privilege"], outline="")
        privilege_swatch.pack(side="left", padx=(14, 3))
        ttk.Label(actions, text="Privileges").pack(side="left")
        ttk.Label(actions, text="★ Most connected visible nodes").pack(side="left", padx=(14, 0))

        ttk.Button(actions, text="Export PNG…", command=self.export_png).pack(side="right")
        ttk.Button(actions, text="Export Excel…", command=self.export_excel).pack(side="right", padx=6)
        ttk.Button(actions, text="Fit width", command=self.fit_width).pack(side="right", padx=(12, 3))
        ttk.Button(actions, text="+", width=3, command=lambda: self._zoom_by(1.15)).pack(side="right")
        ttk.Button(actions, text="−", width=3, command=lambda: self._zoom_by(1 / 1.15)).pack(side="right", padx=3)
        ttk.Label(actions, text="Node size = total SKU users; line width = shared SKU users").pack(
            side="right", padx=12
        )

    def _build_canvas(self) -> None:
        self.pane = ttk.Panedwindow(self, orient="vertical")
        self.pane.pack(fill="both", expand=True)
        canvas_frame = ttk.Frame(self.pane)
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            canvas_frame,
            background="#FFFFFF",
            highlightthickness=1,
            highlightbackground="#C7CDD4",
        )
        x_scroll = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        y_scroll = ttk.Scrollbar(canvas_frame, orient="vertical", command=self._scroll_canvas_y)
        self.canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.canvas.bind("<Configure>", lambda _event: self.after_idle(self.draw))
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Motion>", self._on_hover)
        self.canvas.bind("<Leave>", lambda _event: self._hide_tooltip())
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<ButtonPress-2>", lambda event: self.canvas.scan_mark(event.x, event.y))
        self.canvas.bind("<B2-Motion>", self._scan_drag_canvas)
        self.canvas.bind_all("<Escape>", lambda _event: self.clear_focus())
        self.pane.add(canvas_frame, weight=4)

    def _build_details(self) -> None:
        detail_frame = ttk.Frame(self.pane, padding=(0, 5, 0, 0))
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(1, weight=1)
        header = ttk.Frame(detail_frame)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        ttk.Label(header, textvariable=self.detail_var).pack(side="left", fill="x", expand=True)
        ttk.Button(header, text="Clear selection", command=self.clear_focus).pack(side="right")
        self.all_scope_button = ttk.Radiobutton(
            header,
            text="All relationships",
            value="all",
            variable=self.detail_scope_var,
            command=self._update_detail_for_selection,
        )
        self.all_scope_button.pack(side="right", padx=(8, 0))
        self.visible_scope_button = ttk.Radiobutton(
            header,
            text="Visible relationships",
            value="visible",
            variable=self.detail_scope_var,
            command=self._update_detail_for_selection,
        )
        self.visible_scope_button.pack(side="right", padx=(8, 0))
        ttk.Label(header, textvariable=self.selection_users_var, font=("Segoe UI", 10, "bold")).pack(
            side="right", padx=(12, 8)
        )

        self.detail_tree = ttk.Treeview(
            detail_frame,
            columns=("TYPE", "NAME", "USERS", "SHARED_USERS"),
            show="headings",
            height=4,
            selectmode="extended",
        )
        for column, heading, width, anchor in (
            ("TYPE", "Type", 100, "w"),
            ("NAME", "Connected role or privilege", 650, "w"),
            ("USERS", "Total SKU users", 120, "e"),
            ("SHARED_USERS", "Shared users", 110, "e"),
        ):
            self.detail_tree.heading(column, text=heading, command=lambda c=column: self._sort_details(c))
            self.detail_tree.column(column, width=width, anchor=anchor, stretch=column == "NAME")
        detail_y = ttk.Scrollbar(detail_frame, orient="vertical", command=self.detail_tree.yview)
        detail_x = ttk.Scrollbar(detail_frame, orient="horizontal", command=self.detail_tree.xview)
        self.detail_tree.configure(yscrollcommand=detail_y.set, xscrollcommand=detail_x.set)
        self.detail_tree.grid(row=1, column=0, sticky="nsew")
        detail_y.grid(row=1, column=1, sticky="ns")
        detail_x.grid(row=2, column=0, sticky="ew")
        self.detail_tree.bind("<Double-1>", self._focus_detail_row)
        self.detail_tree.bind("<Return>", self._focus_detail_row)
        self.detail_tree.bind("<Control-c>", self._copy_detail_rows)
        self.pane.add(detail_frame, weight=1)
        self.clear_selection_button = next(
            widget for widget in header.winfo_children() if isinstance(widget, ttk.Button)
        )
        self._set_detail_actions_enabled(False)

    def _set_initial_sash(self) -> None:
        height = self.pane.winfo_height()
        if height > 0:
            self.pane.sashpos(0, max(220, int(height * 0.72)))

    def _set_detail_actions_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.visible_scope_button.configure(state=state)
        self.all_scope_button.configure(state=state)
        self.clear_selection_button.configure(state=state)

    def set_data(self, frame: pd.DataFrame) -> None:
        self.frame = frame.copy()
        self.selected_node = None
        self._set_detail_actions_enabled(False)
        self.role_search_var.set("")
        self.privilege_search_var.set("")
        if self.search_job is not None:
            self.after_cancel(self.search_job)
            self.search_job = None
        role_weights = self.frame.groupby("ROLE_CODE")["USER_LOGIN_HASH"].nunique()
        privilege_weights = self.frame.groupby("PRIVILEGE")["USER_LOGIN_HASH"].nunique()
        edge_weights = self.frame.groupby(["ROLE_CODE", "PRIVILEGE"])["USER_LOGIN_HASH"].nunique()
        role_limit_max = max(MINIMUM_NODE_LIMIT, int(self.frame["ROLE_CODE"].nunique()))
        privilege_limit_max = max(MINIMUM_NODE_LIMIT, int(self.frame["PRIVILEGE"].nunique()))
        self.role_limit_spinbox.configure(to=role_limit_max)
        self.privilege_limit_spinbox.configure(to=privilege_limit_max)
        if int(self.roles_var.get()) > role_limit_max:
            self.roles_var.set(str(role_limit_max))
        if int(self.privileges_var.get()) > privilege_limit_max:
            self.privileges_var.set(str(privilege_limit_max))
        self.max_node_weight = max(
            1,
            int(role_weights.max()) if not role_weights.empty else 1,
            int(privilege_weights.max()) if not privilege_weights.empty else 1,
        )
        self.max_edge_weight = max(1, int(edge_weights.max()) if not edge_weights.empty else 1)
        self.refresh()

    def set_workbook_info(self, info: dict[str, object], source: str | Path) -> None:
        self.workbook_info = dict(info)
        self.source_path = Path(source)

    def schedule_refresh(self) -> None:
        if self.search_job is not None:
            self.after_cancel(self.search_job)
        self.search_job = self.after(300, self.refresh)

    def _filter_values(self) -> tuple[int, int, int, int] | None:
        try:
            roles = int(self.roles_var.get())
            privileges = int(self.privileges_var.get())
            relationships = int(self.relationships_var.get())
            minimum = int(self.min_shared_var.get())
        except (TypeError, ValueError, tk.TclError):
            self.filter_error_var.set("Limits and minimum shared users must be whole numbers.")
            return None
        maximum_roles = max(MINIMUM_NODE_LIMIT, int(self.frame["ROLE_CODE"].nunique()))
        maximum_privileges = max(MINIMUM_NODE_LIMIT, int(self.frame["PRIVILEGE"].nunique()))
        if not MINIMUM_NODE_LIMIT <= roles <= maximum_roles:
            self.filter_error_var.set(
                f"Maximum roles must be between {MINIMUM_NODE_LIMIT} and {maximum_roles:,}."
            )
            return None
        if not MINIMUM_NODE_LIMIT <= privileges <= maximum_privileges:
            self.filter_error_var.set(
                f"Maximum privileges must be between {MINIMUM_NODE_LIMIT} and {maximum_privileges:,}."
            )
            return None
        if not 1 <= relationships <= 500:
            self.filter_error_var.set("Maximum relationships must be between 1 and 500.")
            return None
        if not 1 <= minimum <= 100000:
            self.filter_error_var.set("Minimum shared users must be between 1 and 100,000.")
            return None
        self.filter_error_var.set("")
        return roles, privileges, relationships, minimum

    def refresh(self) -> None:
        self.search_job = None
        if self.frame.empty:
            self.nodes = pd.DataFrame()
            self.edges = pd.DataFrame()
            self._clear_selected_expansion()
            self.role_total_var.set("0 visible")
            self.privilege_total_var.set("0 visible")
            self.network_summary_var.set("No SKU selected")
            self.selection_users_var.set("Users matching current filters: —")
            self.detail_var.set("Select a SKU to display its network.")
            self.empty_message = "Select a SKU to display its network."
            self._fill_detail_tree(pd.DataFrame())
            self.draw()
            return
        values = self._filter_values()
        if values is None:
            return
        max_roles, max_privileges, max_relationships, minimum = values
        self.nodes, self.edges = build_network_data(
            self.frame,
            max_roles=max_roles,
            max_privileges=max_privileges,
            max_relationships=max_relationships,
            role_query=self.role_search_var.get(),
            privilege_query=self.privilege_search_var.get(),
            min_shared_users=minimum,
        )
        filtered = self._filtered_assignments()
        total_roles = self.frame["ROLE_CODE"].nunique()
        total_privileges = self.frame["PRIVILEGE"].nunique()
        match_roles = filtered["ROLE_CODE"].nunique()
        match_privileges = filtered["PRIVILEGE"].nunique()
        visible_roles = int(self.nodes["KIND"].eq("role").sum()) if not self.nodes.empty else 0
        visible_privileges = int(self.nodes["KIND"].eq("privilege").sum()) if not self.nodes.empty else 0
        available_roles = match_roles if self.role_search_var.get().strip() else total_roles
        available_privileges = match_privileges if self.privilege_search_var.get().strip() else total_privileges
        role_context = "matching" if self.role_search_var.get().strip() else "available"
        privilege_context = "matching" if self.privilege_search_var.get().strip() else "available"
        eligible_relationships = (
            filtered.groupby(["ROLE_CODE", "PRIVILEGE"])["USER_LOGIN_HASH"]
            .nunique()
            .ge(minimum)
        )
        total_relationships = int(eligible_relationships.sum())
        self.role_total_var.set(f"Roles: {visible_roles:,} shown of {available_roles:,} {role_context}")
        self.privilege_total_var.set(
            f"Privileges: {visible_privileges:,} shown of {available_privileges:,} {privilege_context}"
        )
        self.network_summary_var.set(
            f"{visible_roles:,}/{available_roles:,} roles · "
            f"{visible_privileges:,}/{available_privileges:,} privileges · "
            f"{len(self.edges):,}/{total_relationships:,} relationships"
        )
        self.selection_users_var.set(
            f"Users matching current filters: {filtered['USER_LOGIN_HASH'].nunique():,}"
        )
        self.selected_node = None
        self._clear_selected_expansion()
        self._build_neighbours()
        self._fill_detail_tree(pd.DataFrame())
        if filtered.empty:
            self.empty_message = "No role or privilege names match the current search. Reset the filters to continue."
        elif self.nodes.empty:
            self.empty_message = (
                f"No relationships have at least {minimum:,} shared users. Lower the minimum to continue."
            )
        else:
            self.empty_message = "No network data"
        self.detail_var.set(
            f"Showing {visible_roles:,} roles and {visible_privileges:,} privileges. "
            "Select a node to highlight its relationships."
        )
        self.visible_scope_button.configure(text="Visible relationships")
        self.all_scope_button.configure(text="All relationships")
        self.draw()

    def reset_filters(self) -> None:
        if self.search_job is not None:
            self.after_cancel(self.search_job)
            self.search_job = None
        maximum_roles = max(MINIMUM_NODE_LIMIT, int(self.frame["ROLE_CODE"].nunique()))
        maximum_privileges = max(MINIMUM_NODE_LIMIT, int(self.frame["PRIVILEGE"].nunique()))
        self.roles_var.set(str(min(DEFAULT_ROLE_LIMIT, maximum_roles)))
        self.privileges_var.set(str(min(DEFAULT_PRIVILEGE_LIMIT, maximum_privileges)))
        self.min_shared_var.set(str(DEFAULT_MINIMUM_SHARED))
        self.relationships_var.set(str(DEFAULT_RELATIONSHIP_LIMIT))
        self.role_search_var.set("")
        self.privilege_search_var.set("")
        if self.search_job is not None:
            self.after_cancel(self.search_job)
            self.search_job = None
        self.refresh()

    def _filtered_assignments(self) -> pd.DataFrame:
        filtered = self.frame
        role_query = self.role_search_var.get().strip()
        privilege_query = self.privilege_search_var.get().strip()
        if role_query:
            filtered = filtered[
                filtered["ROLE_CODE"].str.contains(role_query, case=False, regex=False, na=False)
            ]
        if privilege_query:
            filtered = filtered[
                filtered["PRIVILEGE"].str.contains(
                    privilege_query, case=False, regex=False, na=False
                )
            ]
        return filtered

    def _build_neighbours(self) -> None:
        self.neighbours = {str(node_id): set() for node_id in self.nodes.get("ID", [])}
        edge_weights: dict[str, int] = {node_id: 0 for node_id in self.neighbours}
        for edge in self.edges.itertuples(index=False):
            source, target = str(edge.SOURCE), str(edge.TARGET)
            self.neighbours.setdefault(source, set()).add(target)
            self.neighbours.setdefault(target, set()).add(source)
            edge_weights[source] = edge_weights.get(source, 0) + int(edge.WEIGHT)
            edge_weights[target] = edge_weights.get(target, 0) + int(edge.WEIGHT)
        self.key_nodes = set()
        for kind in ("role", "privilege"):
            candidates = self.nodes[self.nodes["KIND"].eq(kind)].copy()
            if len(candidates) < 4:
                continue
            candidates["CONNECTIONS"] = candidates["ID"].map(
                lambda value: len(self.neighbours.get(str(value), set()))
            )
            candidates["SHARED_TOTAL"] = candidates["ID"].map(
                lambda value: edge_weights.get(str(value), 0)
            )
            key_count = min(3, max(1, len(candidates) // 5))
            leaders = candidates.sort_values(
                ["CONNECTIONS", "SHARED_TOTAL", "WEIGHT", "LABEL"],
                ascending=[False, False, False, True],
                kind="stable",
            ).head(key_count)
            self.key_nodes.update(leaders.loc[leaders["CONNECTIONS"].gt(0), "ID"].astype(str))

    @staticmethod
    def _neighbours_for_edges(edges: pd.DataFrame) -> dict[str, set[str]]:
        neighbours: dict[str, set[str]] = {}
        for edge in edges.itertuples(index=False):
            source, target = str(edge.SOURCE), str(edge.TARGET)
            neighbours.setdefault(source, set()).add(target)
            neighbours.setdefault(target, set()).add(source)
        return neighbours

    def _clear_selected_expansion(self) -> None:
        self.expanded_nodes = pd.DataFrame()
        self.expanded_edges = pd.DataFrame()
        self.expansion_added_nodes = 0
        self.expansion_connection_count = 0

    def _build_selected_expansion(self) -> None:
        self._clear_selected_expansion()
        if not self.selected_node or not self.expand_selected_var.get() or self.frame.empty:
            return
        kind, label = self.selected_node.split(":", 1)
        filtered = self._filtered_assignments()
        try:
            minimum = max(1, int(self.min_shared_var.get()))
        except (TypeError, ValueError, tk.TclError):
            return

        if kind == "role":
            selected_column = "ROLE_CODE"
            connected_column = "PRIVILEGE"
            connected_kind = "privilege"
        else:
            selected_column = "PRIVILEGE"
            connected_column = "ROLE_CODE"
            connected_kind = "role"

        selected_rows = filtered[filtered[selected_column].eq(label)]
        connection_weights = (
            selected_rows.groupby(connected_column)["USER_LOGIN_HASH"]
            .nunique()
            .loc[lambda values: values.ge(minimum)]
            .sort_values(ascending=False, kind="stable")
        )
        self.expansion_connection_count = int(len(connection_weights))

        node_rows: list[dict[str, object]] = []
        selected_users = int(
            self.frame.loc[self.frame[selected_column].eq(label), "USER_LOGIN_HASH"].nunique()
        )
        node_rows.append(
            {"ID": self.selected_node, "LABEL": label, "KIND": kind, "WEIGHT": selected_users}
        )
        edge_rows: list[dict[str, object]] = []
        for connected_label, shared_users in connection_weights.items():
            connected_label = str(connected_label)
            connected_id = f"{connected_kind}:{connected_label}"
            connected_users = int(
                self.frame.loc[
                    self.frame[connected_column].eq(connected_label), "USER_LOGIN_HASH"
                ].nunique()
            )
            node_rows.append(
                {
                    "ID": connected_id,
                    "LABEL": connected_label,
                    "KIND": connected_kind,
                    "WEIGHT": connected_users,
                }
            )
            source = self.selected_node if kind == "role" else connected_id
            target = connected_id if kind == "role" else self.selected_node
            edge_rows.append(
                {"SOURCE": source, "TARGET": target, "WEIGHT": int(shared_users)}
            )

        additional_nodes = pd.DataFrame(node_rows, columns=("ID", "LABEL", "KIND", "WEIGHT"))
        direct_edges = pd.DataFrame(edge_rows, columns=("SOURCE", "TARGET", "WEIGHT"))
        self.expanded_nodes = (
            pd.concat([self.nodes, additional_nodes], ignore_index=True)
            .drop_duplicates("ID", keep="last")
            .reset_index(drop=True)
        )
        self.expanded_edges = (
            pd.concat([self.edges, direct_edges], ignore_index=True)
            .sort_values(["WEIGHT", "SOURCE", "TARGET"], ascending=[False, True, True], kind="stable")
            .drop_duplicates(["SOURCE", "TARGET"], keep="first")
            .reset_index(drop=True)
        )
        baseline_ids = set(self.nodes.get("ID", pd.Series(dtype="string")).astype(str))
        self.expansion_added_nodes = int(
            (~self.expanded_nodes["ID"].astype(str).isin(baseline_ids)).sum()
        )

    def _selection_options_changed(self) -> None:
        if self.selected_node:
            self._build_selected_expansion()
            self._update_detail_for_selection()
        self.draw()

    def _display_data(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        nodes = self.nodes
        edges = self.edges
        if self.selected_node and self.expand_selected_var.get() and not self.expanded_nodes.empty:
            nodes = self.expanded_nodes
            edges = self.expanded_edges
        if not self.selected_node or not self.focus_mode_var.get():
            return nodes, edges
        neighbours = self._neighbours_for_edges(edges)
        active = {self.selected_node} | neighbours.get(self.selected_node, set())
        nodes = nodes[nodes["ID"].astype(str).isin(active)]
        edges = edges[
            edges["SOURCE"].astype(str).eq(self.selected_node)
            | edges["TARGET"].astype(str).eq(self.selected_node)
        ]
        return nodes, edges

    def _ordered_ids(self, nodes: pd.DataFrame, edges: pd.DataFrame) -> dict[str, list[str]]:
        role_nodes = nodes[nodes["KIND"].eq("role")].sort_values(
            ["WEIGHT", "LABEL"], ascending=[False, True], kind="stable"
        )
        privilege_nodes = nodes[nodes["KIND"].eq("privilege")].sort_values(
            ["WEIGHT", "LABEL"], ascending=[False, True], kind="stable"
        )
        roles = role_nodes["ID"].astype(str).tolist()
        privileges = privilege_nodes["ID"].astype(str).tolist()
        for _ in range(2):
            privilege_position = {node_id: index for index, node_id in enumerate(privileges)}
            role_score: dict[str, float] = {}
            for role in roles:
                connected = edges[edges["SOURCE"].astype(str).eq(role)]
                total = connected["WEIGHT"].sum()
                role_score[role] = (
                    sum(privilege_position.get(str(row.TARGET), 0) * int(row.WEIGHT) for row in connected.itertuples())
                    / total
                    if total
                    else float("inf")
                )
            roles.sort(key=lambda value: (role_score[value], value))
            role_position = {node_id: index for index, node_id in enumerate(roles)}
            privilege_score: dict[str, float] = {}
            for privilege in privileges:
                connected = edges[edges["TARGET"].astype(str).eq(privilege)]
                total = connected["WEIGHT"].sum()
                privilege_score[privilege] = (
                    sum(role_position.get(str(row.SOURCE), 0) * int(row.WEIGHT) for row in connected.itertuples())
                    / total
                    if total
                    else float("inf")
                )
            privileges.sort(key=lambda value: (privilege_score[value], value))
        return {"role": roles, "privilege": privileges}

    def _node_radius(self, weight: int, *, scale: float | None = None) -> float:
        display_scale = self.zoom_factor if scale is None else scale
        return display_scale * (5 + 7.5 * math.sqrt(max(0, weight) / self.max_node_weight))

    @staticmethod
    def _packed_vertical_positions(
        node_ids: list[str],
        radii: dict[str, float],
        *,
        top: float,
        minimum_center_gap: float,
        clear_gap: float,
    ) -> tuple[dict[str, float], float]:
        if not node_ids:
            return {}, top
        first = node_ids[0]
        current_y = top + radii[first]
        positions = {first: current_y}
        previous = first
        for node_id in node_ids[1:]:
            current_y += max(
                minimum_center_gap,
                radii[previous] + radii[node_id] + clear_gap,
            )
            positions[node_id] = current_y
            previous = node_id
        return positions, current_y + radii[previous]

    def draw(self) -> None:
        self.canvas.delete("all")
        self.node_items.clear()
        self.edge_items.clear()
        self.positions.clear()
        self.hover_item = None
        nodes, edges = self._display_data()
        viewport_width = max(700, self.canvas.winfo_width())
        viewport_height = max(300, self.canvas.winfo_height())
        if nodes.empty:
            self.canvas.configure(scrollregion=(0, 0, viewport_width, viewport_height))
            self.canvas.create_text(
                viewport_width / 2,
                viewport_height / 2,
                text=self.empty_message,
                width=max(300, viewport_width - 120),
                fill="#59636E",
                font=("Segoe UI", 11),
            )
            return

        ordered = self._ordered_ids(nodes, edges)
        content_width = max(viewport_width - 4, int(1280 * self.zoom_factor))
        radii = {
            str(row.ID): self._node_radius(int(row.WEIGHT))
            for row in nodes.itertuples(index=False)
        }
        vertical_positions: dict[str, dict[str, float]] = {}
        column_bottoms: list[float] = []
        for kind in ("role", "privilege"):
            y_positions, bottom = self._packed_vertical_positions(
                ordered[kind],
                radii,
                top=38,
                minimum_center_gap=max(16, 17 * self.zoom_factor),
                clear_gap=max(4, 5 * self.zoom_factor),
            )
            vertical_positions[kind] = y_positions
            column_bottoms.append(bottom)
        content_height = max(viewport_height - 4, max(column_bottoms, default=38) + 34)
        self.canvas.configure(scrollregion=(0, 0, content_width, content_height))
        columns = {"role": content_width * 0.34, "privilege": content_width * 0.67}
        heading_y = self.canvas.canvasy(viewport_height / 2)
        headings = {
            "role": (22, 90),
            "privilege": (content_width - 22, 270),
        }
        for kind, (heading_x, angle) in headings.items():
            self.canvas.create_text(
                heading_x,
                heading_y,
                text=KIND_LABELS[kind],
                angle=angle,
                fill="#38434F",
                font=("Segoe UI", max(20, int(26 * self.zoom_factor)), "bold"),
                tags=("__column_heading__",),
            )
        for kind, x in columns.items():
            for node_id in ordered[kind]:
                self.positions[node_id] = (x, vertical_positions[kind][node_id])

        display_neighbours = self._neighbours_for_edges(edges)
        active = (
            {self.selected_node} | display_neighbours.get(self.selected_node, set())
            if self.selected_node and not self.focus_mode_var.get()
            else None
        )
        for edge in edges.itertuples(index=False):
            source, target = str(edge.SOURCE), str(edge.TARGET)
            if source not in self.positions or target not in self.positions:
                continue
            highlighted = self.selected_node is None or self.selected_node in (source, target)
            colour = "#78909C" if highlighted else "#D7DDE1"
            line_width = max(1.0, self.zoom_factor * (1 + 4 * math.sqrt(int(edge.WEIGHT) / self.max_edge_weight)))
            item = self.canvas.create_line(
                *self.positions[source],
                *self.positions[target],
                fill=colour,
                width=line_width,
            )
            self.edge_items[item] = (source, target, int(edge.WEIGHT))

        node_font = ("Segoe UI", max(8, int(9 * self.zoom_factor)))
        for row in nodes.itertuples(index=False):
            node_id = str(row.ID)
            if node_id not in self.positions:
                continue
            x, y = self.positions[node_id]
            radius = radii[node_id]
            muted = active is not None and node_id not in active
            fill = "#CED5DA" if muted else KIND_COLOURS[str(row.KIND)]
            if node_id == self.selected_node:
                outline, outline_width = "#174A7E", 3
            elif node_id in self.key_nodes and not muted:
                outline, outline_width = "#7A5200", 3
            else:
                outline, outline_width = "#FFFFFF", 1
            if str(row.KIND) == "role":
                item = self.canvas.create_oval(
                    x - radius,
                    y - radius,
                    x + radius,
                    y + radius,
                    fill=fill,
                    outline=outline,
                    width=outline_width,
                )
            else:
                item = self.canvas.create_rectangle(
                    x - radius,
                    y - radius,
                    x + radius,
                    y + radius,
                    fill=fill,
                    outline=outline,
                    width=outline_width,
                )
            self.node_items[item] = node_id
            anchor = "e" if str(row.KIND) == "role" else "w"
            label_x = x - radius - 6 if anchor == "e" else x + radius + 6
            label = str(row.LABEL)
            short = label if len(label) <= 64 else label[:61] + "…"
            if node_id in self.key_nodes:
                short = "★ " + short
            text_item = self.canvas.create_text(
                label_x,
                y,
                text=short,
                anchor=anchor,
                fill="#7B858C" if muted else "#263238",
                font=node_font,
            )
            self.node_items[text_item] = node_id

    def _event_coordinates(self, event: tk.Event) -> tuple[float, float]:
        return self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

    def _on_click(self, event: tk.Event) -> None:
        x, y = self._event_coordinates(event)
        node_id = self._node_at(x, y, 4)
        if node_id is None or node_id == self.selected_node:
            self.clear_focus()
        else:
            self.focus_node(node_id)

    def _on_hover(self, event: tk.Event) -> None:
        x, y = self._event_coordinates(event)
        node_id = self._node_at(x, y, 3)
        if node_id is not None:
            marker = ("node", node_id)
            if marker == self.hover_item:
                return
            display_nodes, _ = self._display_data()
            match = display_nodes[display_nodes["ID"].astype(str).eq(node_id)]
            if match.empty:
                return
            row = match.iloc[0]
            kind = "Role" if row["KIND"] == "role" else "Privilege"
            key_text = "\nMost connected visible node" if node_id in self.key_nodes else ""
            self._show_tooltip(
                event,
                f"{kind}: {row['LABEL']}\nTotal SKU users: {int(row['WEIGHT']):,}{key_text}",
                marker,
            )
            return
        edge = self._edge_at(x, y, 4)
        if edge is not None:
            marker = ("edge", edge)
            if marker == self.hover_item:
                return
            source, target, weight = edge
            self._show_tooltip(
                event,
                f"{source.split(':', 1)[1]}\n↔ {target.split(':', 1)[1]}\nShared users: {weight:,}",
                marker,
            )
            return
        self._hide_tooltip()

    def _show_tooltip(self, event: tk.Event, message: str, marker: tuple[str, object]) -> None:
        self._hide_tooltip()
        x, y = self._event_coordinates(event)
        text_item = self.canvas.create_text(
            x + 14,
            y + 14,
            text=message,
            anchor="nw",
            width=380,
            fill="#FFFFFF",
            font=("Segoe UI", 9),
            tags=("__tooltip__",),
        )
        bounds = self.canvas.bbox(text_item)
        if bounds:
            rectangle = self.canvas.create_rectangle(
                bounds[0] - 7,
                bounds[1] - 5,
                bounds[2] + 7,
                bounds[3] + 5,
                fill="#263238",
                outline="#263238",
                tags=("__tooltip__",),
            )
            self.canvas.tag_lower(rectangle, text_item)
        self.hover_item = marker

    def _node_at(self, x: float, y: float, margin: int) -> str | None:
        items = self.canvas.find_overlapping(x - margin, y - margin, x + margin, y + margin)
        candidates = {self.node_items[item] for item in items if item in self.node_items}
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda node_id: (
                (self.positions.get(node_id, (x, y))[0] - x) ** 2
                + (self.positions.get(node_id, (x, y))[1] - y) ** 2
            ),
        )

    def _edge_at(self, x: float, y: float, margin: int) -> tuple[str, str, int] | None:
        items = self.canvas.find_overlapping(x - margin, y - margin, x + margin, y + margin)
        return next((self.edge_items[item] for item in reversed(items) if item in self.edge_items), None)

    def _hide_tooltip(self) -> None:
        self.canvas.delete("__tooltip__")
        self.hover_item = None

    def focus_node(self, node_id: str) -> None:
        display_nodes, _ = self._display_data()
        match = display_nodes[display_nodes["ID"].astype(str).eq(node_id)]
        if match.empty:
            return
        self.selected_node = node_id
        self._build_selected_expansion()
        self._set_detail_actions_enabled(True)
        self.detail_scope_var.set("visible")
        self._update_detail_for_selection()
        self.canvas.yview_moveto(0)
        self.draw()

    def clear_focus(self) -> None:
        self.selected_node = None
        self._clear_selected_expansion()
        self._set_detail_actions_enabled(False)
        self._fill_detail_tree(pd.DataFrame())
        filtered = self._filtered_assignments()
        self.selection_users_var.set(
            f"Users matching current filters: {filtered['USER_LOGIN_HASH'].nunique():,}"
            if not self.frame.empty
            else "Users matching current filters: —"
        )
        visible_roles = int(self.nodes["KIND"].eq("role").sum()) if not self.nodes.empty else 0
        visible_privileges = int(self.nodes["KIND"].eq("privilege").sum()) if not self.nodes.empty else 0
        self.detail_var.set(
            f"Showing {visible_roles:,} roles and {visible_privileges:,} privileges. "
            "Select a node to highlight its relationships."
        )
        self.visible_scope_button.configure(text="Visible relationships")
        self.all_scope_button.configure(text="All relationships")
        self.draw()

    def _connection_details(self, node_id: str, *, visible_only: bool) -> pd.DataFrame:
        if self.frame.empty:
            return pd.DataFrame(columns=("TYPE", "NAME", "USERS", "SHARED_USERS"))
        kind, label = node_id.split(":", 1)
        if kind == "role":
            selected = self.frame[self.frame["ROLE_CODE"].eq(label)]
            shared = selected.groupby("PRIVILEGE", as_index=False).agg(
                SHARED_USERS=("USER_LOGIN_HASH", "nunique")
            )
            totals = self.frame.groupby("PRIVILEGE", as_index=False).agg(
                USERS=("USER_LOGIN_HASH", "nunique")
            )
            details = shared.merge(totals, on="PRIVILEGE", how="left").rename(
                columns={"PRIVILEGE": "NAME"}
            )
            details.insert(0, "TYPE", "Privilege")
        else:
            selected = self.frame[self.frame["PRIVILEGE"].eq(label)]
            shared = selected.groupby("ROLE_CODE", as_index=False).agg(
                SHARED_USERS=("USER_LOGIN_HASH", "nunique")
            )
            totals = self.frame.groupby("ROLE_CODE", as_index=False).agg(
                USERS=("USER_LOGIN_HASH", "nunique")
            )
            details = shared.merge(totals, on="ROLE_CODE", how="left").rename(
                columns={"ROLE_CODE": "NAME"}
            )
            details.insert(0, "TYPE", "Role")
        if visible_only:
            _, visible_edges = self._display_data()
            visible_neighbours = self._neighbours_for_edges(visible_edges)
            visible_names = {
                value.split(":", 1)[1] for value in visible_neighbours.get(node_id, set())
            }
            details = details[details["NAME"].astype(str).isin(visible_names)]
        return details[["TYPE", "NAME", "USERS", "SHARED_USERS"]].sort_values(
            ["SHARED_USERS", "USERS", "NAME"], ascending=[False, False, True], kind="stable"
        ).reset_index(drop=True)

    def _update_detail_for_selection(self) -> None:
        if not self.selected_node:
            return
        display_nodes, _ = self._display_data()
        match = display_nodes[display_nodes["ID"].astype(str).eq(self.selected_node)]
        if match.empty:
            return
        row = match.iloc[0]
        kind = "Role" if row["KIND"] == "role" else "Privilege"
        visible_details = self._connection_details(self.selected_node, visible_only=True)
        all_details = self._connection_details(self.selected_node, visible_only=False)
        self.visible_scope_button.configure(text=f"Visible relationships ({len(visible_details):,})")
        self.all_scope_button.configure(text=f"All relationships ({len(all_details):,})")
        detail = f"{kind}: {row['LABEL']} — {int(row['WEIGHT']):,} total SKU users"
        if self.expand_selected_var.get():
            connected_kind = "privileges" if row["KIND"] == "role" else "roles"
            detail += f" — showing all {self.expansion_connection_count:,} connected {connected_kind}"
            if self.expansion_added_nodes:
                detail += f" ({self.expansion_added_nodes:,} added to the overview)"
        self.detail_var.set(detail)
        self.selection_users_var.set(f"Selected {kind.lower()} users: {int(row['WEIGHT']):,}")
        details = visible_details if self.detail_scope_var.get() == "visible" else all_details
        self._fill_detail_tree(details)

    def _fill_detail_tree(self, details: pd.DataFrame) -> None:
        self.detail_tree.delete(*self.detail_tree.get_children())
        self.current_details = details.copy()
        for row in details.itertuples(index=False):
            kind = "role" if row.TYPE == "Role" else "privilege"
            self.detail_tree.insert(
                "",
                "end",
                iid=f"{kind}:{row.NAME}",
                values=(row.TYPE, row.NAME, f"{int(row.USERS):,}", f"{int(row.SHARED_USERS):,}"),
            )

    def _sort_details(self, column: str) -> None:
        if self.current_details.empty:
            return
        state = getattr(self, "_detail_sort", ("SHARED_USERS", False))
        descending = not state[1] if state[0] == column else column in {"USERS", "SHARED_USERS"}
        self._detail_sort = (column, descending)
        self.current_details = self.current_details.sort_values(
            [column, "NAME"] if column != "NAME" else ["NAME"],
            ascending=[not descending, True] if column != "NAME" else [not descending],
            kind="stable",
        )
        self._fill_detail_tree(self.current_details)

    def _focus_detail_row(self, _event: tk.Event) -> None:
        selection = self.detail_tree.selection()
        if not selection:
            return
        node_id = str(selection[0])
        display_nodes, _ = self._display_data()
        display_ids = set(display_nodes.get("ID", pd.Series(dtype="string")).astype(str))
        if node_id not in display_ids:
            kind, label = node_id.split(":", 1)
            if kind == "role":
                self.role_search_var.set(label)
            else:
                self.privilege_search_var.set(label)
            if self.search_job is not None:
                self.after_cancel(self.search_job)
                self.search_job = None
            self.refresh()
            display_nodes, _ = self._display_data()
            display_ids = set(display_nodes.get("ID", pd.Series(dtype="string")).astype(str))
        if node_id in display_ids:
            self.focus_node(node_id)

    def _copy_detail_rows(self, _event: tk.Event) -> str:
        rows = [self.detail_tree.item(item, "values") for item in self.detail_tree.selection()]
        if rows:
            text = "\n".join("\t".join(map(str, row)) for row in rows)
            self.clipboard_clear()
            self.clipboard_append(text)
        return "break"

    def _on_mousewheel(self, event: tk.Event) -> str:
        if event.state & 0x0004:
            self._zoom_by(1.1 if event.delta > 0 else 1 / 1.1)
        elif event.state & 0x0001:
            self.canvas.xview_scroll(int(-event.delta / 120), "units")
        else:
            self.canvas.yview_scroll(int(-event.delta / 120), "units")
            self._reposition_column_headings()
        return "break"

    def _scroll_canvas_y(self, *args: str) -> None:
        self.canvas.yview(*args)
        self._reposition_column_headings()

    def _scan_drag_canvas(self, event: tk.Event) -> None:
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        self._reposition_column_headings()

    def _reposition_column_headings(self) -> None:
        center_y = self.canvas.canvasy(self.canvas.winfo_height() / 2)
        for item in self.canvas.find_withtag("__column_heading__"):
            coordinates = self.canvas.coords(item)
            if len(coordinates) >= 2:
                self.canvas.coords(item, coordinates[0], center_y)
                self.canvas.tag_raise(item)

    def _zoom_by(self, factor: float) -> None:
        self.zoom_factor = min(1.8, max(0.65, self.zoom_factor * factor))
        self.draw()

    def fit_width(self) -> None:
        viewport = max(700, self.canvas.winfo_width())
        self.zoom_factor = min(1.0, max(0.65, viewport / 1280))
        self.canvas.xview_moveto(0)
        self.draw()

    def export_png(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="Export network image",
            defaultextension=".png",
            initialfile=f"{self._sku_name()}_network.png",
            filetypes=(("PNG image", "*.png"),),
        )
        if not filename:
            return
        try:
            self._render_png(Path(filename))
            self._show_export_complete(Path(filename))
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def _render_png(self, filename: Path) -> None:
        from PIL import Image, ImageDraw, ImageFont

        nodes, edges = self._display_data()
        ordered = self._ordered_ids(nodes, edges)
        width = 2200
        graph_top = 220
        radii = {
            str(row.ID): self._node_radius(int(row.WEIGHT), scale=1.36)
            for row in nodes.itertuples(index=False)
        }
        packed_positions: dict[str, dict[str, float]] = {}
        packed_bottoms: list[float] = []
        for kind in ("role", "privilege"):
            y_positions, bottom = self._packed_vertical_positions(
                ordered[kind],
                radii,
                top=graph_top,
                minimum_center_gap=28,
                clear_gap=7,
            )
            packed_positions[kind] = y_positions
            packed_bottoms.append(bottom)
        height = max(760, int(max(packed_bottoms, default=graph_top) + 80))
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)

        def font(size: int, *, bold: bool = False):
            name = "segoeuib.ttf" if bold else "segoeui.ttf"
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                return ImageFont.load_default()

        draw.text(
            (50, 35),
            "Oracle Fusion SaaS Roles and Privileges network",
            fill="#1F4E78",
            font=font(30, bold=True),
        )
        draw.text((50, 82), f"SKU: {self._sku_name()}  |  Service: {self._service_name()}", fill="#263238", font=font(18, bold=True))
        filters = (
            f"Role search: {self.role_search_var.get().strip() or 'None'}  |  "
            f"Privilege search: {self.privilege_search_var.get().strip() or 'None'}  |  "
            f"Maximum roles: {self.roles_var.get()}  |  Maximum privileges: {self.privileges_var.get()}  |  "
            f"Maximum relationships: {self.relationships_var.get()}  |  "
            f"Minimum shared users: {self.min_shared_var.get()}"
        )
        draw.text((50, 118), filters, fill="#455A64", font=font(15))
        draw.text(
            (50, 148),
            f"{self.network_summary_var.get()}  |  Exported {datetime.now():%d %b %Y %H:%M}",
            fill="#455A64",
            font=font(15),
        )
        draw.ellipse((50, 182, 66, 198), fill=KIND_COLOURS["role"])
        draw.text((74, 179), "Roles", fill="#263238", font=font(14))
        draw.rectangle((150, 182, 166, 198), fill=KIND_COLOURS["privilege"])
        draw.text((174, 179), "Privileges", fill="#263238", font=font(14))
        draw.text((320, 179), "★ Most connected visible nodes", fill="#263238", font=font(14))
        draw.text((650, 179), "Node size = total SKU users; line width = shared SKU users", fill="#263238", font=font(14))

        positions: dict[str, tuple[float, float]] = {}
        columns = {"role": width * 0.34, "privilege": width * 0.66}
        heading_font = font(40, bold=True)

        def draw_vertical_heading(text: str, x: int, angle: int) -> None:
            bounds = draw.textbbox((0, 0), text, font=heading_font)
            text_width = bounds[2] - bounds[0]
            text_height = bounds[3] - bounds[1]
            label = Image.new("RGBA", (text_width + 16, text_height + 16), (255, 255, 255, 0))
            label_draw = ImageDraw.Draw(label)
            label_draw.text((8 - bounds[0], 8 - bounds[1]), text, fill="#263238", font=heading_font)
            rotated = label.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
            center_y = (graph_top + height) // 2
            image.paste(
                rotated,
                (int(x - rotated.width / 2), int(center_y - rotated.height / 2)),
                rotated,
            )

        draw_vertical_heading(KIND_LABELS["role"], 35, 90)
        draw_vertical_heading(KIND_LABELS["privilege"], width - 35, 270)
        for kind in ("role", "privilege"):
            x = columns[kind]
            for node_id in ordered[kind]:
                positions[node_id] = (x, packed_positions[kind][node_id])
        for edge in edges.itertuples(index=False):
            source, target = str(edge.SOURCE), str(edge.TARGET)
            if source not in positions or target not in positions:
                continue
            line_width = max(1, int(1 + 6 * math.sqrt(int(edge.WEIGHT) / self.max_edge_weight)))
            draw.line((*positions[source], *positions[target]), fill="#78909C", width=line_width)
        for row in nodes.itertuples(index=False):
            node_id = str(row.ID)
            if node_id not in positions:
                continue
            x, y = positions[node_id]
            radius = radii[node_id]
            box = (x - radius, y - radius, x + radius, y + radius)
            if row.KIND == "role":
                draw.ellipse(box, fill=KIND_COLOURS["role"], outline="#174A7E" if node_id == self.selected_node else "white", width=3)
                label = ("★ " if node_id in self.key_nodes else "") + str(row.LABEL)
                bounds = draw.textbbox((0, 0), label, font=font(14))
                draw.text((x - radius - 10 - (bounds[2] - bounds[0]), y - 9), label, fill="#263238", font=font(14))
            else:
                draw.rectangle(box, fill=KIND_COLOURS["privilege"], outline="#174A7E" if node_id == self.selected_node else "white", width=3)
                label = ("★ " if node_id in self.key_nodes else "") + str(row.LABEL)
                draw.text((x + radius + 10, y - 9), label, fill="#263238", font=font(14))
        image.save(filename, "PNG", optimize=True)

    def export_excel(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="Export network overview",
            defaultextension=".xlsx",
            initialfile=f"{self._sku_name()}_network.xlsx",
            filetypes=(("Excel workbook", "*.xlsx"),),
        )
        if not filename:
            return
        try:
            values = self._filter_values()
            if values is None:
                raise ValueError(self.filter_error_var.get())
            max_roles, max_privileges, max_relationships, minimum = values
            display_nodes, display_edges = self._display_data()
            summary = pd.DataFrame(
                [
                    ("Source workbook", self.source_path.name),
                    ("Prepared for", self.workbook_info.get("prepared_for", "")),
                    ("Usage data collected", self.workbook_info.get("usage_data_collected", "")),
                    ("DT data collected", self.workbook_info.get("dt_data_collected", "")),
                    ("Exported at", datetime.now()),
                    ("SKU", self._sku_name()),
                    ("Service", self._service_name()),
                    ("Total SKU users", self.frame["USER_LOGIN_HASH"].nunique()),
                    ("Total SKU roles", self.frame["ROLE_CODE"].nunique()),
                    ("Total SKU privileges", self.frame["PRIVILEGE"].nunique()),
                    ("Role search", self.role_search_var.get().strip()),
                    ("Privilege search", self.privilege_search_var.get().strip()),
                    ("Maximum roles", max_roles),
                    ("Maximum privileges", max_privileges),
                    ("Maximum relationships", max_relationships),
                    ("Minimum shared users", minimum),
                    ("Selected node", self.selected_node or ""),
                    ("Show only selected node's connections", bool(self.focus_mode_var.get())),
                    ("Show all connections for selected node", bool(self.expand_selected_var.get())),
                    ("Exported nodes", len(display_nodes)),
                    ("Exported relationships", len(display_edges)),
                ],
                columns=("Metric", "Value"),
            )
            nodes = display_nodes.copy()
            if not nodes.empty:
                display_neighbours = self._neighbours_for_edges(display_edges)
                nodes["CONNECTIONS"] = nodes["ID"].map(
                    lambda value: len(display_neighbours.get(str(value), set()))
                )
                nodes["MOST_CONNECTED_VISIBLE"] = nodes["ID"].astype(str).isin(self.key_nodes)
                nodes = nodes.rename(
                    columns={
                        "ID": "Node ID",
                        "LABEL": "Name",
                        "KIND": "Type",
                        "WEIGHT": "Total SKU users",
                        "CONNECTIONS": "Visible relationships",
                        "MOST_CONNECTED_VISIBLE": "Most connected visible node",
                    }
                )
            connections = display_edges.rename(
                columns={"SOURCE": "Role node ID", "TARGET": "Privilege node ID", "WEIGHT": "Shared users"}
            )
            visible_details = (
                self._connection_details(self.selected_node, visible_only=True)
                if self.selected_node
                else pd.DataFrame()
            )
            all_details = (
                self._connection_details(self.selected_node, visible_only=False)
                if self.selected_node
                else pd.DataFrame()
            )
            with pd.ExcelWriter(filename, engine="openpyxl") as writer:
                summary.to_excel(writer, sheet_name="Summary", index=False)
                nodes.to_excel(writer, sheet_name="Visible Nodes", index=False)
                connections.to_excel(writer, sheet_name="Visible Relationships", index=False)
                if not visible_details.empty:
                    visible_details.to_excel(writer, sheet_name="Selected Visible", index=False)
                if not all_details.empty:
                    all_details.to_excel(writer, sheet_name="Selected All", index=False)
            self._show_export_complete(Path(filename))
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def _show_export_complete(self, filename: Path) -> None:
        open_folder = messagebox.askyesno(
            "Export complete",
            f"Saved to:\n{filename}\n\nOpen the containing folder?",
        )
        if open_folder:
            os.startfile(filename.parent)

    def _sku_name(self) -> str:
        return str(self.frame["SKU"].iloc[0]) if not self.frame.empty and "SKU" in self.frame else "SKU"

    def _service_name(self) -> str:
        return str(self.frame["SERVICE"].iloc[0]) if not self.frame.empty and "SERVICE" in self.frame else ""
