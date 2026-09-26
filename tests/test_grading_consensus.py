"""Bewertung aus mehreren Durchgängen (D202, D217): Uneinige Durchgänge holen
einen dritten, und dann zählt ein echter Durchgang mit seiner Begründung."""
from pydantic import BaseModel

from backend.grading_consensus import diverge, settle, settle_exact


class G(BaseModel):
    points: float
    uncertain: bool = False
    rationale: str = ""


def test_half_a_point_apart_asks_for_a_third_pass():
    assert diverge([G(points=3), G(points=2.5)])
    assert not diverge([G(points=3), G(points=3)])
    assert not diverge([G(points=3), G(points=1, uncertain=True)])


def test_the_middle_pass_counts_with_its_own_rationale():
    runs = [G(points=3, rationale="drei"), G(points=2, rationale="zwei"), G(points=2, rationale="zwei b")]
    got = settle_exact(runs, 3)
    assert got["points"] == 2 and got["rationale"].startswith("zwei") and not got["uncertain"]
    # Bis 1.40 wurde gemittelt: 2,5 Punkte mit der Begründung eines Durchgangs.
    assert settle(runs[:2], 3)["points"] == 2.5
    assert settle_exact(runs[:2], 3)["points"] == 2.5, "mit nur zwei Durchgängen bleibt es beim Mittel"
