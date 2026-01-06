# League Matchup API

A small FastAPI backend for storing and querying explainable League of Legends lane matchups, built as part of an accelerated, self-directed Python learning process.

---

## What this service does

- Lets you create curated lane matchups (champion vs champion, per lane) with a numeric rating.
- Stores explanations and gameplan steps for each matchup in a structured way.
- Saves all data to a local SQLite database so matchups remain available after restarts.
- Exposes a REST API with clear, validated request and response formats.
- Supports filtering and pagination when listing matchups (for example by lane or rating range).
- Includes automated integration tests to verify behaviour and data storage.

---

## Quickstart

### Requirements
- Python 3.10+
- Windows

### Setup and run

```bash
# create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate 

# install dependencies
pip install fastapi uvicorn sqlalchemy pytest httpx

# run the API
python -m uvicorn app:app --reload
