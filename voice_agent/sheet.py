"""Google Sheet access via gspread + a service account.

The sheet is the call queue. Columns (header row, case-insensitive):
    name, phone, email, consent_given, status, transcript

Share the sheet with the service account's client_email (Editor).
"""

import gspread

from . import config

# Expected header names, lowercased.
_COLS = ("name", "phone", "email", "consent_given", "status", "transcript")


def _open_worksheet():
    gc = gspread.service_account(filename=config.GOOGLE_SERVICE_ACCOUNT_JSON)
    return gc.open_by_key(config.SHEET_ID).worksheet(config.SHEET_TAB)


def _col_index(header: list[str], name: str) -> int:
    """1-based column index for a header name (case-insensitive)."""
    lower = [h.strip().lower() for h in header]
    return lower.index(name) + 1


def get_lead(row_number: int) -> dict:
    """Read one lead row (1-based, including header offset).

    Returns a dict with keys from _COLS plus 'row' (the sheet row number).
    Raises ValueError if the row is empty.
    """
    ws = _open_worksheet()
    header = ws.row_values(1)
    values = ws.row_values(row_number)
    if not values:
        raise ValueError(f"Row {row_number} is empty")

    lower = [h.strip().lower() for h in header]
    lead = {"row": row_number}
    for col in _COLS:
        if col in lower:
            idx = lower.index(col)
            lead[col] = values[idx] if idx < len(values) else ""
        else:
            lead[col] = ""
    return lead


def consent_given(lead: dict) -> bool:
    """True if the consent_given cell is an affirmative value."""
    return str(lead.get("consent_given", "")).strip().lower() in {
        "true", "yes", "y", "1", "x", "✓",
    }


def write_result(row_number: int, status: str, transcript: str) -> None:
    """Write status + transcript back to the lead's row."""
    ws = _open_worksheet()
    header = ws.row_values(1)
    status_col = _col_index(header, "status")
    transcript_col = _col_index(header, "transcript")

    ws.update_cell(row_number, status_col, status)
    ws.update_cell(row_number, transcript_col, transcript)
