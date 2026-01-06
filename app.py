"""
League Matchups API

A small FastAPI backend for storing and querying curated lane matchups.
Focus: clear API contracts, persistence (SQLite), and explainable outputs.
"""

from fastapi import FastAPI, Query
from pydantic import BaseModel

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Literal, List, Dict, Tuple

from sqlalchemy import create_engine, Column, Integer, String, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker

# --- Database setup (SQLite) ---
# SQLite keeps setup friction near-zero (single file DB).
# `check_same_thread=False` allows SQLite use across FastAPI request threads.
engine = create_engine("sqlite:///matchups.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class MatchupRow(Base):
    __tablename__ = "matchups"

    id = Column(Integer, primary_key=True, index=True)
    lane = Column(String, nullable=False)
    my_champ = Column(String, nullable=False)
    enemy_champ = Column(String, nullable=False)
    rating = Column(Integer, nullable=False)

    # Prevent duplicate matchups per lane (also enforced in the API for a friendly message).
    __table_args__ = (UniqueConstraint("lane", "my_champ", "enemy_champ", name="uq_matchup"),)

class MatchupNoteRow(Base):
    __tablename__ = "matchup_notes"

    id = Column(Integer, primary_key=True, index=True)
    matchup_id = Column(Integer, nullable=False, index=True)  # simple FK style for now
    kind = Column(String, nullable=False)  # "explanation" or "gameplan"
    text = Column(String, nullable=False)
    order_index = Column(Integer, nullable=False)


Base.metadata.create_all(bind=engine)


# ----- Request / Response models (validation contracts) -----

Lane = Literal["top", "jungle", "mid", "bot", "support"]


class MatchupRequest(BaseModel):
    lane: Lane = Field(description="Lane the matchup is played in")
    my_champ: str = Field(min_length=2, description="Your champion name, e.g. 'Darius'")
    enemy_champ: str = Field(min_length=2, description="Enemy champion name, e.g. 'Garen'")


class MatchupResponse(BaseModel):
    lane: str
    my_champ: str
    enemy_champ: str
    rating: int  # 0..100
    explanations: List[str]
    gameplan: List[str]


@app.get("/health")
def health():
    return {"status": "ok"}


# ----- Tiny “data” (curated, small, obvious) -----
# Intentionally small for now, can be extended later
# Format: (my, enemy, lane) -> (base_rating, explanations, gameplan)
MATCHUP_DB: Dict[Tuple[str, str, str], Tuple[int, List[str], List[str]]] = {
    ("Darius", "Garen", "top"): (
        65,
        [
            "You have strong extended trades and a pull that can punish short trade patterns.",
            "If you get an early lead, you can deny waves with threat of all-in.",
        ],
        [
            "Level 1–2: look for extended trades if you can maintain spacing.",
            "Hold wave near your side to punish oversteps.",
            "Track jungle: you’re strongest when fights stay long, weakest when kited/CC-chained.",
        ],
    ),
    ("Ahri", "Zed", "mid"): (
        45,
        [
            "Enemy has strong all-in windows; your safety depends on holding key cooldowns.",
            "If you use mobility aggressively, you may lose your escape vs the all-in.",
        ],
        [
            "Play for wave control; don’t take coinflip trades before first recall.",
            "Save your main defensive tool for the all-in timing.",
            "Ping missing early: roam timings matter in this matchup.",
        ],
    ),
}


def normalize_name(name: str) -> str:
    """
    Normalize champion names for consistent storage and querying.

    Note: `.title()` is a simplification. It can mangle names like "Kha'Zix".
    A later upgrade would normalize by mapping against a canonical champion list.
    """
    return name.strip().title()


@app.post("/matchup", response_model=MatchupResponse)
def matchup(req: MatchupRequest):
    my = normalize_name(req.my_champ)
    enemy = normalize_name(req.enemy_champ)
    lane = req.lane

    # Look up the matchup in our tiny curated DB
    key = (my, enemy, lane)
    if key in MATCHUP_DB:
        base_rating, explanations, gameplan = MATCHUP_DB[key]
        rating = base_rating
    else:
        # Fallback: return a neutral answer with guidance.
        rating = 50
        explanations = [
            "No curated matchup entry found. Returning a neutral baseline.",
            "Add a matchup entry to improve accuracy and explainability.",
        ]
        gameplan = [
            "Focus on fundamentals: wave control, vision timings, and tracking jungle.",
            "Avoid high-variance trades until you understand key cooldown windows.",
        ]

    return MatchupResponse(
        lane=lane,
        my_champ=my,
        enemy_champ=enemy,
        rating=rating,
        explanations=explanations,
        gameplan=gameplan,
    )

class CreateMatchupRequest(BaseModel):
    lane: Lane
    my_champ: str = Field(min_length=2)
    enemy_champ: str = Field(min_length=2)
    rating: int = Field(ge=0, le=100)
    explanations: List[str] = Field(min_length=1)
    gameplan: List[str] = Field(min_length=1)

@app.get("/matchups")
@app.get("/matchups")
def list_matchups(
    lane: Lane | None = None,
    my_champ: str | None = None,
    enemy_champ: str | None = None,
    min_rating: int | None = Query(default=None, ge=0, le=100),
    max_rating: int | None = Query(default=None, ge=0, le=100),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    db = SessionLocal()
    try:
        q = db.query(MatchupRow)

        if lane is not None:
            q = q.filter(MatchupRow.lane == lane)

        if my_champ is not None:
            q = q.filter(MatchupRow.my_champ == normalize_name(my_champ))

        if enemy_champ is not None:
            q = q.filter(MatchupRow.enemy_champ == normalize_name(enemy_champ))

        if min_rating is not None:
            q = q.filter(MatchupRow.rating >= min_rating)

        if max_rating is not None:
            q = q.filter(MatchupRow.rating <= max_rating)

        total = q.count()

        rows = (
            q.order_by(MatchupRow.rating.desc(), MatchupRow.lane, MatchupRow.my_champ, MatchupRow.enemy_champ)
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "total": total,
            "count": len(rows),
            "limit": limit,
            "offset": offset,
            "matchups": [
                {
                    "id": r.id,
                    "lane": r.lane,
                    "my_champ": r.my_champ,
                    "enemy_champ": r.enemy_champ,
                    "rating": r.rating,
                }
                for r in rows
            ],
        }
    finally:
        db.close()

@app.post("/matchups")
def create_matchup(req: CreateMatchupRequest):
    my = normalize_name(req.my_champ)
    enemy = normalize_name(req.enemy_champ)
    lane = req.lane

    db = SessionLocal()
    try:
        # Detect duplicates before insert so clients get a stable, readable error response.
        # The DB unique constraint still acts as the final safeguard.
        existing = (
            db.query(MatchupRow)
            .filter(
                MatchupRow.lane == lane,
                MatchupRow.my_champ == my,
                MatchupRow.enemy_champ == enemy,
            )
            .first()
        )
        if existing:
            return {
                "error": "Matchup already exists",
                "existing": {"id": existing.id, "lane": lane, "my_champ": my, "enemy_champ": enemy},
            }

        # Insert notes as rows so ordering is explicit and the API can return structured explanations/gameplans.
        # 1) create matchup
        row = MatchupRow(lane=lane, my_champ=my, enemy_champ=enemy, rating=req.rating)
        db.add(row)
        db.commit()
        db.refresh(row)

        # 2) create notes (explanations + gameplan)
        notes_to_add = []

        for i, text in enumerate(req.explanations):
            notes_to_add.append(
                MatchupNoteRow(
                    matchup_id=row.id,
                    kind="explanation",
                    text=text.strip(),
                    order_index=i,
                )
            )

        for i, text in enumerate(req.gameplan):
            notes_to_add.append(
                MatchupNoteRow(
                    matchup_id=row.id,
                    kind="gameplan",
                    text=text.strip(),
                    order_index=i,
                )
            )

        db.add_all(notes_to_add)
        db.commit()

        return {
            "created": True,
            "matchup": {"id": row.id, "lane": lane, "my_champ": my, "enemy_champ": enemy, "rating": row.rating},
            "notes_saved": len(notes_to_add),
        }
    finally:
        db.close()

@app.get("/matchups/{matchup_id}")
def get_matchup(matchup_id: int):
    db = SessionLocal()
    try:
        row = db.query(MatchupRow).filter(MatchupRow.id == matchup_id).first()
        if row is None:
            return {"error": "Not found", "matchup_id": matchup_id}

        notes = (
            db.query(MatchupNoteRow)
            .filter(MatchupNoteRow.matchup_id == matchup_id)
            .order_by(MatchupNoteRow.kind, MatchupNoteRow.order_index)
            .all()
        )

        explanations = [n.text for n in notes if n.kind == "explanation"]
        gameplan = [n.text for n in notes if n.kind == "gameplan"]

        return {
            "id": row.id,
            "lane": row.lane,
            "my_champ": row.my_champ,
            "enemy_champ": row.enemy_champ,
            "rating": row.rating,
            "explanations": explanations,
            "gameplan": gameplan,
        }
    finally:
        db.close()

