import pytest
from unittest.mock import MagicMock, patch
from flask import url_for
from web_app.app import create_app
from flask_login import login_user
import os
from werkzeug.security import generate_password_hash
from flask_login import UserMixin
import pytest
from web_app.app import connect_mongodb
from bson.objectid import ObjectId


class TestUser(UserMixin):
    def __init__(self, user_id, username):
        self.id = user_id
        self.username = username

# ----------------------------------------
# Fixtures & Mocks
# ----------------------------------------


#@pytest.fixture
#def login_test_user(client):
#    from web_app.app import User
#    user = User(user_id=str(ObjectId()), username="charlie")  # <-- str(ObjectId()) not "test_id"
#    with client.session_transaction() as sess:
#        sess["_user_id"] = user.id
#    return user

@pytest.fixture
def login_test_user(client):
    user = TestUser(user_id=str(ObjectId()), username="charlie")
    with client.session_transaction() as sess:
        sess["_user_id"] = user.id
    return user

@pytest.fixture
def login_test_user2(client):
    from web_app.app import User  # if you expose User on app
    user = client.application.User(user_id=str(ObjectId()), username="charlie")
    with client.session_transaction() as sess:
        sess["_user_id"] = user.id
    return user


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
        "password": "test",
        "confirm_password": "test"
    }, follow_redirects=True)   # <-- FOLLOW redirects
    
    # Look for the flashed message now
    assert b"Username already exists" in response.data

def test_login_failure(client, mock_db):
    mock_db.users.find_one.return_value = None

    response = client.post("/login", data={
        "username": "invalid",
        "password": "invalid"
    }, follow_redirects=True)  # <-- ADD THIS

    assert response.status_code == 200
    assert b"Invalid credentials" in response.data



# ----------------------------------------
# Protected Routes
# ----------------------------------------

#def test_home_requires_login(client):
#    response = client.get("/", follow_redirects=True)
#    assert response.status_code == 200
#    assert "/login" in response.headers["Location"]

def test_home_requires_login(client):
    response = client.get("/home", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]




#@patch.dict(os.environ, {}, clear=True)
#def test_connect_mongodb_missing_env():
#    from web_app.app import connect_mongodb
#    db = connect_mongodb()
#    assert db is None

@patch.dict(os.environ, {}, clear=True)
def test_connect_mongodb_missing_env():
    with pytest.raises(ValueError, match="MONGO_URI not found"):
        connect_mongodb()

@patch("web_app.app.current_user")
def test_render_home(mock_user, client):
    mock_user.username = "testuser"

    with client.application.test_request_context('/'):
        from web_app.app import render_home
        response = render_home()

    assert "space bar" in response


def test_login_success(client, mock_db):
    mock_db.users.find_one.return_value = {
        "_id": ObjectId(),   # <-- use real ObjectId()
        "username": "alice",
        "password": generate_password_hash("test123")
    }

    response = client.post("/login", data={
        "username": "alice",
        "password": "test123"
    }, follow_redirects=True)

    assert response.status_code == 200


def test_signup_get(client):
    response = client.get("/signup")
    assert response.status_code == 200
    assert b"Create your account" in response.data

def test_signup_user_exists(client, mock_db):
    mock_db.users.find_one.return_value = {"username": "testuser"}
    response = client.post("/signup", data={
        "username": "testuser",
        "password": "secret",
        "confirm_password": "secret"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Username already exists" in response.data


def test_logout_redirects(client, login_test_user):
    response = client.get("/logout", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

@patch("web_app.app.current_user")
def test_results_page(mock_user, client, mock_db, login_test_user):
    mock_user.username = "charlie"
    mock_user.is_authenticated = True

    # Mock find_one to return the latest user's score (needs "_id" to avoid KeyError)
    mock_db.statistics.find_one.return_value = {
        "_id": ObjectId(), 
        "numClick": 120
    }

    # Mock find().sort() to return all scores
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = [
        {"numClick": 50},
        {"numClick": 100},
        {"numClick": 120},
        {"numClick": 150}
    ]
    mock_db.statistics.find.return_value = mock_cursor

    response = client.get("/results", follow_redirects=True)

    assert response.status_code == 200
    assert b"View Profile" in response.data



def test_create_account_page(client):
    response = client.get("/create_account")
    assert response.status_code == 200
    assert b"Create your account" in response.data


#def test_play_game_requires_login(client):
#    response = client.get("/play_game", follow_redirects=True)
#    assert "/login" in response.headers["Location"]

@patch("web_app.app.current_user")
def test_play_game_requires_login(mock_user, client):
    mock_user.is_authenticated = False  # Pretend user is NOT logged in

    response = client.get("/play_game", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# ----------------------------------------
# Profile Logic
# ----------------------------------------

def test_profile_stats_with_data(client, mock_db, login_test_user):
    mock_db.statistics.find.return_value = [
        {"numClick": 100},
        {"numClick": 200},
        {"numClick": 300}
    ]

    response = client.get("/profile", follow_redirects=True)
    assert response.status_code == 200
    assert b"300" in response.data
    assert b"200.0" in response.data
    assert b"3" in response.data


@patch("web_app.app.current_user")
def test_profile_stats_no_data(mock_user, client, mock_db):
    mock_user.is_authenticated = True
    mock_user.username = "bob"
    mock_db.statistics.find.return_value = []
    response = client.get("/profile", follow_redirects=True)
    assert b"0" in response.data

# ----------------------------------------
# Game Results
# ----------------------------------------

#@patch("web_app.app.current_user")
#def test_view_results_inserts_score(mock_user, client, mock_db):
#    mock_user.is_authenticated = True
#    mock_user.username = "charlie"
#    mock_db.statistics.insert_one.return_value = None
#
#    response = client.post("/view_results", json={"score": 123})
#    assert response.status_code == 200
#    assert b"success" in response.data
#    mock_db.statistics.insert_one.assert_called_with({
#        "numClick": 123,
#        "user": "charlie"
#    })


@patch("web_app.app.current_user")
def test_view_results_inserts_score(mock_user, client, mock_db, login_test_user):
    # Mock the current_user inside the app
    mock_user.is_authenticated = True
    mock_user.username = login_test_user.username

    # Send POST request
    response = client.post("/view_results", json={"score": 123})

    # Print call arguments for debug (optional while testing)
    print(mock_db.statistics.insert_one.call_args)

    # Check response
    assert response.status_code == 200
    assert b"success" in response.data

    # Verify the DB insert
    mock_db.statistics.insert_one.assert_called_once_with({
        "numClick": 123,
        "user": "charlie"   # login_test_user.username
    })

def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"JITTER" in response.data

def test_check_username_available(client, mock_db):
    mock_db.users.find_one.return_value = None
    response = client.post("/check_username", json={"username": "newuser"})
    assert response.status_code == 200
    assert response.json["available"] is True

def test_check_username_taken(client, mock_db):
    mock_db.users.find_one.return_value = {"username": "existing"}
    response = client.post("/check_username", json={"username": "existing"})
    assert response.status_code == 200
    assert response.json["available"] is False

def test_signup_passwords_dont_match(client):
    response = client.post("/signup", data={
        "username": "user1",
        "password": "pass1",
        "confirm_password": "notmatching"
    }, follow_redirects=True)
    assert b"Passwords did not match" in response.data

@patch("web_app.app.current_user")
def test_leaderboard_page(mock_user, client, mock_db, login_test_user):
    mock_user.is_authenticated = True
    mock_user.username = "charlie"

    mock_db.statistics.aggregate.side_effect = [
        [{"user": "a", "numClick": 300}, {"user": "b", "numClick": 250}],  # all_time
        [{"user": "a", "numClick": 150}, {"user": "c", "numClick": 140}],  # daily
        [{"_id": "a", "averageScore": 200.0, "gamesPlayed": 5}]           # average
    ]

    response = client.get("/leaderboard", follow_redirects=True)
    assert response.status_code == 200
    assert b"leaderboard" in response.data.lower()
