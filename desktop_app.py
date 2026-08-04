from __future__ import annotations

import threading
import tkinter as tk
import queue
import sys
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pandas as pd

from access_analysis import load_raw_data, load_workbook_info, sku_catalog
from network_view import NetworkView


APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
NAMED_DEFAULT_SOURCE = APP_DIR.parent / "Rotterdam Raw Data 20260703.xlsx"


def find_default_source() -> Path:
    if NAMED_DEFAULT_SOURCE.exists():
        return NAMED_DEFAULT_SOURCE
    candidates = sorted(
        APP_DIR.parent.glob("*Raw Data*.xlsx"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else NAMED_DEFAULT_SOURCE


class SkuNetworkApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("SKU Roles and Privileges Network")
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
        self.details_visible = False
        self.source_var = tk.StringVar(value=str(find_default_source()))
        self.source_name_var = tk.StringVar(value=find_default_source().name)
        self.sku_var = tk.StringVar()
        self.service_var = tk.StringVar(value="No SKU selected")
        self.user_count_var = tk.StringVar(value="—")
        self.prepared_for_var = tk.StringVar(value="Prepared for: —")
        self.dates_var = tk.StringVar(value="Usage data collected: —    |    DT data collected: —")
        self.status_var = tk.StringVar(value="Loading data…")
        self.workbook_toggle_var = tk.StringVar(value="Workbook details ▸")

        self._configure_style()
        self._build_ui()
        self.root.after(100, self.load_source)

    def _configure_style(self) -> None:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 19, "bold"), foreground="#1F4E78")
        style.configure("InfoLabel.TLabel", font=("Segoe UI", 9, "bold"), foreground="#59636E")
        style.configure("InfoValue.TLabel", font=("Segoe UI", 11, "bold"), foreground="#263238")
        style.configure("UserValue.TLabel", font=("Segoe UI", 18, "bold"), foreground="#375623")
        style.configure("Error.TLabel", foreground="#A61B1B")

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        title_row = ttk.Frame(outer)
        title_row.pack(fill="x")
        ttk.Label(title_row, text="Roles and Privileges Network", style="Title.TLabel").pack(side="left")
        self.progress = ttk.Progressbar(title_row, mode="indeterminate", length=150)
        self.source_button = ttk.Button(title_row, text="Change workbook…", command=self.browse_source)
        self.source_button.pack(side="right")

        source_row = ttk.Frame(outer)
        source_row.pack(fill="x", pady=(4, 0))
        ttk.Button(
            source_row,
            textvariable=self.workbook_toggle_var,
            command=self.toggle_workbook_details,
        ).pack(side="left")
        ttk.Label(source_row, textvariable=self.source_name_var).pack(side="left", padx=(8, 0))

        self.workbook_details = ttk.Frame(outer, padding=(8, 5))
        self.workbook_details.columnconfigure(0, weight=1)
        ttk.Label(self.workbook_details, text="Source workbook", style="InfoLabel.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(self.workbook_details, textvariable=self.source_var, state="readonly").grid(
            row=1, column=0, sticky="ew"
        )
        metadata = ttk.Frame(self.workbook_details)
        metadata.grid(row=2, column=0, sticky="ew", pady=(5, 0))
        ttk.Label(metadata, textvariable=self.prepared_for_var, style="InfoValue.TLabel").pack(side="left")
        ttk.Label(metadata, textvariable=self.dates_var).pack(side="right")

        selector = ttk.LabelFrame(outer, text="SKU selection", padding=(8, 6))
        selector.pack(fill="x", pady=(6, 6))
        selector.columnconfigure(0, weight=3)
        selector.columnconfigure(2, weight=5)
        ttk.Label(selector, text="Type any part of the SKU code or service name", style="InfoLabel.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        self.sku_combo = ttk.Combobox(selector, textvariable=self.sku_var, state="normal")
        self.sku_combo.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        self.sku_combo.bind("<<ComboboxSelected>>", lambda _event: self.select_sku())
        self.sku_combo.bind("<Return>", lambda _event: self.select_sku())
        self.sku_combo.bind("<KeyRelease>", self.filter_skus)
        self.sku_combo.bind("<FocusOut>", lambda _event: self.clear_sku() if not self.sku_var.get().strip() else None)
        self.clear_sku_button = ttk.Button(selector, text="Clear SKU", command=self.clear_sku)
        self.clear_sku_button.grid(row=1, column=1, sticky="w", padx=(0, 14))

        ttk.Label(selector, text="Service", style="InfoLabel.TLabel").grid(row=0, column=2, sticky="w")
        self.service_label = ttk.Label(selector, textvariable=self.service_var, style="InfoValue.TLabel")
        self.service_label.grid(row=1, column=2, sticky="w", padx=(0, 16))
        selector.bind(
            "<Configure>",
            lambda event: self.service_label.configure(wraplength=max(260, int(event.width * 0.42))),
        )

        ttk.Label(selector, text="Total SKU users", style="InfoLabel.TLabel").grid(
            row=0, column=3, sticky="e"
        )
        ttk.Label(selector, textvariable=self.user_count_var, style="UserValue.TLabel").grid(
            row=1, column=3, sticky="e"
        )

        self.network_view = NetworkView(outer)
        self.network_view.pack(fill="both", expand=True)
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="e", pady=(4, 0))

    def toggle_workbook_details(self) -> None:
        if self.details_visible:
            self.workbook_details.pack_forget()
            self.workbook_toggle_var.set("Workbook details ▸")
        else:
            self.workbook_details.pack(fill="x", pady=(2, 3), before=self.network_view.master.winfo_children()[3])
            self.workbook_toggle_var.set("Workbook details ▾")
        self.details_visible = not self.details_visible

    def browse_source(self) -> None:
        current = Path(self.source_var.get())
        filename = filedialog.askopenfilename(
            title="Select source workbook",
            initialdir=str(current.parent if current.parent.exists() else APP_DIR.parent),
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

        previous_label = self.sku_var.get().strip()
        self.data = data
        self.catalog = catalog
        self.all_labels = self.catalog["LABEL"].tolist()
        self.sku_combo["values"] = [""] + self.all_labels
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
            "",
        )
        self.sku_var.set(default)
        if default:
            self.select_sku()
        else:
            self.clear_sku()
        self.status_var.set(f"Loaded {source.name}: {len(self.data):,} unique assignment rows")

    def _set_loading(self, loading: bool, status: str = "") -> None:
        state = "disabled" if loading else "normal"
        self.source_button.configure(state=state)
        self.clear_sku_button.configure(state=state)
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
        self.sku_combo["values"] = [""] + matches
        if not query:
            self.clear_sku()
        elif not matches:
            self._show_pending_sku("No matching SKU or service")
            self.status_var.set(f"No SKU or service contains “{self.sku_var.get().strip()}”")
        else:
            if self.sku_var.get().strip() not in self.all_labels:
                self._show_pending_sku("Press Enter to select the first match")
            self.status_var.set(f"{len(matches):,} matching SKU{'s' if len(matches) != 1 else ''}; press Enter to select the first match")

    def _show_pending_sku(self, message: str) -> None:
        self.service_var.set(message)
        self.user_count_var.set("—")
        if not self.data.empty:
            self.network_view.set_data(self.data.iloc[0:0].copy())

    def select_sku(self) -> None:
        if self.catalog.empty:
            return
        entered = self.sku_var.get().strip()
        if not entered:
            self.clear_sku()
            return
        if entered not in self.all_labels:
            folded = entered.casefold()
            match = next((label for label in self.all_labels if folded in label.casefold()), None)
            if match is None:
                self.status_var.set(f"No SKU or service contains “{entered}”")
                return
            self.sku_var.set(match)

        selected = self.catalog[self.catalog["LABEL"].eq(self.sku_var.get())]
        if selected.empty:
            return
        sku = str(selected["SKU"].iloc[0])
        service = str(selected["SERVICE"].iloc[0])
        user_count = int(selected["USERS"].iloc[0])
        self.service_var.set(service)
        self.user_count_var.set(f"{user_count:,}")
        selected_data = self.data[self.data["SKU"].eq(sku) & self.data["SERVICE"].eq(service)]
        self.network_view.set_data(selected_data)
        self.status_var.set(f"Network for {sku}")

    def clear_sku(self) -> None:
        self.sku_var.set("")
        self.service_var.set("No SKU selected")
        self.user_count_var.set("—")
        if not self.data.empty:
            self.network_view.set_data(self.data.iloc[0:0].copy())
        self.status_var.set("No SKU selected")


def main() -> None:
    root = tk.Tk()
    SkuNetworkApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
