"""
eFootball Match Tracker API
============================
Install:  pip install fastapi uvicorn
Run:      uvicorn main:app --reload
Docs:     http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from collections import defaultdict

app = FastAPI(title="eFootball Tracker", version="1.0")

# ── Storage ───────────────────────────────────────────────────────────────────
matches: dict[int, dict] = {}
_next_id = 1


# ── Schemas ───────────────────────────────────────────────────────────────────
Result = Literal["win", "loss", "draw"]

class MatchIn(BaseModel):
    my_team:       str = Field(example="Manchester City")
    opponent:      str = Field(example="Barcelona")
    formation:     str = Field(example="4-3-3")
    goals_for:     int = Field(ge=0, example=3)
    goals_against: int = Field(ge=0, example=1)
    result:        Result
    note:          Optional[str] = Field(None, example="Played really well")

class MatchOut(MatchIn):
    id:        int
    played_at: str


# ── Helpers ───────────────────────────────────────────────────────────────────
def _get(match_id: int) -> dict:
    m = matches.get(match_id)
    if not m:
        raise HTTPException(404, "Match not found")
    return m

def _all_sorted() -> list[dict]:
    return sorted(matches.values(), key=lambda m: m["played_at"], reverse=True)


# ── CRUD ──────────────────────────────────────────────────────────────────────
@app.post("/matches", response_model=MatchOut, status_code=201, tags=["Matches"])
def log_match(payload: MatchIn):
    """Log a new match."""
    global _next_id
    m = payload.model_dump()
    m["id"] = _next_id
    m["played_at"] = datetime.now().isoformat(timespec="seconds")
    matches[_next_id] = m
    _next_id += 1
    return m

@app.get("/matches", response_model=list[MatchOut], tags=["Matches"])
def list_matches(result: Optional[Result] = None, opponent: Optional[str] = None):
    """List all matches. Filter by result= or opponent=."""
    data = _all_sorted()
    if result:
        data = [m for m in data if m["result"] == result]
    if opponent:
        data = [m for m in data if opponent.lower() in m["opponent"].lower()]
    return data

@app.get("/matches/{match_id}", response_model=MatchOut, tags=["Matches"])
def get_match(match_id: int):
    """Get a single match by ID."""
    return _get(match_id)

@app.delete("/matches/{match_id}", tags=["Matches"])
def delete_match(match_id: int):
    """Delete a match by ID."""
    _get(match_id)
    del matches[match_id]
    return {"detail": f"Match {match_id} deleted"}


# ── Stats ─────────────────────────────────────────────────────────────────────
@app.get("/stats", tags=["Stats"])
def overall_stats():
    """Overall stats: win rate, goals, current streak."""
    if not matches:
        return {"message": "No matches logged yet"}

    data = _all_sorted()
    total  = len(data)
    wins   = sum(1 for m in data if m["result"] == "win")
    losses = sum(1 for m in data if m["result"] == "loss")
    draws  = sum(1 for m in data if m["result"] == "draw")
    gf     = sum(m["goals_for"]     for m in data)
    ga     = sum(m["goals_against"] for m in data)

    # Current streak — how many in a row of the same result
    streak_val = 1
    streak_res = data[0]["result"]
    for m in data[1:]:
        if m["result"] == streak_res:
            streak_val += 1
        else:
            break

    return {
        "total_matches": total,
        "wins":   wins,
        "losses": losses,
        "draws":  draws,
        "win_rate":    f"{wins / total * 100:.1f}%",
        "goals_for":     gf,
        "goals_against": ga,
        "goal_diff":     gf - ga,
        "current_streak": {"result": streak_res, "count": streak_val},
    }


@app.get("/stats/formations", tags=["Stats"])
def formation_stats():
    """Win rate broken down by formation."""
    if not matches:
        return []

    fdata: dict[str, dict] = defaultdict(lambda: {"wins": 0, "losses": 0, "draws": 0})
    for m in matches.values():
        fdata[m["formation"]][m["result"] + "s"] += 1

    result = []
    for formation, s in fdata.items():
        total = s["wins"] + s["losses"] + s["draws"]
        result.append({
            "formation": formation,
            "played":  total,
            "wins":    s["wins"],
            "losses":  s["losses"],
            "draws":   s["draws"],
            "win_rate": f"{s['wins'] / total * 100:.1f}%",
        })

    return sorted(result, key=lambda x: x["wins"], reverse=True)


@app.get("/nemesis", tags=["Stats"])
def nemesis():
    """Top 5 opponents you lose to the most."""
    if not matches:
        return []

    opp: dict[str, dict] = defaultdict(lambda: {"wins": 0, "losses": 0, "draws": 0})
    for m in matches.values():
        opp[m["opponent"]][m["result"] + "s"] += 1

    result = []
    for name, s in opp.items():
        total = s["wins"] + s["losses"] + s["draws"]
        result.append({
            "opponent":    name,
            "played":      total,
            "your_wins":   s["wins"],
            "your_losses": s["losses"],
            "your_draws":  s["draws"],
            "loss_rate":   f"{s['losses'] / total * 100:.1f}%",
        })

    return sorted(result, key=lambda x: x["your_losses"], reverse=True)[:5]


@app.get("/best-match", tags=["Stats"])
def best_match():
    """Your best win by goal difference."""
    wins = [m for m in matches.values() if m["result"] == "win"]
    if not wins:
        return {"message": "No wins logged yet"}
    return max(wins, key=lambda m: m["goals_for"] - m["goals_against"])
