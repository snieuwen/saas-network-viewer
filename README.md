# Oracle Fusion SaaS network viewer

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Open Source](https://img.shields.io/badge/Open%20Source-Yes-brightgreen.svg)](LICENSE)

Oracle Fusion SaaS network viewer is a local, read-only desktop application for exploring the relationships between roles and privileges for one SKU at a time.

## Open source

This project is completely open source. You may use, inspect, modify, and redistribute the application, including for commercial purposes, under the permissive [MIT License](LICENSE). Contributions and forks are welcome.

The application runs locally and does not send workbook data to an external service. Third-party Python packages and components retain their own open-source licenses.

## Independent personal project

This is an independent personal project by Sandor Nieuwenhuijs. It is not an Oracle Corporation product or project and is not sponsored, endorsed, approved, maintained, supported, or warranted by Oracle or its affiliates. Oracle and related product names are trademarks of Oracle and/or its affiliates and are used only to identify the services this viewer relates to. See the [LICENSE](LICENSE) for the complete non-affiliation, trademark, confidentiality, warranty, and liability notices.

## Start

1. Download the real Windows executable using [Download SaaS Network Viewer](https://github.com/snieuwen/saas-network-viewer/raw/refs/heads/main/saas-network-viewer.exe). The complete file is approximately 43 MB; a file of roughly 151 KB is the GitHub web page, not the application.
2. Double-click `start_app.bat` in the complete source folder to run the latest source version. The launcher uses an available Python runtime and falls back to `saas-network-viewer.exe` only when Python is unavailable. You can also start the packaged EXE directly.
3. Choose a workbook in the application. No workbook, SKU, or service is selected at startup.
4. If Windows SmartScreen warns about the unsigned application, verify that it came from this repository before choosing **More info** and **Run anyway**.

The source workbook is only read and is never modified.

## Select a workbook

- Choose **Open workbook** to select an `.xlsx` or `.xlsm` file.
- The workbook must contain a `Raw User Data` worksheet with these columns: `SKU`, `SERVICE`, `USER_LOGIN_HASH`, `PRIVILEGE`, and `ROLE_CODE`.
- The optional `Info` worksheet supplies **Prepared for**, **Usage data collected**, and **DT data collected**.
- Loading runs in the background. If a new workbook is invalid, the previous workbook and network remain active.
- The selected filename and **Prepared for** value appear together above the SKU selector; collection dates appear on the right of the same row.

## Select a SKU

- Type any part of the SKU code or service name. Matching is case-insensitive.
- Press **Enter** to select the first match, or open the list and select a result.
- After a workbook loads, the viewer always keeps a valid SKU selected. Empty or invalid input restores the current selection.
- The service name and total distinct SKU users are shown next to the selection.

## Filter the network

- **Search roles** and **Search privileges** match names case-insensitively.
- **Maximum roles**, **Maximum privileges**, and **Relationships for node selection** determine the initial node set. All three default to 30; the role and privilege spinboxes use the actual number available for the selected SKU as their upper bound. Once the initial nodes are selected, every matching relationship between those nodes is drawn without adding further nodes. Search results always respect these settings.
- **Minimum shared users** removes relationships below the chosen threshold.
- Choose **Apply filters**, press Enter in a numeric field, or use a spinbox arrow to apply numeric changes.
- Choose **Reset filters** to return to the default of 30 roles, 30 privileges, and 30 relationships used for node selection.
- The filter summary shows the number displayed alongside the total number available before the limits are applied.
- The graph selects a connected set of the strongest relationships while maximising useful role and privilege coverage.

## Explore the network

- Circles represent roles; squares represent privileges.
- Roles and privileges are packed independently: larger nodes receive more vertical space, while smaller nodes use less.
- The initial vertical order starts from total SKU users (then name) and applies two weighted topology passes to reduce line crossings. When a selection reveals hidden connections, the revealed nodes are inserted using the same topology ordering while nodes that were already visible retain their relative order. Changing the filters creates a new initial order.
- Roles and privileges revealed by a selection use lighter variants of their normal colours. The legend places **Revealed roles** beside **Roles** and **Revealed privileges** beside **Privileges**; the Excel export identifies them as **Revealed by selection**.
- When a role or privilege maximum hides available nodes, a note below the affected column identifies the limiting control. The note is omitted when all matching nodes are shown.
- Node size represents total distinct users for that role or privilege in the complete SKU.
- Line width represents distinct users shared by that role and privilege in the complete SKU.
- A star marks the most connected nodes in the currently visible network.
- Hover over a node or line to see exact details.
- Select a node to highlight its relationships while keeping the complete visible network in place. The selected role or privilege name is also copied automatically to the Windows clipboard. **Show all connections for selected node** is enabled by default: selecting a role adds any connected privileges omitted by the initial limits, and selecting a privilege adds any omitted connected roles. This works in either direction, including when selecting a node that was just added. Clear the selection to restore the initial limited overview.
- Enable **Show only selected node's connections** to hide unrelated nodes and relationships instead. Active text searches and **Minimum shared users** still apply to expanded selections.
- Clear a selection by selecting the same node again, clicking empty graph space, pressing **Esc**, or choosing **Clear selection**.
- Switch the detail table between **Visible relationships** and **All relationships**.
- Sort the detail table by selecting a column heading. Double-click a row to navigate to that node. Press **Ctrl+C** to copy selected rows.
- Use the mouse wheel to scroll, Shift+wheel to scroll horizontally, Ctrl+wheel or the +/− buttons to zoom, and the middle mouse button to pan.
- **Fit width** restores a useful horizontal scale.

Individual users are deliberately not displayed as nodes. This keeps large SKU networks readable while retaining distinct-user counts in node and relationship weights.

## Export

- **Export PNG…** creates a clean image directly from the network data, including the SKU, service, active filters, legend, and export time. It does not take a screen capture.
- **Export Excel…** includes workbook metadata, all active filters, visible nodes and relationships, and both visible and complete details for a selected node.
- After export, the application can open the containing folder.

## License

Copyright (c) 2026 Sandor Nieuwenhuijs. Released under the [MIT License](LICENSE).
