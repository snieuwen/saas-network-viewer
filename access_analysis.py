from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import pandas as pd


REQUIRED_COLUMNS = (
    "SKU",
    "SERVICE",
    "USER_LOGIN_HASH",
    "PRIVILEGE",
    "ROLE_CODE",
)


NETWORK_NODE_COLUMNS = ("ID", "LABEL", "KIND", "WEIGHT")
NETWORK_EDGE_COLUMNS = ("SOURCE", "TARGET", "WEIGHT")


def _empty_network() -> tuple[pd.DataFrame, pd.DataFrame]:
    return (
        pd.DataFrame(columns=NETWORK_NODE_COLUMNS),
        pd.DataFrame(columns=NETWORK_EDGE_COLUMNS),
    )


def load_workbook_info(source: str | Path | BinaryIO) -> dict[str, object]:
    """Read the identifying fields used in the workbook's Info sheet."""
    try:
        info = pd.read_excel(source, sheet_name="Info", header=None, dtype=object)
    except ValueError:
        return {}

    result: dict[str, object] = {}
    for row in info.itertuples(index=False, name=None):
        values = [value for value in row if not pd.isna(value) and str(value).strip()]
        if not values:
            continue
        label = str(values[0]).strip()
        folded = label.casefold()
        if folded.startswith("prepared for"):
            prepared = label[len("Prepared for") :].strip(" :-")
            if not prepared and len(values) > 1:
                prepared = str(values[1]).strip()
            result["prepared_for"] = prepared
        elif folded == "usage data collected" and len(values) > 1:
            result["usage_data_collected"] = values[1]
        elif folded == "dt data collected" and len(values) > 1:
            result["dt_data_collected"] = values[1]
    return result


def build_network_data(
    frame: pd.DataFrame,
    *,
    max_roles: int = 8,
    max_privileges: int = 12,
    max_relationships: int = 36,
    role_query: str = "",
    privilege_query: str = "",
    min_shared_users: int = 1,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create a bounded, connection-aware role/privilege network."""
    if frame.empty:
        return _empty_network()

    full_clean = frame.loc[:, ("USER_LOGIN_HASH", "ROLE_CODE", "PRIVILEGE")].drop_duplicates()
    clean = full_clean
    role_query = str(role_query).strip()
    privilege_query = str(privilege_query).strip()
    if role_query:
        clean = clean[clean["ROLE_CODE"].str.contains(role_query, case=False, regex=False, na=False)]
    if privilege_query:
        clean = clean[clean["PRIVILEGE"].str.contains(privilege_query, case=False, regex=False, na=False)]
    if clean.empty:
        return _empty_network()

    maximum_roles = max(1, int(max_roles))
    maximum_privileges = max(1, int(max_privileges))
    maximum_relationships = max(1, int(max_relationships))
    minimum = max(1, int(min_shared_users))
    candidate_edges = (
        clean.groupby(["ROLE_CODE", "PRIVILEGE"], as_index=False)
        .agg(WEIGHT=("USER_LOGIN_HASH", "nunique"))
    )
    candidate_edges = candidate_edges[candidate_edges["WEIGHT"].ge(minimum)].sort_values(
        ["WEIGHT", "ROLE_CODE", "PRIVILEGE"],
        ascending=[False, True, True],
        kind="stable",
    )
    if candidate_edges.empty:
        return _empty_network()

    # Select the strongest connected relationships instead of independently taking
    # two Top-X lists, which can leave high-ranking but disconnected nodes behind.
    candidates = list(candidate_edges.itertuples(index=False))
    roles: set[str] = set()
    privileges: set[str] = set()
    chosen_pairs: set[tuple[str, str]] = set()

    # First maximise useful node coverage. Weight breaks ties so that coverage is
    # still built from the strongest available relationships.
    while len(chosen_pairs) < maximum_relationships:
        best: tuple[tuple[int, int], str, str, int] | None = None
        for edge in candidates:
            role = str(edge.ROLE_CODE)
            privilege = str(edge.PRIVILEGE)
            if (role, privilege) in chosen_pairs:
                continue
            role_is_new = role not in roles
            privilege_is_new = privilege not in privileges
            if role_is_new and len(roles) >= maximum_roles:
                continue
            if privilege_is_new and len(privileges) >= maximum_privileges:
                continue
            new_nodes = int(role_is_new) + int(privilege_is_new)
            if new_nodes == 0:
                continue
            score = (new_nodes, int(edge.WEIGHT))
            if best is None or score > best[0]:
                best = (score, role, privilege, int(edge.WEIGHT))
        if best is None:
            break
        _, role, privilege, _ = best
        roles.add(role)
        privileges.add(privilege)
        chosen_pairs.add((role, privilege))
        if len(roles) >= maximum_roles and len(privileges) >= maximum_privileges:
            break

    # Then add the strongest remaining relationships between the selected nodes.
    candidate_weights = {
        (str(edge.ROLE_CODE), str(edge.PRIVILEGE)): int(edge.WEIGHT)
        for edge in candidates
    }
    selected_edges: list[dict[str, object]] = [
        {
            "SOURCE": f"role:{role}",
            "TARGET": f"privilege:{privilege}",
            "WEIGHT": candidate_weights[(role, privilege)],
        }
        for role, privilege in sorted(
            chosen_pairs,
            key=lambda pair: (-candidate_weights[pair], pair[0], pair[1]),
        )
    ]
    for edge in candidates:
        role = str(edge.ROLE_CODE)
        privilege = str(edge.PRIVILEGE)
        if role not in roles or privilege not in privileges:
            continue
        if (role, privilege) in chosen_pairs:
            continue
        selected_edges.append(
            {
                "SOURCE": f"role:{role}",
                "TARGET": f"privilege:{privilege}",
                "WEIGHT": int(edge.WEIGHT),
            }
        )
        if len(selected_edges) >= maximum_relationships:
            break

    if not roles or not privileges:
        return _empty_network()

    role_totals = (
        full_clean[full_clean["ROLE_CODE"].isin(roles)]
        .groupby("ROLE_CODE")["USER_LOGIN_HASH"]
        .nunique()
        .to_dict()
    )
    privilege_totals = (
        full_clean[full_clean["PRIVILEGE"].isin(privileges)]
        .groupby("PRIVILEGE")["USER_LOGIN_HASH"]
        .nunique()
        .to_dict()
    )

    role_order = sorted(roles, key=lambda value: (-int(role_totals[value]), value))
    privilege_order = sorted(privileges, key=lambda value: (-int(privilege_totals[value]), value))
    node_rows = [
        {"ID": f"role:{role}", "LABEL": role, "KIND": "role", "WEIGHT": int(role_totals[role])}
        for role in role_order
    ]
    node_rows.extend(
        {
            "ID": f"privilege:{privilege}",
            "LABEL": privilege,
            "KIND": "privilege",
            "WEIGHT": int(privilege_totals[privilege]),
        }
        for privilege in privilege_order
    )

    edge_rows = selected_edges
    connected_ids = {
        str(value)
        for edge in edge_rows
        for value in (edge["SOURCE"], edge["TARGET"])
    }
    node_rows = [node for node in node_rows if str(node["ID"]) in connected_ids]
    return pd.DataFrame(node_rows, columns=NETWORK_NODE_COLUMNS), pd.DataFrame(
        edge_rows, columns=NETWORK_EDGE_COLUMNS
    )


def load_raw_data(source: str | Path | BinaryIO) -> pd.DataFrame:
    """Load and normalize the Raw User Data worksheet."""
    try:
        header = pd.read_excel(source, sheet_name="Raw User Data", nrows=0)
    except ValueError as exc:
        raise ValueError("The workbook does not contain a 'Raw User Data' worksheet.") from exc
    missing = [column for column in REQUIRED_COLUMNS if column not in header.columns]
    if missing:
        raise ValueError(
            "The 'Raw User Data' worksheet is missing required columns: "
            + ", ".join(missing)
        )

    frame = pd.read_excel(
        source,
        sheet_name="Raw User Data",
        usecols=list(REQUIRED_COLUMNS),
        dtype={column: "string" for column in REQUIRED_COLUMNS},
    )

    frame = frame.loc[:, REQUIRED_COLUMNS].copy()
    for column in REQUIRED_COLUMNS:
        frame[column] = frame[column].fillna("").str.strip()

    frame = frame[
        frame["SKU"].ne("")
        & frame["USER_LOGIN_HASH"].ne("")
        & frame["PRIVILEGE"].ne("")
        & frame["ROLE_CODE"].ne("")
    ].drop_duplicates()
    if frame.empty:
        raise ValueError("The 'Raw User Data' worksheet contains no usable assignment rows.")
    frame.loc[frame["SERVICE"].eq(""), "SERVICE"] = "Unknown service"
    return frame.reset_index(drop=True)


def sku_catalog(frame: pd.DataFrame) -> pd.DataFrame:
    catalog = (
        frame.groupby(["SKU", "SERVICE"], as_index=False)
        .agg(USERS=("USER_LOGIN_HASH", "nunique"))
        .sort_values(["SKU", "SERVICE"], kind="stable")
        .reset_index(drop=True)
    )
    catalog["LABEL"] = catalog["SKU"] + " | " + catalog["SERVICE"]
    return catalog
