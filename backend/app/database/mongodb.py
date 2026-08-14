import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv(
    "MONGO_URL",
    "mongodb://localhost:27017"
)

client = MongoClient(MONGO_URL)

db = client["scibrain"]

papers_collection = db["papers"]