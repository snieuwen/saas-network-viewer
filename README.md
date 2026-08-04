# SKU Roles and Privileges Network

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Open Source](https://img.shields.io/badge/Open%20Source-Yes-brightgreen.svg)](LICENSE)

A local, read-only desktop application for exploring the relationships between roles and privileges for one SKU at a time.

## Open source

This project is completely open source. You may use, inspect, modify, and redistribute the application, including for commercial purposes, under the permissive [MIT License](LICENSE). Contributions and forks are welcome.

The application runs locally and does not send workbook data to an external service. Third-party Python packages and components retain their own open-source licenses.

## Start

1. Download the real Windows executable using [Download SaaS Network Viewer](https://github.com/snieuwen/Fusion-SaaS-network-viewer/raw/refs/heads/main/saas-network-viewer.exe). The complete file is approximately 43 MB; a file of roughly 151 KB is the GitHub web page, not the application.
2. Start `saas-network-viewer.exe`, or double-click `start_app.bat` when running from the complete source folder.
3. Choose a workbook in the application. No workbook, SKU, or service is selected at startup.
4. If Windows SmartScreen warns about the unsigned application, verify that it came from this repository before choosing **More info** and **Run anyway**.

The source workbook is only read and is never modified.

## Select a workbook

- Choose **Change workbook…** to select an `.xlsx` or `.xlsm` file.
- The workbook must contain a `Raw User Data` worksheet with these columns: `SKU`, `SERVICE`, `USER_LOGIN_HASH`, `PRIVILEGE`, and `ROLE_CODE`.
- The optional `Info` worksheet supplies **Prepared for**, **Usage data collected**, and **DT data collected**.
- Loading runs in the background. If a new workbook is invalid, the previous workbook and network remain active.
- Use **Workbook details** to show or hide the full path and workbook metadata.

## Select or clear a SKU

- Type any part of the SKU code or service name. Matching is case-insensitive.
- Press **Enter** to select the first match, or open the list and select a result.
- Choose the empty list entry, clear the text, or use **Clear SKU** to select no SKU.
- The service name and total distinct SKU users are shown next to the selection.

## Filter the network

- **Search roles** and **Search privileges** match names case-insensitively.
- **Maximum roles**, **Maximum privileges**, and **Maximum relationships** keep the graph readable. Role and privilege limits default to 30 and accept values from 10 through 100. Search results always respect these limits.
- **Minimum shared users** removes relationships below the chosen threshold.
- Choose **Apply filters**, press Enter in a numeric field, or use a spinbox arrow to apply numeric changes.
- Choose **Reset filters** to return to the default of 30 roles and 30 privileges.
- The filter summary shows the number displayed alongside the total number available before the limits are applied.
- The graph selects a connected set of the strongest relationships while maximising useful role and privilege coverage.

## Explore the network

- Circles represent roles; squares represent privileges.
- Node size represents total distinct users for that role or privilege in the complete SKU.
- Line width represents distinct users shared by that role and privilege in the complete SKU.
- A star marks the most connected nodes in the currently visible network.
- Hover over a node or line to see exact details.
- Select a node to highlight its relationships while keeping the complete visible network in place. Enable **Show only selected node's connections** to hide unrelated nodes and relationships instead.
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
