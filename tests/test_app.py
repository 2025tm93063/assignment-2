import pytest
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, init_db


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.environ["DB_PATH"] = db_path
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"

    # Re-import DB_PATH into the app module so get_db() picks up the temp path
    import app as app_module
    app_module.DB_PATH = db_path
    app_module.init_db()

    with app.test_client() as c:
        yield c

    os.close(db_fd)
    os.unlink(db_path)


# ── health & version ──────────────────────────────────────────────────────────

def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_health_returns_version(client):
    r = client.get("/health")
    assert "version" in r.get_json()


def test_version_endpoint(client):
    r = client.get("/version")
    assert r.status_code == 200
    assert "version" in r.get_json()


# ── auth ─────────────────────────────────────────────────────────────────────

def test_login_page_loads(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"ACEest" in r.data


def test_valid_login_redirects(client):
    r = client.post("/", data={"username": "admin", "password": "admin123"}, follow_redirects=False)
    assert r.status_code == 302
    assert "/dashboard" in r.headers["Location"]


def test_invalid_login_shows_error(client):
    r = client.post("/", data={"username": "admin", "password": "wrongpass"})
    assert r.status_code == 200
    assert b"Invalid" in r.data


def test_dashboard_requires_login(client):
    r = client.get("/dashboard", follow_redirects=False)
    assert r.status_code == 302


def test_dashboard_accessible_after_login(client):
    client.post("/", data={"username": "admin", "password": "admin123"})
    r = client.get("/dashboard")
    assert r.status_code == 200


# ── clients API ──────────────────────────────────────────────────────────────

def test_list_clients_empty(client):
    r = client.get("/clients")
    assert r.status_code == 200
    assert r.get_json() == []


def test_add_client_success(client):
    r = client.post("/clients", json={"name": "TestUser", "age": 25, "weight": 70, "program": "Fat Loss (FL)"})
    assert r.status_code == 201
    assert r.get_json()["name"] == "TestUser"


def test_add_client_missing_name(client):
    r = client.post("/clients", json={"age": 25})
    assert r.status_code == 400


def test_add_duplicate_client(client):
    client.post("/clients", json={"name": "DupUser"})
    r = client.post("/clients", json={"name": "DupUser"})
    assert r.status_code == 409


def test_get_client_by_name(client):
    client.post("/clients", json={"name": "GetUser", "weight": 80, "program": "Muscle Gain (MG)"})
    r = client.get("/clients/GetUser")
    assert r.status_code == 200
    assert r.get_json()["name"] == "GetUser"


def test_get_nonexistent_client(client):
    r = client.get("/clients/NoSuchPerson")
    assert r.status_code == 404


def test_delete_client(client):
    client.post("/clients", json={"name": "ToDelete"})
    r = client.delete("/clients/ToDelete")
    assert r.status_code == 200
    assert client.get("/clients/ToDelete").status_code == 404


def test_calorie_calculation(client):
    client.post("/clients", json={"name": "CalUser", "weight": 80, "program": "Muscle Gain (MG)"})
    r = client.get("/clients/CalUser")
    data = r.get_json()
    assert data["calories"] == 80 * 35


# ── progress API ─────────────────────────────────────────────────────────────

def test_add_and_get_progress(client):
    client.post("/clients", json={"name": "ProgUser"})
    r = client.post("/clients/ProgUser/progress", json={"adherence": 85, "week": "Week 01 - 2026"})
    assert r.status_code == 201
    r2 = client.get("/clients/ProgUser/progress")
    data = r2.get_json()
    assert len(data) == 1
    assert data[0]["adherence"] == 85


def test_progress_empty_by_default(client):
    client.post("/clients", json={"name": "EmptyProg"})
    r = client.get("/clients/EmptyProg/progress")
    assert r.get_json() == []


# ── workouts API ─────────────────────────────────────────────────────────────

def test_add_and_get_workout(client):
    client.post("/clients", json={"name": "WorkUser"})
    r = client.post("/clients/WorkUser/workouts", json={
        "date": "2026-01-10", "workout_type": "Strength", "duration_min": 60, "notes": "Heavy day"
    })
    assert r.status_code == 201
    r2 = client.get("/clients/WorkUser/workouts")
    data = r2.get_json()
    assert len(data) == 1
    assert data[0]["workout_type"] == "Strength"


# ── programs API ─────────────────────────────────────────────────────────────

def test_list_programs(client):
    r = client.get("/programs")
    assert r.status_code == 200
    data = r.get_json()
    assert "Fat Loss (FL)" in data
    assert "Muscle Gain (MG)" in data
    assert "Beginner (BG)" in data


def test_get_program_detail(client):
    r = client.get("/programs/Fat Loss (FL)")
    assert r.status_code == 200
    assert "workout" in r.get_json()


def test_get_invalid_program(client):
    r = client.get("/programs/NonExistentProgram")
    assert r.status_code == 404


def test_list_clients_after_add(client):
    client.post("/clients", json={"name": "ListCheck"})
    r = client.get("/clients")
    names = [c["name"] for c in r.get_json()]
    assert "ListCheck" in names
