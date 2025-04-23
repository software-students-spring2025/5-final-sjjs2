from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,  # Add this
    url_for,
)
from flask_pymongo import PyMongo
import os
from dotenv import load_dotenv
import pymongo
from bson.objectid import ObjectId
#from .userdb import insert_data, check_user
import datetime
from flask import session

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")


connection = pymongo.MongoClient(
    os.getenv("MONGO_URI")
)

db = connection["NAME OF COLLECTION"]


@app.route("/")
def func ():
    pass


@app.route("/add_restaurant", methods=["POST"])
def func ():
    pass

@app.route("/search", methods=["GET"])
def func ():
    pass
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5001)

