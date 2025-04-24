"""
File that houses python backend (Flask)
"""

import os
import datetime
import traceback
import pymongo
from bson.objectid import ObjectId
from dotenv import load_dotenv
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo.server_api import ServerApi
from pymongo.errors import ConnectionFailure, ConfigurationError
import requests


def connect_mongodb():
    """
    Connect to the mongodb atlas database
    """
    # MongoDB connection with error handling
    try:
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise ValueError("MONGO_URI not found in environment variables")

        db_name = os.getenv("MONGO_DBNAME")
        if not db_name:
            raise ValueError("MONGO_DBNAME not found in environment variables")

        # Update MongoDB connection to use retry writes and server API
        cxn = pymongo.MongoClient(
            mongo_uri, server_api=ServerApi("1"), retryWrites=True, w="majority"
        )
        db = cxn[db_name]
        # Test connection
        cxn.admin.command("ping")
        print(" * Connected to MongoDB Atlas!")

    except (ConnectionFailure, ConfigurationError) as e:
        print(" * MongoDB connection error:", e)
        db = None
    return db

# FIX THIS
def render_home(app):
    """
    Render home screen
    """
    db = app.config["db"]
    if db is not None:
        # Query the speechSummary collection instead of messages
        query = {"user": current_user.username}
        # Sort by timestamp in descending order (newest first)
        docs = list(db.speechSummary.find(query).sort("timestamp", -1))

        # Add this debug print
        for doc in docs:
            print(f"Home page document: {doc['_id']}, title: {doc.get('title')}")

        return render_template("home.html", docs=docs, username=current_user.username)
    return render_template("home.html", docs=[], username=current_user.username)


def create_app():
    """
    Create Flask App
    """
    app = Flask(__name__)

    app.secret_key = os.getenv("SECRET_KEY", "default_secret_key")

    load_dotenv()

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "login"

    class User(UserMixin):
        """
        User object class for login
        """

        def __init__(self, user_id, username):
            self.id = user_id
            self.username = username

    @login_manager.user_loader
    def load_user(user_id):
        db = app.config["db"]
        if db is not None:
            user_data = db.users.find_one({"_id": ObjectId(user_id)})
            if user_data:
                return User(user_id, user_data["username"])
        return None

    db = connect_mongodb()

    # Store db connection in app config
    app.config["db"] = db

    @app.route("/")
    @login_required
    def home():
        return render_home(app)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form["username"]
            password = request.form["password"]
            db = app.config["db"]
            if db is not None:
                user_data = db.users.find_one({"username": username})
                if user_data and check_password_hash(user_data["password"], password):
                    user = User(user_id=str(user_data["_id"]), username=username)
                    login_user(user)
                    return redirect(url_for("home"))
                return render_template("login.html", error="Invalid credentials")
        return render_template("login.html")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            username = request.form["username"]
            password = request.form["password"]
            db = app.config["db"]
            if db is not None:
                existing_user = db.users.find_one({"username": username})
                if existing_user:
                    return render_template("signup.html", error="User already exists")
                hashed_password = generate_password_hash(password)
                db.users.insert_one({"username": username, "password": hashed_password})
                user_data = db.users.find_one({"username": username})
                user = User(user_id=str(user_data["_id"]), username=username)
                login_user(user)
                return redirect(url_for("onboard"))
        return render_template("signup.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/start_game")
    def start_game():
        pass 

    @app.route("/view_results")
    def view_results():
        db = app.config["db"]
        if db is not None:
            docs = db.stats.find({}, {"_id":1, "numClick": 1, "user": 1}).sort("numClick", 1)
            return render_template("results.html", docs=docs, username=current_user.username)
        return render_template("results.html", docs=[], username=current_user.username)

    @app.route("/update_stats" , methods=["POST"])
    @login_required
    def update_stats():
        pass 

    @app.route("/create_account")
    def create_account():
        pass

    @app.route("/play_game")
    def play_game():
        pass

    return app

if __name__ == "__main__":
    flaskapp = create_app()
    flaskapp.run(host="0.0.0.0", port=5002)