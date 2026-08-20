from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.postgres import get_db
from app.models.user import User
from app.core.dependencies import get_current_admin
from app.database.mongodb import papers_collection


router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"]
)


# ==========================================================
# ADMIN DASHBOARD STATISTICS
# ==========================================================

@router.get("/statistics")
def get_admin_statistics(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    total_users = db.query(User).count()

    active_users = (
        db.query(User)
        .filter(User.is_active == True)
        .count()
    )

    total_papers = papers_collection.count_documents({})

    analyzed_papers = papers_collection.count_documents({
        "status": "analyzed"
    })

    processing_papers = papers_collection.count_documents({
        "status": "processing"
    })

    failed_papers = papers_collection.count_documents({
        "status": "error"
    })

    return {
        "users": {
            "total": total_users,
            "active": active_users,
        },
        "papers": {
            "total": total_papers,
            "analyzed": analyzed_papers,
            "processing": processing_papers,
            "failed": failed_papers,
        }
    }


# ==========================================================
# GET USERS
# ==========================================================

@router.get("/users")
def get_users(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
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
# DEACTIVATE USER
# ==========================================================

@router.patch("/users/{user_id}/status")
def update_user_status(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found."
        )

    # Prevent the admin from disabling itself
    if user.id == admin.id:
        raise HTTPException(
            status_code=400,
            detail="The admin account cannot be deactivated."
        )

    user.is_active = not user.is_active

    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "is_active": user.is_active,
        "message": (
            "User activated successfully."
            if user.is_active
            else "User deactivated successfully."
        )
    }


# ==========================================================
# DELETE USER
# ==========================================================

@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found."
        )

    if user.id == admin.id:
        raise HTTPException(
            status_code=400,
            detail="The admin account cannot be deleted."
        )

    db.delete(user)
    db.commit()

    return {
        "message": "User deleted successfully."
    }


# ==========================================================
# GET ALL PAPERS
# ==========================================================

@router.get("/papers")
def get_admin_papers(
    admin: User = Depends(get_current_admin)
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
            }
        ).sort(
            "uploaded_at",
            -1
        )
    )

    result = []

    for paper in papers:

        result.append({
            "id": str(paper["_id"]),
            "title": paper.get("title", "Untitled Paper"),
            "filename": paper.get("filename", ""),
            "page_count": paper.get("page_count", 0),
            "status": paper.get("status", "uploaded"),
            "uploaded_at": paper.get("uploaded_at"),
            "has_analysis": paper.get("analysis") is not None,
        })

    return result


# ==========================================================
# DELETE PAPER
# ==========================================================

@router.delete("/papers/{paper_id}")
def delete_paper(
    paper_id: str,
    admin: User = Depends(get_current_admin)
):
    paper = papers_collection.find_one({
        "_id": paper_id
    })

    if not paper:
        raise HTTPException(
            status_code=404,
            detail="Paper not found."
        )

    papers_collection.delete_one({
        "_id": paper_id
    })

    return {
        "message": "Paper deleted successfully."
    }