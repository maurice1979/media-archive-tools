"""Common Utils."""

from datetime import datetime
from pathlib import Path

import yaml


def load_events(path: Path) -> list[dict]:
    """Load events from a YAML file and parse their date ranges.

    Parameters
    ----------
    path : Path
        Path to the YAML file containing events.

    Returns
    -------
    list of dict
        List of event dictionaries with 'name', 'start', and 'end' keys.

    """
    with path.open() as f:
        data = yaml.safe_load(f)

    events: list[dict] = []
    for e in data.get("events", []):
        events.append(
            {
                "name": e["name"],
                "start": datetime.strptime(str(e["start"]), "%Y%m%d").date(),
                "end": datetime.strptime(str(e["end"]), "%Y%m%d").date(),
            }
        )

    return events
