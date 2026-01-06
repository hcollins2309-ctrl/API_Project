from fastapi.testclient import TestClient
from app import app, normalize_name
import uuid

client = TestClient(app)


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_create_and_fetch_matchup():
    # Arrange: create a unique matchup so this test does not depend on existing DB state
    unique_my = f"Jax{uuid.uuid4().hex[:8]}"
    payload = {
        "lane": "top",
        "my_champ": unique_my,
        "enemy_champ": "Gnar",
        "rating": 60,
        "explanations": ["Test explanation 1", "Test explanation 2"],
        "gameplan": ["Test plan 1"],
    }

    # Act: create the matchup via the API
    r = client.post("/matchups", json=payload)

    # Assert: creation succeeded and returned an ID
    assert r.status_code == 200
    data = r.json()
    assert data["created"] is True
    matchup_id = data["matchup"]["id"]

    # Act: fetch the matchup details from the API
    r2 = client.get(f"/matchups/{matchup_id}")

    # Assert: persisted data and notes match what was submitted
    assert r2.status_code == 200
    detail = r2.json()

    assert detail["lane"] == "top"
    assert detail["my_champ"] == normalize_name(unique_my)
    assert detail["enemy_champ"] == "Gnar"
    assert detail["rating"] == 60
    assert detail["explanations"] == ["Test explanation 1", "Test explanation 2"]
    assert detail["gameplan"] == ["Test plan 1"]

