"""Validation / status-classification helpers for workload data."""


def stream_status(streams: list) -> tuple[str, str]:
    """Return (symbol_html, tooltip) describing a workload row's stream validity."""
    if not streams:
        return '<span style="color:#6B7280;font-size:16px;" title="Empty / No Streams">●</span>', "Empty"
    if any(not str(s.get("stream_id", "")).strip() for s in streams):
        return '<span style="color:#EF4444;font-size:16px;" title="Errors">❗</span>', "Error"
    return '<span style="color:#4CAF50;font-size:16px;" title="Valid Config">✓</span>', "Valid"


def status_icon(passed) -> str:
    """Return an html status symbol for a tri-state pipeline check (None/True/False)."""
    if passed is None:
        return '<span style="color:#6B7280;font-size:14px;" title="Not run">●</span>'
    if passed:
        return '<span style="color:#4CAF50;font-size:14px;" title="Passed">✓</span>'
    return '<span style="color:#EF4444;font-size:14px;" title="Failed">✗</span>'
