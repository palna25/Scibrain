import os

from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv(
    "MONGO_URL",
    "mongodb://localhost:27017"
)

client = MongoClient(MONGO_URL)

db = client["scibrain"]

# ------------------------------------------------------------
# Existing paper collection
# ------------------------------------------------------------

papers_collection = db["papers"]


# ------------------------------------------------------------
# Notebook chat collection
# ------------------------------------------------------------

notebook_chats_collection = db["notebook_chats"]


# ------------------------------------------------------------
# Indexes
# ------------------------------------------------------------

# Every chat_id must be unique.
notebook_chats_collection.create_index(
    [("chat_id", ASCENDING)],
    unique=True
)

# Makes it efficient to retrieve a user's chats
# ordered by most recently updated.
notebook_chats_collection.create_index(
    [
        ("user_id", ASCENDING),
        ("updated_at", DESCENDING)
    ]
)