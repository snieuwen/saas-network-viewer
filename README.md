# SKU Roles and Privileges Network

A local, read-only desktop application for exploring the relationships between roles and privileges for one SKU at a time.

## Start

1. Keep the application folder next to the source workbook, or choose another workbook after startup.
2. Double-click `start_app.bat`.
3. If a packaged `SKU_Network_Viewer.exe` is present, the launcher uses it. Otherwise it starts the Python version.
4. SKU `B108674` is selected by default when it exists in the workbook.

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
- **Maximum roles**, **Maximum privileges**, and **Maximum relationships** keep the graph readable. Search results always respect these limits.
- **Minimum shared users** removes relationships below the chosen threshold.
- Choose **Apply filters**, press Enter in a numeric field, or use a spinbox arrow to apply numeric changes.
- Choose **Reset filters** to return to the readable default view.
- The graph selects a connected set of the strongest relationships while maximising useful role and privilege coverage.

## Explore the network

- Circles represent roles; squares represent privileges.
- Node size represents total distinct users for that role or privilege in the complete SKU.
- Line width represents distinct users shared by that role and privilege in the complete SKU.
- A star marks the most connected nodes in the currently visible network.
- Hover over a node or line to see exact details.
- Select a node to inspect its relationships. With **Focus selected node** enabled, the graph shows only its direct neighbours.
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
