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
from datetime import datetime, timedelta
from flask import flash, get_flashed_messages
import pytz  # Add pytz for timezone handling


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

    # Function to get current EST datetime
    def get_est_datetime():
        """Get the current datetime in Eastern Time"""
        eastern = pytz.timezone('US/Eastern')
        return datetime.now(eastern)

    # Function to get EST day boundaries
    def get_est_day_boundaries():
        """Get the start and end of the current day in EST"""
        eastern = pytz.timezone('US/Eastern')
        est_now = datetime.now(eastern)
        est_today_start = eastern.localize(datetime(est_now.year, est_now.month, est_now.day))
        est_tomorrow_start = est_today_start + timedelta(days=1)
        # Convert to UTC for MongoDB (ObjectId uses UTC)
        utc_today_start = est_today_start.astimezone(pytz.UTC)
        utc_tomorrow_start = est_tomorrow_start.astimezone(pytz.UTC)
        
        return est_now, utc_today_start, utc_tomorrow_start

    @app.route("/")
    def index(): 
        return render_template("index.html")

    @app.route("/home")
    @login_required
    def home():
        return render_home()

    # Add this new route to check username availability
    @app.route("/check_username", methods=["POST"])
    def check_username():
        data = request.get_json()
        username = data.get("username", "")
        
        db = current_app.config["db"]
        if db is not None:
            # Case insensitive search using a regular expression
            existing_user = db.users.find_one({"username": {"$regex": f"^{username}$", "$options": "i"}})
            return jsonify({"available": existing_user is None})
        
        # Default to unavailable if DB connection issues
        return jsonify({"available": False})

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form["username"]
            password = request.form["password"]
            db = app.config["db"]
            if db is not None:
                # Case insensitive search using a regular expression
                user_data = db.users.find_one({"username": {"$regex": f"^{username}$", "$options": "i"}})
                if user_data and check_password_hash(user_data["password"], password):
                    # Use the exact username case from the database
                    user = User(user_id=str(user_data["_id"]), username=user_data["username"])
                    login_user(user)
                    return redirect(url_for("home"))
                flash("Invalid credentials", "error")
                return redirect(url_for("login"))
                #return render_template("login.html", error="Invalid username or password. Please try again.")
        return render_template("login.html")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            username = request.form["username"]
            password = request.form["password"]
            confirm_password = request.form.get("confirm_password")
            
            # Check if passwords match
            if password != confirm_password:
                # Redirect to login with a flash message instead of showing an error
                flash("Passwords did not match. Please try again.")
                return redirect(url_for("signup"))
                
            db = app.config["db"]
            if db is not None:
                # Case insensitive check for existing username
                existing_user = db.users.find_one({"username": {"$regex": f"^{username}$", "$options": "i"}})
                if existing_user:
                    # Redirect to login with a flash message instead of showing an error
                    flash("Username already exists. Please log in or choose a different username.")
                    return redirect(url_for("signup"))
                    
                hashed_password = generate_password_hash(password)
                # Store the username as provided by the user (preserving case)
                db.users.insert_one({
                    "username": username,
                    "password": hashed_password
                })
                
                # Get the user data for login
                user_data = db.users.find_one({"username": {"$regex": f"^{username}$", "$options": "i"}})
                user = User(user_id=str(user_data["_id"]), username=user_data["username"])
                login_user(user)
                return redirect(url_for("home"))
        
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
            
            # Get current EST time for the record
            est_now = get_est_datetime()
            
            add = {
                "numClick": clicks,
                "user": current_user.username,
                "timestamp": est_now.replace(tzinfo=None),  # Store as naive datetime for compatibility
                "timezone": "EST"  # Mark the timezone for reference
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
        # Get the most recent score for this user
        latest_score = db.statistics.find_one({"user": current_user.username}, sort=[("_id", -1)])
        user_score = latest_score["numClick"]
        
        # Get all user scores for distribution calculation
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

        # Get user's previous top score to check if this is a new personal best
        previous_scores = list(db.statistics.find(
            {"user": current_user.username, "_id": {"$ne": latest_score["_id"]}},
            sort=[("numClick", -1)]
        ))
        
        # Check if this is a new personal best
        is_personal_best = False
        if not previous_scores:
            # First game, automatically a personal best
            is_personal_best = True
        else:
            previous_best = max(s["numClick"] for s in previous_scores) if previous_scores else 0
            # Only set to true if the new score is HIGHER than previous best, not equal
            is_personal_best = user_score > previous_best

        return render_template(
            "results.html", 
            bins=bin, 
            username=current_user.username, 
            bin_size=bin_size, 
            user_score=user_score, 
            percentile=percentile,
            is_personal_best=is_personal_best
        )

    @app.route("/create_account")
    def create_account():
        return render_template("signup.html")
    
    
    @app.route("/play_game")
    @login_required
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

    @app.route("/leaderboard")
    @login_required
    def leaderboard():
        db = current_app.config["db"]
        
        # Get EST time boundaries for today
        est_now, utc_today_start, utc_tomorrow_start = get_est_day_boundaries()
        
        # Format date string for display - use EST time for display
        daily_date = est_now.strftime("%B %d, %Y") + " (EST)"
        
        # Get all-time top scores, sorting by score (desc) and then by _id (desc) for most recent
        all_time_pipeline = [
            {"$sort": {"numClick": -1, "_id": -1}},  # Sort by score and then by _id (recent first)
            {"$limit": 10}  # Get exactly top 10
        ]
        all_time_results = list(db.statistics.aggregate(all_time_pipeline))
        
        # Format all-time leaderboard with proper ranking (handling ties)
        all_time_leaderboard = []
        current_rank = 1
        previous_score = None
        
        for result in all_time_results:
            if previous_score is not None and result["numClick"] < previous_score:
                current_rank += 1
            
            all_time_leaderboard.append({
                "rank": current_rank,
                "username": result.get("user", "Unknown"),
                "score": result["numClick"]
            })
            
            previous_score = result["numClick"]
        
        # Get daily top scores using the timestamp field for EST-based filtering
        # For records with timestamp, use it directly
        # For records without timestamp (older entries), fall back to ObjectId filtering
        
        # First, try to find any existing timestamp field to ensure backward compatibility
        has_timestamp = db.statistics.find_one({"timestamp": {"$exists": True}})
        
        if has_timestamp:
            # Use timestamp field for filtering
            utc_today_naive = utc_today_start.replace(tzinfo=None)
            utc_tomorrow_naive = utc_tomorrow_start.replace(tzinfo=None)
            
            daily_pipeline = [
                {"$match": {"timestamp": {"$gte": utc_today_naive, "$lt": utc_tomorrow_naive}}},
                {"$sort": {"numClick": -1, "_id": -1}},
                {"$limit": 10}
            ]
        else:
            # Fall back to ObjectId filtering
            today_id = ObjectId.from_datetime(utc_today_start.replace(tzinfo=None))
            tomorrow_id = ObjectId.from_datetime(utc_tomorrow_start.replace(tzinfo=None))
            
            daily_pipeline = [
                {"$match": {"_id": {"$gte": today_id, "$lt": tomorrow_id}}},
                {"$sort": {"numClick": -1, "_id": -1}},
                {"$limit": 10}
            ]
        
        daily_results = list(db.statistics.aggregate(daily_pipeline))
        
        # Format daily leaderboard with proper ranking (handling ties)
        daily_leaderboard = []
        current_rank = 1
        previous_score = None
        
        for result in daily_results:
            if previous_score is not None and result["numClick"] < previous_score:
                current_rank += 1
            
            daily_leaderboard.append({
                "rank": current_rank,
                "username": result.get("user", "Unknown"),
                "score": result["numClick"]
            })
            
            previous_score = result["numClick"]
        
        # Get top players by average score
        # First group by user and calculate average scores
        average_pipeline = [
            {"$group": {
                "_id": "$user",
                "averageScore": {"$avg": "$numClick"},
                "gamesPlayed": {"$sum": 1}
            }},
            # Only include users with at least 3 games played to avoid outliers
            {"$match": {"gamesPlayed": {"$gte": 3}}},
            {"$sort": {"averageScore": -1}},
            {"$limit": 10}
        ]
        
        average_results = list(db.statistics.aggregate(average_pipeline))
        
        # Format average leaderboard with proper ranking (handling ties)
        average_leaderboard = []
        current_rank = 1
        previous_score = None
        
        for result in average_results:
            if previous_score is not None and round(result["averageScore"], 1) < previous_score:
                current_rank += 1
            
            average_leaderboard.append({
                "rank": current_rank,
                "username": result.get("_id", "Unknown"),
                "score": round(result["averageScore"], 1)  # Round to 1 decimal place
            })
            
            previous_score = round(result["averageScore"], 1)
        
        # Ensure all leaderboards have at least 10 entries for consistent height
        # Fill with empty entries if needed
        while len(all_time_leaderboard) < 10:
            all_time_leaderboard.append({
                "rank": "-",
                "username": "-",
                "score": "-"
            })
            
        while len(daily_leaderboard) < 10:
            daily_leaderboard.append({
                "rank": "-",
                "username": "-",
                "score": "-"
            })
            
        while len(average_leaderboard) < 10:
            average_leaderboard.append({
                "rank": "-",
                "username": "-",
                "score": "-"
            })
        
        return render_template(
            "leaderboard.html",
            all_time_leaderboard=all_time_leaderboard,
            daily_leaderboard=daily_leaderboard,
            average_leaderboard=average_leaderboard,
            daily_date=daily_date
        )

    @app.route("/one_v_one_setup")
    @login_required
    def one_v_one_setup():
        return render_template("one_v_one_setup.html")

    @app.route("/one_v_one_game")
    @login_required
    def one_v_one_game():
        return render_template("one_v_one_game.html")

    @app.route("/one_v_one_results")
    @login_required
    def one_v_one_results():
        return render_template("one_v_one_results.html")
    
    return app

if __name__ == "__main__":
    flaskapp = create_app()
    flaskapp.run(host="0.0.0.0", port=5002)