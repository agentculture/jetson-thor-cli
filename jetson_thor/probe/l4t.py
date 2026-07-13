"""``thor l4t`` — the flashed L4T/JetPack release from /etc/nv_tegra_release.

Jetson boards stamp their flashed L4T (Linux for Tegra) release into a single
comment line in ``/etc/nv_tegra_release``, e.g.::

    # R38 (release), REVISION: 2.2, GCID: 42205042, BOARD: generic,
    # EABI: aarch64, DATE: Thu Sep 25 22:47:11 UTC 2025

which this collector turns into a compact ``"R38.2.2"`` string plus the
individual fields. The file doesn't exist on non-Jetson hosts, so absence
degrades to ``unavailable`` rather than raising.
"""

from __future__ import annotations

import re
from typing import Optional

from jetson_thor.probe._report import report, unavailable
from jetson_thor.probe._run import read_text

_RELEASE_RE = re.compile(r"^R(?P<release>\d+)\s*\(release\)")


def _parse_fields(line: str) -> Optional[dict[str, str]]:
    """Parse one ``# R38 (release), REVISION: 2.2, KEY: value, ...`` line."""
    parts = [p.strip() for p in line.lstrip("#").strip().split(",")]
    if not parts:
        return None
    match = _RELEASE_RE.match(parts[0])
    if not match:
        return None
    fields = {"RELEASE": match.group("release")}
    for part in parts[1:]:
        if ":" not in part:
            continue
        key, _, value = part.partition(":")
        key = key.strip().upper()
        value = value.strip()
        if key and value:
            fields[key] = value
    return fields


def _parse(text: str) -> Optional[dict]:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        fields = _parse_fields(stripped)
        if fields is None:
            continue
        revision = fields.get("REVISION")
        if not revision:
            continue
        release = fields["RELEASE"]
        return {
            "release": f"R{release}",
            "revision": revision,
            "l4t": f"R{release}.{revision}",
            "gcid": fields.get("GCID"),
            "board": fields.get("BOARD"),
            "eabi": fields.get("EABI"),
            "date": fields.get("DATE"),
        }
    return None


def collect(path: str = "/etc/nv_tegra_release") -> dict:
    """Return the parsed L4T release from ``path`` (injectable for tests)."""
    text = read_text(path)
    if not text:
        return unavailable("l4t", path, "run on a Jetson board (non-Jetson hosts lack this file)")

    parsed = _parse(text)
    if parsed is None:
        return unavailable("l4t", path, f"unrecognized format in {path}")

    items = [
        f"L4T: {parsed['l4t']}",
        f"release: {parsed['release']}",
        f"revision: {parsed['revision']}",
    ]
    if parsed["board"]:
        items.append(f"board: {parsed['board']}")
    if parsed["gcid"]:
        items.append(f"GCID: {parsed['gcid']}")
    if parsed["date"]:
        items.append(f"built: {parsed['date']}")

    sections = [{"title": "L4T release", "items": items}]
    return report("l4t", source=path, sections=sections, data=parsed)
