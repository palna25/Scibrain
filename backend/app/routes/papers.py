import os
import uuid

import fitz

from fastapi import APIRouter, UploadFile, File, HTTPException
from datetime import datetime, timezone
from bson import ObjectId

from app.database.mongodb import papers_collection
from app.services.analysis import analyze_paper
from app.services.vector_store import index_paper_chunks

router = APIRouter(
    prefix="/api/papers",
    tags=["Papers"]
)


UPLOAD_DIR = "uploads/papers"

os.makedirs(UPLOAD_DIR, exist_ok=True)


# ==========================================================
# UPLOAD PAPER
# ==========================================================

@router.post("/upload")
async def upload_paper(file: UploadFile = File(...)):

    # Validate file
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file selected."
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported."
        )

    # Generate unique ID
    paper_id = str(uuid.uuid4())

    safe_filename = f"{paper_id}.pdf"

    file_path = os.path.join(
        UPLOAD_DIR,
        safe_filename
    )

    # ------------------------------------------------------
    # Save PDF
    # ------------------------------------------------------

    try:
        contents = await file.read()

        with open(file_path, "wb") as buffer:
            buffer.write(contents)

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to save PDF: {str(error)}"
        )

    # ------------------------------------------------------
    # Extract text
    # ------------------------------------------------------

    try:

        document = fitz.open(file_path)

        extracted_text = ""

        for page in document:
            extracted_text += page.get_text()

        page_count = len(document)

        document.close()

    except Exception as error:

        if os.path.exists(file_path):
            os.remove(file_path)

        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract PDF text: {str(error)}"
        )

    # ------------------------------------------------------
    # Create MongoDB document
    # ------------------------------------------------------

    paper_document = {
        "_id": paper_id,

        "title": os.path.splitext(file.filename)[0],

        "filename": file.filename,

        "stored_filename": safe_filename,

        "file_path": file_path,

        "page_count": page_count,

        "text": extracted_text,

        "text_length": len(extracted_text),

        "status": "uploaded",

        "processing_error": None,

        "analysis": None,

        "uploaded_at": datetime.now(timezone.utc),
    }

    # ------------------------------------------------------
    # Save to MongoDB
    # ------------------------------------------------------

    try:

        papers_collection.insert_one(
            paper_document
        )

        # Index vectors into Qdrant
        try:
            index_paper_chunks(
                paper_id=paper_id,
                title=paper_document["title"],
                text=extracted_text,
            )
        except Exception as vec_err:
            print(f"Warning: Vector indexing for paper {paper_id} encountered: {vec_err}")

    except Exception as error:

        if os.path.exists(file_path):
            os.remove(file_path)

        raise HTTPException(
            status_code=500,
            detail=f"Failed to save paper to MongoDB: {str(error)}"
        )

    return {
        "id": paper_id,
        "title": paper_document["title"],
        "filename": file.filename,
        "page_count": page_count,
        "text_length": len(extracted_text),
        "status": "uploaded",
        "message": "Paper uploaded and processed successfully."
    }


# ==========================================================
# GET ALL PAPERS
# ==========================================================

@router.get("/")
async def get_papers():

    try:

        papers = list(
            papers_collection.find(
                {},
                {
                    "_id": 1,
                    "title": 1,
                    "filename": 1,
                    "page_count": 1,
                    "text_length": 1,
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

            paper_id = paper.get("_id")

            if isinstance(paper_id, ObjectId):
                paper_id = str(paper_id)

            result.append({

                "id": paper_id,

                "title": paper.get(
                    "title",
                    "Untitled Paper"
                ),

                "filename": paper.get(
                    "filename",
                    ""
                ),

                "page_count": paper.get(
                    "page_count",
                    0
                ),

                "text_length": paper.get(
                    "text_length",
                    0
                ),

                "status": paper.get(
                    "status",
                    "uploaded"
                ),

                "uploaded_at": paper.get(
                    "uploaded_at"
                ),

                "analysis": paper.get(
                    "analysis"
                ),
            })

        return result

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch papers: {str(error)}"
        )

# ==========================================================
# GET PAPER STATISTICS
# ==========================================================

@router.get("/stats")
async def get_paper_stats():

    try:

        total_papers = papers_collection.count_documents({})

        analyzed_papers = papers_collection.count_documents({
            "status": "analyzed"
        })

        papers = list(
            papers_collection.find(
                {
                    "status": "analyzed",
                    "analysis": {"$ne": None}
                },
                {
                    "analysis": 1
                }
            )
        )

        # --------------------------------------------------
        # Extract concepts
        # --------------------------------------------------

        concepts = set()

        potential_gaps = 0

        for paper in papers:

            analysis = paper.get("analysis") or {}

            # Datasets
            for dataset in analysis.get("datasets", []):
                if dataset:
                    concepts.add(
                        f"dataset:{dataset.strip().lower()}"
                    )

            # Metrics
            for metric in analysis.get("metrics", []):
                if metric:
                    concepts.add(
                        f"metric:{metric.strip().lower()}"
                    )

            # Methodology statements
            for method in analysis.get("methodology", []):
                if method:
                    concepts.add(
                        f"method:{method.strip().lower()}"
                    )

            # --------------------------------------------------
            # Potential research gaps
            #
            # Currently derived from limitations + future work.
            # This is NOT an LLM-generated gap detector yet.
            # --------------------------------------------------

            potential_gaps += len(
                analysis.get("limitations", [])
            )

            potential_gaps += len(
                analysis.get("future_work", [])
            )

        return {
            "total_papers": total_papers,
            "analyzed_papers": analyzed_papers,
            "knowledge_nodes": len(concepts),
            "contradictions": 0,
            "research_gaps": potential_gaps,
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate paper statistics: {str(error)}"
        )
# ==========================================================
# GET SINGLE PAPER
# ==========================================================

@router.get("/{paper_id}")
async def get_paper(paper_id: str):

    paper = papers_collection.find_one(
        {
            "_id": paper_id
        }
    )

    if not paper:

        raise HTTPException(
            status_code=404,
            detail="Paper not found."
        )

    return {

        "id": str(
            paper["_id"]
        ),

        "title": paper.get(
            "title",
            ""
        ),

        "filename": paper.get(
            "filename",
            ""
        ),

        "page_count": paper.get(
            "page_count",
            0
        ),

        "text": paper.get(
            "text",
            ""
        ),

        "text_length": paper.get(
            "text_length",
            0
        ),

        "status": paper.get(
            "status",
            "uploaded"
        ),

        "processing_error": paper.get(
            "processing_error"
        ),

        "analysis": paper.get(
            "analysis"
        ),

        "uploaded_at": paper.get(
            "uploaded_at"
        ),
    }


# ==========================================================
# ANALYZE PAPER
# ==========================================================

@router.post("/{paper_id}/analyze")
async def analyze_paper_route(paper_id: str):

    paper = papers_collection.find_one({
        "_id": paper_id
    })

    if not paper:
        raise HTTPException(
            status_code=404,
            detail="Paper not found."
        )

    extracted_text = paper.get("text", "")

    if not extracted_text.strip():
        raise HTTPException(
            status_code=400,
            detail="No extracted text is available for analysis."
        )

    papers_collection.update_one(
        {"_id": paper_id},
        {
            "$set": {
                "status": "processing",
                "processing_error": None,
            }
        }
    )

    try:

        analysis = analyze_paper(paper_id)

        return {
            "id": paper_id,
            "status": "analyzed",
            "message": "Paper analysis completed successfully.",
            "analysis": analysis,
        }

    except Exception as error:

        papers_collection.update_one(
            {"_id": paper_id},
            {
                "$set": {
                    "status": "error",
                    "processing_error": str(error),
                }
            }
        )

        raise HTTPException(
            status_code=500,
            detail=f"Paper analysis failed: {str(error)}"
        )