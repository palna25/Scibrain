
import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(PROJECT_ROOT / "backend" / ".env", override=False)


def build_mongo_url() -> str:
    configured_url = os.getenv("MONGO_URL")
    if configured_url:
        return configured_url

    username = os.getenv("MONGO_USERNAME")
    password = os.getenv("MONGO_PASSWORD")
    host = os.getenv("MONGO_HOST", "localhost")
    port = os.getenv("MONGO_PORT", "27017")

    if username and password:
        return (
            f"mongodb://{quote_plus(username)}:{quote_plus(password)}"
            f"@{host}:{port}/?authSource=admin"
        )

    raise RuntimeError(
        "MongoDB credentials are missing. Configure MONGO_URL or both "
        "MONGO_USERNAME and MONGO_PASSWORD in the project environment."
    )


MONGO_URL = build_mongo_url()

client = MongoClient(
    MONGO_URL,
    serverSelectionTimeoutMS=5000,
)

db = client["scibrain"]

# Core collections
papers_collection = db["papers"]
notebooks_collection = db["notebooks"]
notebook_chats_collection = db["notebook_chats"]
knowledge_graphs_collection = db["knowledge_graphs"]

# Research Gaps collections
research_gap_analyses_collection = db["research_gap_analyses"]
research_gap_source_selections_collection = db[
    "research_gap_source_selections"
]

# Notebook indexes
notebooks_collection.create_index(
    [("notebook_id", ASCENDING)],
    unique=True,
)

notebooks_collection.create_index(
    [
        ("user_id", ASCENDING),
        ("updated_at", DESCENDING),
    ]
)

notebooks_collection.create_index(
    [
        ("user_id", ASCENDING),
        ("notebook_id", ASCENDING),
    ]
)

# Notebook chat indexes
notebook_chats_collection.create_index(
    [("chat_id", ASCENDING)],
    unique=True,
)

notebook_chats_collection.create_index(
    [
        ("notebook_id", ASCENDING),
        ("updated_at", DESCENDING),
    ]
)

notebook_chats_collection.create_index(
    [
        ("user_id", ASCENDING),
        ("updated_at", DESCENDING),
    ]
)

# Saved Research Gaps analysis indexes
research_gap_analyses_collection.create_index(
    [("analysis_id", ASCENDING)],
    unique=True,
)

research_gap_analyses_collection.create_index(
    [
        ("user_id", ASCENDING),
        ("notebook_id", ASCENDING),
        ("created_at", DESCENDING),
    ]
)

# Independent Research Gaps source-selection index.
# Each user gets one independent selection per notebook.
research_gap_source_selections_collection.create_index(
    [
        ("user_id", ASCENDING),
        ("notebook_id", ASCENDING),
    ],
    unique=True,
    name="unique_user_research_gap_source_selection",
)
