# Oracle Fusion SaaS network viewer

Current version: **v0.9.0**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Open Source](https://img.shields.io/badge/Open%20Source-Yes-brightgreen.svg)](LICENSE)

Oracle Fusion SaaS network viewer is a local, read-only desktop application for exploring the relationships between roles and privileges for one SKU at a time.

## Open source

This project is completely open source. You may use, inspect, modify, and redistribute the application, including for commercial purposes, under the permissive [MIT License](LICENSE). Contributions and forks are welcome.

The application runs locally and does not send workbook data to an external service. Third-party Python packages and components retain their own open-source licenses.

## Independent personal project

This is an independent personal project by Sandor Nieuwenhuijs. It is not an Oracle Corporation product or project and is not sponsored, endorsed, approved, maintained, supported, or warranted by Oracle or its affiliates. Oracle and related product names are trademarks of Oracle and/or its affiliates and are used only to identify the services this viewer relates to. See the [LICENSE](LICENSE) for the complete non-affiliation, trademark, confidentiality, warranty, and liability notices.

## Start on Windows

1. Download the real Windows executable using [Download SaaS Network Viewer](https://github.com/snieuwen/saas-network-viewer/raw/refs/heads/main/saas-network-viewer.exe). The complete file is approximately 43 MB; a file of roughly 151 KB is the GitHub web page, not the application.
2. Double-click `start_app.bat` in the complete source folder to run the latest source version. The launcher uses an available Python runtime and falls back to `saas-network-viewer.exe` only when Python is unavailable. You can also start the packaged EXE directly.
3. Choose a workbook in the application. No workbook, SKU, or service is selected at startup.
4. If Windows SmartScreen warns about the unsigned application, verify that it came from this repository before choosing **More info** and **Run anyway**.

The source workbook is only read and is never modified.

## Start on Apple Silicon macOS

1. Download `saas-network-viewer-macos-apple-silicon-v0.9.0.zip` from the [v0.9.0 release](https://github.com/snieuwen/saas-network-viewer/releases/tag/v0.9.0).
2. Unzip it and move **Oracle Fusion SaaS network viewer.app** to **Applications**.
3. The app is ad-hoc signed but not Apple-notarized. On first launch, Control-click the app, choose **Open**, and confirm **Open** if Gatekeeper asks. Only do this for a copy downloaded from this repository.
4. Choose a workbook in the application. No workbook, SKU, or service is selected at startup.

The macOS build is a self-contained Apple Silicon application and does not require Python or the source repository. It is built natively on GitHub's `macos-15` arm64 runner. Intel Macs are not supported by this build.

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
- **Role groups** provides independent checkboxes for **Oracle predefined**, **Application Implementation**, and **Read-only** roles. Oracle predefined roles are identified by an `ORA_` role-code prefix. Application Implementation roles are identified by `APPLICATION_IMPLEMENTATION` in the role code and form a separate group even when their code also starts with `ORA_`.
- **Read-only role word** classifies role codes case-insensitively without acting as a normal search. Matching roles receive the blue read-only colour, while non-matching roles remain visible. Clear the **Read-only** checkbox to exclude only the matching roles. A read-only match has priority over the other role groups.
- **Abstract roles** is an independent filter because an abstract role can also be Oracle predefined, custom, or read-only. Abstract roles are identified by the `_ABSTRACT` role-code suffix. Clear the checkbox to exclude them.
- **Other roles**, shown as the final role-group checkbox, includes only roles that are not Oracle predefined, Application Implementation, read-only matches, or Abstract roles. It is enabled by default and uses the orange role colour.
- **Maximum roles**, **Maximum privileges**, and **Relationships for node selection** determine the initial node set. All three default to 30; the role and privilege spinboxes use the actual number available for the selected SKU as their upper bound. Once the initial nodes are selected, every matching relationship between those nodes is drawn without adding further nodes. Search results always respect these settings.
- **Minimum role/privilege users** excludes roles and privileges used by fewer than the specified number of total SKU users. It defaults to 1.
- **Minimum shared users** removes relationships below the chosen threshold.
- Choose **Apply filters**, press Enter in a numeric field, or use a spinbox arrow to apply numeric changes.
- Choose **Reset filters** to return to the default of 30 roles, 30 privileges, and 30 relationships used for node selection.
- The filter summary shows the number displayed alongside the total number available before the limits are applied.
- The SKU selection area shows both **Total SKU users** and **Filtered SKU users**. The filtered count updates with the active name, role-group, read-only, Abstract, Other-role, and minimum-user filters.
- The graph selects a connected set of the strongest relationships while maximising useful role and privilege coverage.

## Explore the network

- Circles represent roles; squares represent privileges.
- Role colours distinguish ordinary roles, Oracle predefined roles, Application Implementation roles, and roles matching the configured read-only word. These display classifications are included in PNG and Excel exports. They describe role provenance or naming only and do not determine effective access or licensing impact.
- A small **A** badge identifies abstract roles without replacing their existing group colour. Role tooltips show the inferred role type and display group. The badge and role type are also included in exports.
- Roles and privileges are packed independently: larger nodes receive more vertical space, while smaller nodes use less.
- The initial vertical order starts from total SKU users (then name) and applies two weighted topology passes to reduce line crossings. When a selection reveals hidden connections, the revealed nodes are inserted using the same topology ordering while nodes that were already visible retain their relative order. Changing the filters creates a new initial order.
- Roles and privileges revealed by a selection use lighter variants of their normal colours. The legend places **Revealed roles** beside **Roles** and **Revealed privileges** beside **Privileges**; the Excel export identifies them as **Revealed by selection**.
- When a role or privilege maximum hides available nodes, a note below the affected column identifies the limiting control. The note is omitted when all matching nodes are shown.
- Node size represents total distinct users for that role or privilege in the complete SKU.
- Line width represents distinct users shared by that role and privilege in the complete SKU.
- A star marks the most connected nodes in the currently visible network.
- Hover over a node or line to see exact details.
- Select a node to highlight its relationships while keeping the complete visible network in place. The selected role or privilege name is also copied automatically to the Windows clipboard. **Show all connections for selected node** is enabled by default: selecting a role adds any connected privileges omitted by the initial limits, and selecting a privilege adds any omitted connected roles. This works in either direction, including when selecting a node that was just added. Clear the selection to restore the initial limited overview.
- Enable **Show only selected node's connections** to hide unrelated nodes and relationships instead. Active text searches, **Minimum role/privilege users**, and **Minimum shared users** still apply to expanded selections.
- Select **Show details** to open the relationship table at the bottom and **Hide details** to return that space to the network. The panel starts collapsed and always reflects the current selection when opened.
- Clear a selection by selecting the same node again, clicking empty graph space, pressing **Esc**, or choosing **Clear selection**.
- Switch the detail table between **Visible relationships** and **All relationships**.
- Sort the detail table by selecting a column heading. Double-click a row to navigate to that node. Press **Ctrl+C** to copy selected rows.
- Use the mouse wheel to scroll, Shift+wheel to scroll horizontally, Ctrl+wheel or the +/− buttons to zoom, and the middle mouse button to pan.
- **Fit width** restores a useful horizontal scale.

Individual users are deliberately not displayed as nodes. This keeps large SKU networks readable while retaining distinct-user counts in node and relationship weights.

## User guide

The illustrated English user guide is available in both [Word](docs/Oracle-Fusion-SaaS-Network-Viewer-User-Guide.docx) and [PDF](docs/Oracle-Fusion-SaaS-Network-Viewer-User-Guide.pdf) format. It covers installation, workbook requirements, filters, network interpretation, two-way role/privilege exploration, details, exports, recommended workflows, and troubleshooting.

## Export

- **Export PNG…** creates a clean image directly from the network data, including the SKU, service, active filters, legend, and export time. It does not take a screen capture.
- **Export Excel…** includes workbook metadata, all active filters, visible nodes and relationships, and both visible and complete details for a selected node.
- After export, the application can open the containing folder.

## Scenario analysis

- Select a node, or use Ctrl/Shift+click to select several role and privilege nodes. Right-click a selected node and choose **Add selected nodes to scenario…**.
- Choose an existing scenario from the list or choose **Create new scenario…** and enter a name. A scenario records excluded roles and privileges only; it never changes the source workbook or the displayed network.
- The confirmation shows a simple access-based impact: users with an excluded assignment, users remaining in scope, and users with no remaining assignment after the exclusions.
- Choose **Scenario report…** in the main title bar to compare the unrestricted baseline with up to two named scenarios side by side. Comparison headings and values are left-aligned. Long role and privilege exclusion lists are abbreviated to fit the current column width; resize a column to show more or fewer entries, or double-click a scenario (or use **View complete exclusions…**) to open the complete scrollable list.
- In the report, select a scenario and choose **Edit selected scenario…** to remove individual role or privilege exclusions.
- Each scenario is automatically saved as its own JSON file in the local **SaaS Network Viewer** application-data `scenarios` folder. The file is named after the scenario, and saved scenarios are loaded automatically when the application starts. Use **Reload saved scenarios** in the report after adding files to that folder manually. Scenarios are matched to their SKU and service, so unrelated scenarios are not offered for comparison.
- Scenario results are an access-based estimate, not a contractual licence determination. Confirm the applicable Oracle metric, entitlement terms, and licence rules separately.

## License

Copyright (c) 2026 Sandor Nieuwenhuijs. Released under the [MIT License](LICENSE).
