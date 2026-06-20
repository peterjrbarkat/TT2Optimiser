"""Persistent logging of optimizer runs to a Google Sheet.

Each run is stored as one wide row:
    timestamp | <one column per ingredient (count)> | <one column per loot type (importance)>

This is used to build the aggregate "community" statistics (box plots of
ingredient counts and a loot-importance vote tally) and to power the
admin-only data export.

Configuration (Streamlit secrets):
    [gcp_service_account]
    # full service-account JSON contents (type, project_id, private_key, ...)

    [gsheets]
    sheet_key = "<spreadsheet id from the sheet URL>"

If these secrets are missing, logging silently no-ops so local development
still works without a backend.
"""

import datetime

import pandas as pd
import streamlit as st

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_TIMESTAMP_COL = "timestamp"


def is_logging_configured() -> bool:
    """Return True only if the Google Sheets backend is fully configured."""
    try:
        return "gcp_service_account" in st.secrets and "gsheets" in st.secrets
    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def _get_worksheet():
    """Authorise with the service account and return the first worksheet.

    Cached as a resource so we only build one client per server process.
    """
    import gspread
    from google.oauth2.service_account import Credentials

    sa_info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(sa_info, scopes=_SCOPES)
    client = gspread.authorize(creds)
    sheet_key = st.secrets["gsheets"]["sheet_key"]
    return client.open_by_key(sheet_key).sheet1


def _build_header(ingredient_order, loot_order) -> list[str]:
    return [_TIMESTAMP_COL, *ingredient_order, *loot_order]


def log_run(ingredient_counts, importance_scores, ingredient_order, loot_order) -> bool:
    """Append a single run to the sheet. Returns True on success.

    Fails gracefully (returns False) if the backend is not configured or any
    network/auth error occurs, so the optimizer UX is never blocked by logging.
    """
    if not is_logging_configured():
        return False
    try:
        ws = _get_worksheet()
        header = _build_header(ingredient_order, loot_order)

        # Write the header row once if the sheet has no content yet.
        # Note: gspread returns [[]] (truthy) for an empty sheet, so check
        # for actual cell content rather than truthiness of the list.
        existing = ws.get_all_values()
        if not any(any(cell for cell in row) for row in existing):
            ws.append_row(header, value_input_option="USER_ENTERED")

        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        row = [timestamp]
        row += [ingredient_counts.get(name, "") for name in ingredient_order]
        row += [importance_scores.get(name, "") for name in loot_order]
        ws.append_row(row, value_input_option="USER_ENTERED")

        # New row won't appear in the cached fetch until it is invalidated.
        fetch_runs.clear()
        return True
    except Exception as exc:  # noqa: BLE001 - logging must never crash the app
        st.session_state["_run_logging_error"] = str(exc)
        return False


@st.cache_data(ttl=300, show_spinner=False)
def fetch_runs() -> pd.DataFrame:
    """Return all logged runs as a DataFrame (empty if unconfigured/unavailable)."""
    if not is_logging_configured():
        return pd.DataFrame()
    try:
        ws = _get_worksheet()
        records = ws.get_all_records()
        return pd.DataFrame(records)
    except Exception as exc:  # noqa: BLE001
        st.session_state["_run_logging_error"] = str(exc)
        return pd.DataFrame()
