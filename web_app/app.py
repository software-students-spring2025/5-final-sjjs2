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
from flask import current_app
import math


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

def render_home():
    return render_template("game.html", username=current_user.username)


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
        return render_home()

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
                return redirect(url_for("login"))
        return render_template("signup.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))
    
    
    @app.route("/view_results" , methods=["POST"])
    @login_required
    def view_results():
        db = app.config["db"]
        if db is not None:
            data = request.get_json()
            clicks = data.get("score")
            add = {
                "numClick": clicks,
                "user": current_user.username,
            }
            db.statistics.insert_one(add)
            return jsonify({
                "status": "success",
                "redirect": url_for("results_page")
            })

    @app.route("/results")
    @login_required
    def results_page():
        db = app.config["db"]
        user_score = db.statistics.find_one({"user": current_user.username}, sort=[("_id", -1)])["numClick"]
        docs = db.statistics.find({}, {"_id":0, "numClick": 1}).sort("numClick", 1)
        all_scores = [d["numClick"] for d in docs if "numClick" in d]

        bin_size = 10
        max_score = max(all_scores)
        bin = [0] * (math.ceil(max_score / bin_size) + 1)

        for score in all_scores:
            i = score // bin_size
            bin[i] += 1

        num_less = sum(1 for s in all_scores if s < user_score)
        percentile = round(100 * num_less / len(all_scores), 1)

        return render_template(
            "results.html", 
            bins=bin, 
            username=current_user.username, 
            bin_size=bin_size, 
            user_score=user_score, 
            percentile=percentile
        )

    @app.route("/create_account")
    def create_account():
        return render_template("signup.html")
    
    @login_required
    @app.route("/play_game")
    def play_game():
        return render_template("game.html")
    
    @app.route("/profile")
    @login_required
    def profile():
        db = current_app.config["db"]
        username = current_user.username

        # Pull all scores for this user from the database
        stats_cursor = db.statistics.find({"user": username})
        stats = list(stats_cursor)

        # Safely compute profile stats
        if stats:
            scores = [s["numClick"] for s in stats if "numClick" in s]
            top_score = max(scores)
            avg_score = round(sum(scores) / len(scores), 1)
            games_played = len(scores)
        else:
            top_score = 0
            avg_score = 0
            games_played = 0

        return render_template(
            "profile.html",
            username=username,
            top_score=top_score,
            avg_score=avg_score,
            games_played=games_played
        )

    return app

if __name__ == "__main__":
    flaskapp = create_app()
    flaskapp.run(host="0.0.0.0", port=5002)