from pathlib import Path
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.postgres import get_db
from app.database.mongodb import (papers_collection,notebooks_collection,
    notebook_chats_collection)
from app.models.user import User
from app.core.dependencies import get_current_admin
from app.services.vector_store import delete_paper_chunks


router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"],
)

logger = logging.getLogger(__name__)
# ==========================================================
# ADMIN DASHBOARD STATISTICS
# ==========================================================

@router.get("/statistics")
def get_admin_statistics(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    total_users = db.query(User).count()

    active_users = (
        db.query(User)
        .filter(User.is_active.is_(True))
        .count()
    )

    total_papers = papers_collection.count_documents({})

    # SciBrain's actual successful paper status is "ready".
    # Keep "analyzed" in the response for frontend compatibility.
    analyzed_papers = papers_collection.count_documents({
        "status": "ready",
    })
    total_notebooks = notebooks_collection.count_documents({})
    total_chats = notebook_chats_collection.count_documents({})

    return {
        "users": {
            "total": total_users,
            "active": active_users,
        },
        "papers": {
            "total": total_papers,
            "analyzed": analyzed_papers,
            
        },
        "notebooks": {
            "total": total_notebooks,
        },
        "chats": {
            "total": total_chats,
        },
    }


# ==========================================================
# GET ALL USERS
# ==========================================================

@router.get("/users")
def get_users(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    users = (
        db.query(User)
        .order_by(User.created_at.desc())
        .all()
    )

    return [
        {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "last_login": user.last_login,
        }
        for user in users
    ]


# ==========================================================
# UPDATE USER STATUS
# ==========================================================

class UserStatusUpdate(BaseModel):
    is_active: bool


@router.patch("/users/{user_id}/status")
def update_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found.",
        )

    if user.id == admin.id and not payload.is_active:
        raise HTTPException(
            status_code=400,
            detail="The admin account cannot be deactivated.",
        )

    if user.is_active == payload.is_active:
        return {
            "id": user.id,
            "is_active": user.is_active,
            "message": (
                "User is already active."
                if user.is_active
                else "User is already inactive."
            ),
        }

    user.is_active = payload.is_active

    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to update user status.",
        )

    return {
        "id": user.id,
        "is_active": user.is_active,
        "message": (
            "User activated successfully."
            if user.is_active
            else "User deactivated successfully."
        ),
    }


# ==========================================================
# DELETE USER
# ==========================================================

@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found.",
        )

    if user.id == admin.id:
        raise HTTPException(
            status_code=400,
            detail="The admin account cannot be deleted.",
        )

    try:
        db.delete(user)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to delete user.",
        )

    return {
        "message": "User deleted successfully.",
    }


# ==========================================================
# GET ALL PAPERS
# ==========================================================

@router.get("/papers")
def get_admin_papers(
    admin: User = Depends(get_current_admin),
):
    papers = list(
        papers_collection.find(
            {},
            {
                "_id": 1,
                "title": 1,
                "filename": 1,
                "page_count": 1,
                "status": 1,
                "uploaded_at": 1,
                "analysis": 1,
            },
        ).sort("uploaded_at", -1)
    )

    return [
        {
            "id": str(paper["_id"]),
            "title": paper.get("title", "Untitled Paper"),
            "filename": paper.get("filename", ""),
            "page_count": paper.get("page_count", 0),
            "status": paper.get("status", "uploaded"),
            "uploaded_at": paper.get("uploaded_at"),
            "has_analysis": paper.get("analysis") is not None,
        }
        for paper in papers
    ]


# ==========================================================
# DELETE PAPER
# ==========================================================


@router.delete("/papers/{paper_id}")
def delete_paper(
    paper_id: str,
    admin: User = Depends(get_current_admin),
):
    paper = papers_collection.find_one({"_id": paper_id})

    if not paper:
        raise HTTPException(
            status_code=404,
            detail="Paper not found.",
        )

    stage = "Qdrant chunk cleanup"

    try:
        # 1. Remove indexed chunks first.
        # If this fails, retain the PDF and MongoDB record.
        delete_paper_chunks(paper_id=paper_id)

        # 2. Remove the stored PDF, if one is recorded.
        stage = "stored PDF cleanup"
        stored_path = paper.get("file_path")

        if stored_path:
            backend_root = Path(__file__).resolve().parents[2]
            upload_dir = (backend_root / "uploads" / "papers").resolve()

            pdf_path = Path(stored_path)

            if not pdf_path.is_absolute():
                pdf_path = backend_root / pdf_path

            pdf_path = pdf_path.resolve()

            # Never allow a database path to delete files
            # outside the papers upload directory.
            try:
                pdf_path.relative_to(upload_dir)
            except ValueError as error:
                raise RuntimeError(
                    "The stored PDF path is outside the papers upload directory."
                ) from error

            # A missing PDF is okay during a retry.
            if pdf_path.is_file():
                pdf_path.unlink()

        # 3. Delete the MongoDB record last.
        stage = "MongoDB record deletion"
        result = papers_collection.delete_one({"_id": paper_id})

        if result.deleted_count != 1:
            raise RuntimeError(
                "MongoDB did not delete exactly one paper record."
            )

    except Exception as error:
        logger.exception(
            "Paper deletion failed for %s during %s",
            paper_id,
            stage,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Paper deletion failed during {stage}. "
                "Some cleanup steps may already have succeeded. "
                "Check the backend logs before retrying."
            ),
        ) from error

    return {
        "message": "Paper and associated stored data deleted successfully."
    }
