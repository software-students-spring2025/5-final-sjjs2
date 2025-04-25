import pytest
from unittest.mock import MagicMock, patch
from flask import url_for
from web_app.app import create_app

# ----------------------------------------
# Fixtures & Mocks
# ----------------------------------------

@pytest.fixture
def mock_db():
    mock = MagicMock()
    mock.users = MagicMock()
    mock.statistics = MagicMock()
    return mock

@pytest.fixture
def client(mock_db):
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "testing"
    app.config["LOGIN_DISABLED"] = False
    app.config["db"] = mock_db

    with app.test_client() as client:
        yield client

# ----------------------------------------
# Auth Tests
# ----------------------------------------

def test_signup_user_already_exists(client, mock_db):
    mock_db.users.find_one.return_value = {"username": "alice"}
    response = client.post("/signup", data={
        "username": "alice",
        "password": "test"
    }, follow_redirects=True)
    assert b"User already exists" in response.data

def test_login_failure(client, mock_db):
    mock_db.users.find_one.return_value = None
    response = client.post("/login", data={
        "username": "invalid",
        "password": "invalid"
    }, follow_redirects=True)
    assert b"Invalid credentials" in response.data

# ----------------------------------------
# Protected Routes
# ----------------------------------------

def test_home_requires_login(client):
    response = client.get("/", follow_redirects=True)
    assert b"Log in" in response.data

def test_play_game_requires_login(client):
    response = client.get("/play_game", follow_redirects=True)
    assert b"Log in" in response.data

# ----------------------------------------
# Profile Logic
# ----------------------------------------

@patch("web_app.app.current_user")
def test_profile_stats_with_data(mock_user, client, mock_db):
    mock_user.username = "alice"
    mock_db.statistics.find.return_value = [
        {"numClick": 100}, {"numClick": 200}, {"numClick": 300}
    ]
    response = client.get("/profile")
    assert b"300" in response.data  # top score
    assert b"200.0" in response.data  # average
    assert b"3" in response.data  # games played

@patch("web_app.app.current_user")
def test_profile_stats_no_data(mock_user, client, mock_db):
    mock_user.username = "bob"
    mock_db.statistics.find.return_value = []
    response = client.get("/profile")
    assert b"0" in response.data

# ----------------------------------------
# Game Results
# ----------------------------------------

@patch("web_app.app.current_user")
def test_view_results_inserts_score(mock_user, client, mock_db):
    mock_user.username = "charlie"
    mock_db.statistics.insert_one.return_value = None

    response = client.post("/view_results", json={"score": 123})
    assert response.status_code == 200
    assert b"success" in response.data
    mock_db.statistics.insert_one.assert_called_with({
        "numClick": 123,
        "user": "charlie"
    })
