"""Generic file I/O helpers with no domain/project-specific knowledge."""

import json


def read_json_file(uploaded_file) -> dict | list:
    """Decode an uploaded file's bytes as UTF-8 JSON.

    Raises ValueError if the bytes cannot be decoded or parsed as JSON.
    """
    try:
        return json.loads(uploaded_file.getvalue().decode("utf-8"))
    except Exception as e:
        raise ValueError("Invalid JSON file.") from e
