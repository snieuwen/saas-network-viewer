from __future__ import annotations

import threading
import tkinter as tk
import queue
import sys
import os
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pandas as pd


if getattr(sys, "frozen", False):
    _BUNDLED_TCL = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "tcl"
    os.environ.setdefault("TCL_LIBRARY", str(_BUNDLED_TCL / "tcl8.6"))
    os.environ.setdefault("TK_LIBRARY", str(_BUNDLED_TCL / "tk8.6"))

from access_analysis import load_raw_data, load_workbook_info, sku_catalog
from network_view import NetworkView
from scenario_analysis import (
    Scenario,
    ScenarioLibrary,
    ScenarioPicker,
    ScenarioReport,
    ScenarioRolePicker,
    scenario_impact,
)
from user_analysis import UserExplorer


APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
APP_VERSION = "1.1"


class OracleFusionSaaSNetworkViewerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"Oracle Fusion SaaS Roles and Privileges network — v{APP_VERSION}")
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        width = min(1420, max(900, screen_width - 80))
        height = min(900, max(620, screen_height - 100))
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 3)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(min(960, width), min(620, height))

        self.data = pd.DataFrame()
        self.catalog = pd.DataFrame()
        self.all_labels: list[str] = []
        self.loading_token = 0
        self.load_results: queue.Queue[tuple[object, ...]] = queue.Queue()
        self.source_var = tk.StringVar()
        self.source_name_var = tk.StringVar()
        self.sku_var = tk.StringVar()
        self.selected_sku_label = ""
        self.service_var = tk.StringVar()
        self.user_count_var = tk.StringVar(value="—")
        self.filtered_user_count_var = tk.StringVar(value="—")
        self.prepared_for_var = tk.StringVar()
        self.dates_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Choose a workbook to begin")
        self.active_sku = ""
        self.active_service = ""
        self.scenario_library = ScenarioLibrary()
        try:
            self.scenario_library.load_saved()
        except (OSError, ValueError, TypeError):
            # A damaged local scenario file must never prevent opening a workbook.
            self.scenario_library = ScenarioLibrary()

        self._configure_style()
        self._build_ui()

    def _configure_style(self) -> None:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 17, "bold"), foreground="#1F4E78")
        style.configure("InfoLabel.TLabel", font=("Segoe UI", 9, "bold"), foreground="#59636E")
        style.configure("InfoValue.TLabel", font=("Segoe UI", 11, "bold"), foreground="#263238")
        style.configure("UserValue.TLabel", font=("Segoe UI", 18, "bold"), foreground="#375623")
        style.configure("Error.TLabel", foreground="#A61B1B")

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=(10, 7))
        outer.pack(fill="both", expand=True)

        title_row = ttk.Frame(outer)
        title_row.pack(fill="x")
        ttk.Label(
            title_row,
            text="Oracle Fusion SaaS Roles and Privileges network",
            style="Title.TLabel",
        ).pack(side="left")
        self.progress = ttk.Progressbar(title_row, mode="indeterminate", length=150)
        self.source_button = ttk.Button(title_row, text="Open workbook", command=self.browse_source)
        self.source_button.pack(side="right")
        self.scenario_report_button = ttk.Button(
            title_row, text="Scenario report…", command=self.open_scenario_report, state="disabled"
        )
        self.scenario_report_button.pack(side="right", padx=(0, 8))
        self.user_explorer_button = ttk.Button(
            title_row, text="User explorer…", command=self.open_user_explorer, state="disabled"
        )
        self.user_explorer_button.pack(side="right", padx=(0, 8))

        source_row = ttk.Frame(outer)
        source_row.pack(fill="x", pady=(2, 0))
        ttk.Label(source_row, text="Workbook", style="InfoLabel.TLabel").pack(side="left")
        ttk.Label(source_row, textvariable=self.source_name_var, style="InfoValue.TLabel").pack(
            side="left", padx=(8, 0)
        )
        ttk.Label(source_row, textvariable=self.prepared_for_var).pack(side="left", padx=(16, 0))
        ttk.Label(source_row, textvariable=self.dates_var).pack(side="right")

        selector = ttk.LabelFrame(outer, text="SKU selection", padding=(7, 3))
        selector.pack(fill="x", pady=(3, 3))
        selector.columnconfigure(0, weight=3)
        selector.columnconfigure(1, weight=5)
        ttk.Label(selector, text="Type any part of the SKU code or service name", style="InfoLabel.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.sku_combo = ttk.Combobox(selector, textvariable=self.sku_var, state="normal")
        self.sku_combo.grid(row=1, column=0, sticky="ew", padx=(0, 14))
        self.sku_combo.bind("<<ComboboxSelected>>", lambda _event: self.select_sku())
        self.sku_combo.bind("<Return>", lambda _event: self.select_sku())
        self.sku_combo.bind("<KeyRelease>", self.filter_skus)
        self.sku_combo.bind("<FocusOut>", lambda _event: self._restore_selected_sku())
        self.sku_combo.bind("<Escape>", lambda _event: self._restore_selected_sku())

        ttk.Label(selector, text="Service", style="InfoLabel.TLabel").grid(row=0, column=1, sticky="w")
        self.service_label = ttk.Label(selector, textvariable=self.service_var, style="InfoValue.TLabel")
        self.service_label.grid(row=1, column=1, sticky="w", padx=(0, 16))
        selector.bind(
            "<Configure>",
            lambda event: self.service_label.configure(wraplength=max(260, int(event.width * 0.42))),
        )

        ttk.Label(selector, text="Total SKU users", style="InfoLabel.TLabel").grid(
            row=0, column=2, sticky="e"
        )
        ttk.Label(selector, textvariable=self.user_count_var, style="UserValue.TLabel").grid(
            row=1, column=2, sticky="e", padx=(0, 16)
        )
        ttk.Label(selector, text="Filtered SKU users", style="InfoLabel.TLabel").grid(
            row=0, column=3, sticky="e"
        )
        ttk.Label(
            selector,
            textvariable=self.filtered_user_count_var,
            style="UserValue.TLabel",
        ).grid(row=1, column=3, sticky="e")

        self.network_view = NetworkView(
            outer,
            on_add_to_scenario=self.add_nodes_to_scenario,
            on_add_privilege_roles_to_scenario=self.add_privilege_roles_to_scenario,
            on_filtered_user_count=self._set_filtered_user_count,
        )
        self.network_view.pack(fill="both", expand=True)
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="e", pady=(2, 0))

    def _set_filtered_user_count(self, count: int | None) -> None:
        self.filtered_user_count_var.set("—" if count is None else f"{count:,}")

    def browse_source(self) -> None:
        current_value = self.source_var.get().strip()
        current = Path(current_value) if current_value else None
        filename = filedialog.askopenfilename(
            title="Select source workbook",
            initialdir=str(current.parent if current and current.parent.exists() else APP_DIR),
            filetypes=(("Excel workbooks", "*.xlsx *.xlsm"), ("All files", "*.*")),
        )
        if filename:
            self.load_source(Path(filename))

    def load_source(self, candidate: str | Path | None = None) -> None:
        source = Path(candidate) if candidate is not None else Path(self.source_var.get())
        if not source.exists():
            self.status_var.set("Source workbook not found")
            messagebox.showerror(
                "Source workbook not found",
                f"The source workbook was not found:\n{source}\n\nChoose a workbook to continue.",
            )
            return
        self.loading_token += 1
        token = self.loading_token
        self._set_loading(True, f"Loading {source.name}…")
        thread = threading.Thread(
            target=self._load_source_worker,
            args=(token, source),
            daemon=True,
        )
        thread.start()
        self.root.after(50, lambda: self._poll_load_result(token))

    def _load_source_worker(self, token: int, source: Path) -> None:
        try:
            data = load_raw_data(source)
            workbook_info = load_workbook_info(source)
            catalog = sku_catalog(data)
            if catalog.empty:
                raise ValueError("The workbook does not contain any selectable SKUs.")
            error: Exception | None = None
        except Exception as exc:
            data = pd.DataFrame()
            workbook_info = {}
            catalog = pd.DataFrame()
            error = exc
        self.load_results.put((token, source, data, workbook_info, catalog, error))

    def _poll_load_result(self, token: int) -> None:
        try:
            result = self.load_results.get_nowait()
        except queue.Empty:
            if token == self.loading_token:
                self.root.after(50, lambda: self._poll_load_result(token))
            return
        self._finish_loading(*result)

    def _finish_loading(
        self,
        token: int,
        source: Path,
        data: pd.DataFrame,
        workbook_info: dict[str, object],
        catalog: pd.DataFrame,
        error: Exception | None,
    ) -> None:
        if token != self.loading_token:
            return
        self._set_loading(False)
        if error is not None:
            self.status_var.set(f"Could not load {source.name}; the previous network is unchanged")
            messagebox.showerror(
                "Could not load workbook",
                f"{error}\n\nThe previously loaded workbook and network remain active.",
            )
            return

        previous_label = self.selected_sku_label
        self.data = data
        self.catalog = catalog
        self.all_labels = self.catalog["LABEL"].tolist()
        self.sku_combo["values"] = self.all_labels
        self.source_var.set(str(source))
        self.source_name_var.set(source.name)
        self.network_view.set_workbook_info(workbook_info, source)
        prepared_for = str(workbook_info.get("prepared_for", "")).strip() or "—"
        self.prepared_for_var.set(f"Prepared for: {prepared_for}")
        usage_date = self._format_date(workbook_info.get("usage_data_collected"))
        dt_date = self._format_date(workbook_info.get("dt_data_collected"))
        self.dates_var.set(
            f"Usage data collected: {usage_date}    |    DT data collected: {dt_date}"
        )
        default = previous_label if previous_label in self.all_labels else next(
            (label for label in self.all_labels if label.startswith("B108674 |")),
            self.all_labels[0],
        )
        self.sku_var.set(default)
        self.select_sku()
        self.status_var.set(f"Loaded {source.name}: {len(self.data):,} unique assignment rows")

    def _set_loading(self, loading: bool, status: str = "") -> None:
        state = "disabled" if loading else "normal"
        self.source_button.configure(state=state)
        self.sku_combo.configure(state="disabled" if loading else "normal")
        self.root.configure(cursor="wait" if loading else "")
        if loading:
            if not self.progress.winfo_manager():
                self.progress.pack(side="right", padx=(8, 0), before=self.source_button)
            self.progress.start(12)
            self.status_var.set(status)
        else:
            self.progress.stop()
            self.progress.configure(value=0)
            self.progress.pack_forget()

    @staticmethod
    def _format_date(value: object) -> str:
        if value is None or pd.isna(value):
            return "—"
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return str(value)
        return parsed.strftime("%d %b %Y")

    def filter_skus(self, event: tk.Event) -> None:
        if event.keysym in {"Return", "Up", "Down", "Escape", "Tab", "Shift_L", "Shift_R"}:
            return
        query = self.sku_var.get().strip().casefold()
        matches = self.all_labels if not query else [
            label for label in self.all_labels if query in label.casefold()
        ]
        self.sku_combo["values"] = matches
        if not query:
            self.status_var.set("Select a SKU")
        elif not matches:
            self.status_var.set(f"No SKU or service contains “{self.sku_var.get().strip()}”")
        else:
            self.status_var.set(f"{len(matches):,} matching SKU{'s' if len(matches) != 1 else ''}; press Enter to select the first match")

    def _restore_selected_sku(self) -> None:
        if self.selected_sku_label in self.all_labels:
            self.sku_var.set(self.selected_sku_label)
            self.sku_combo["values"] = self.all_labels

    def select_sku(self) -> None:
        if self.catalog.empty:
            return
        entered = self.sku_var.get().strip()
        if not entered:
            self._restore_selected_sku()
            return
        if entered not in self.all_labels:
            folded = entered.casefold()
            match = next((label for label in self.all_labels if folded in label.casefold()), None)
            if match is None:
                self.status_var.set(f"No SKU or service contains “{entered}”")
                self._restore_selected_sku()
                return
            self.sku_var.set(match)

        selected = self.catalog[self.catalog["LABEL"].eq(self.sku_var.get())]
        if selected.empty:
            return
        sku = str(selected["SKU"].iloc[0])
        service = str(selected["SERVICE"].iloc[0])
        user_count = int(selected["USERS"].iloc[0])
        self.selected_sku_label = self.sku_var.get()
        self.sku_combo["values"] = self.all_labels
        self.service_var.set(service)
        self.user_count_var.set(f"{user_count:,}")
        self.active_sku = sku
        self.active_service = service
        selected_data = self.data[self.data["SKU"].eq(sku) & self.data["SERVICE"].eq(service)]
        self.network_view.set_data(selected_data)
        self.scenario_report_button.configure(state="normal")
        self.user_explorer_button.configure(state="normal")
        self.status_var.set(f"Network for {sku}")

    def add_nodes_to_scenario(
        self, node_ids: list[str], frame: pd.DataFrame, x_root: int, y_root: int
    ) -> None:
        """Create or extend a named scenario from the graph context menu."""
        scenario = self._choose_scenario(x_root, y_root)
        if scenario is None:
            return
        scenario.add_nodes(node_ids)
        self._save_scenario(scenario)
        impact = scenario_impact(frame, scenario)
        roles = sum(node.startswith("role:") for node in node_ids)
        privileges = len(node_ids) - roles
        self._show_scenario_updated(scenario, impact)
        self.status_var.set(f"Added {roles} role(s) and {privileges} privilege(s) to scenario “{scenario.name}”")

    def add_privilege_roles_to_scenario(
        self, privilege: str, frame: pd.DataFrame, x_root: int, y_root: int
    ) -> None:
        """Exclude one privilege only from selected roles in a named scenario."""
        matching = frame[frame["PRIVILEGE"].astype(str).eq(privilege)]
        roles = [
            (str(role), int(group["USER_LOGIN_HASH"].nunique()))
            for role, group in matching.groupby("ROLE_CODE")
        ]
        roles.sort(key=lambda item: (-item[1], item[0]))
        if not roles:
            messagebox.showinfo(
                "No matching roles",
                f"No roles containing {privilege} were found in the current SKU.",
                parent=self.root,
            )
            return
        role_picker = ScenarioRolePicker(
            self.root,
            privilege,
            roles,
            x_root=x_root,
            y_root=y_root,
        )
        self.root.wait_window(role_picker)
        if not role_picker.result:
            return
        scenario = self._choose_scenario(x_root, y_root)
        if scenario is None:
            return
        scenario.add_privilege_roles(privilege, role_picker.result)
        self._save_scenario(scenario)
        impact = scenario_impact(frame, scenario)
        self._show_scenario_updated(scenario, impact)
        self.status_var.set(
            f"Excluded {privilege} from {len(role_picker.result):,} role(s) in scenario “{scenario.name}”"
        )

    def _choose_scenario(self, x_root: int, y_root: int) -> Scenario | None:
        existing = self.scenario_library.for_sku(self.active_sku, self.active_service)
        picker = ScenarioPicker(self.root, existing, x_root=x_root, y_root=y_root)
        self.root.wait_window(picker)
        name = picker.result
        if not name:
            return None
        scenario = next((item for item in existing if item.name.casefold() == name.casefold()), None)
        if scenario is None:
            name_in_use = next(
                (item for item in self.scenario_library.scenarios if item.name.casefold() == name.casefold()),
                None,
            )
            if name_in_use is not None:
                messagebox.showwarning(
                    "Scenario name already used",
                    "Scenario names must be unique because each scenario is saved as a file with its name. "
                    f"“{name}” already belongs to {name_in_use.sku} | {name_in_use.service}.",
                    parent=self.root,
                )
                return None
            scenario = Scenario(name=name, sku=self.active_sku, service=self.active_service)
            self.scenario_library.scenarios.append(scenario)
        return scenario

    def _save_scenario(self, scenario: Scenario) -> None:
        try:
            self.scenario_library.save_scenario(scenario)
        except OSError as exc:
            messagebox.showwarning(
                "Scenario not saved",
                f"The scenario was updated in this session but could not be saved automatically:\n{exc}",
                parent=self.root,
            )

    def _show_scenario_updated(self, scenario: Scenario, impact: dict[str, int]) -> None:
        messagebox.showinfo(
            "Scenario updated",
            f"{scenario.name} now excludes {len(scenario.excluded_roles):,} role(s) and "
            f"{len(scenario.excluded_privileges):,} privilege(s) globally, plus "
            f"{len(scenario.excluded_privilege_roles):,} privilege-role relationship(s).\n\n"
            f"Current access-based impact:\n"
            f"• {impact['in_scope']:,} users remain in scope\n"
            f"• {impact['removed']:,} users are removed from scope\n"
            f"• {impact['affected']:,} users have an excluded assignment\n\n"
            "Open Scenario report… to compare it with the unrestricted baseline or another scenario.",
            parent=self.root,
        )

    def open_scenario_report(self) -> None:
        if not self.active_sku:
            return
        frame = self.data[
            self.data["SKU"].eq(self.active_sku) & self.data["SERVICE"].eq(self.active_service)
        ]
        ScenarioReport(self.root, self.scenario_library, frame, self.active_sku, self.active_service)

    def open_user_explorer(self) -> None:
        if not self.active_sku:
            return
        frame = self.data[
            self.data["SKU"].eq(self.active_sku) & self.data["SERVICE"].eq(self.active_service)
        ]
        UserExplorer(
            self.root,
            frame,
            self.scenario_library.for_sku(self.active_sku, self.active_service),
            on_focus_user=self.network_view.focus_user,
        )

def main() -> None:
    root = tk.Tk()
    OracleFusionSaaSNetworkViewerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
