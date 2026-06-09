"""Grade <-> points conversion (KMK standard).

Canonical storage is points 0..15 (15 = 1+, 0 = 6). Sek I displays a
school grade with tendency, Sek II displays the point value. Everything is
convertible so a later Notenausgleich can compute on a single scale.
"""

from __future__ import annotations

# points -> Sek-I grade label (with tendency)
POINTS_TO_NOTE: dict[int, str] = {
    15: "1+", 14: "1", 13: "1−",
    12: "2+", 11: "2", 10: "2−",
    9: "3+", 8: "3", 7: "3−",
    6: "4+", 5: "4", 4: "4−",
    3: "5+", 2: "5", 1: "5−",
    0: "6",
}


def note_label(points: int | None) -> str | None:
    if points is None:
        return None
    return POINTS_TO_NOTE.get(points)


def points_label(points: int | None) -> str | None:
    """Sek II style: '11 P. (2)'."""
    if points is None:
        return None
    return f"{points} P. ({POINTS_TO_NOTE.get(points, '?')})"


def display_label(points: int | None, section: str | None) -> str | None:
    if points is None:
        return None
    if section == "sek2":
        return points_label(points)
    return note_label(points)


def options(section: str | None) -> list[dict]:
    """Dropdown options for the given section, highest grade first."""
    out = []
    for p in range(15, -1, -1):
        if section == "sek2":
            out.append({"points": p, "label": f"{p} ({POINTS_TO_NOTE[p]})"})
        else:
            out.append({"points": p, "label": POINTS_TO_NOTE[p]})
    return out
