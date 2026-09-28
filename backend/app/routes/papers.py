""" import os
import uuid

import fitz

from fastapi import APIRouter, UploadFile, File, HTTPException
from datetime import datetime, timezone
from bson import ObjectId

from app.database.mongodb import papers_collection
from app.services.analysis import analyze_paper

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
        ) """
        
import os
import uuid

import fitz

from fastapi import APIRouter, UploadFile, File, HTTPException
from datetime import datetime, timezone
from bson import ObjectId

from app.database.mongodb import papers_collection
from app.services.vector_store import index_paper_chunks, delete_paper_chunks


router = APIRouter(
    prefix="/api/papers",
    tags=["Papers"],
)


UPLOAD_DIR = "uploads/papers"

os.makedirs(UPLOAD_DIR, exist_ok=True)


# ==========================================================
# UPLOAD PAPER
# ==========================================================

@router.post("/upload")
async def upload_paper(file: UploadFile = File(...)):

    # ------------------------------------------------------
    # Validate file
    # ------------------------------------------------------

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file selected.",
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported.",
        )

    # ------------------------------------------------------
    # Generate unique resource ID
    # ------------------------------------------------------

    paper_id = str(uuid.uuid4())

    safe_filename = f"{paper_id}.pdf"

    file_path = os.path.join(
        UPLOAD_DIR,
        safe_filename,
    )

    # ------------------------------------------------------
    # Save PDF
    # ------------------------------------------------------

    try:

        contents = await file.read()

        if not contents:
            raise HTTPException(
                status_code=400,
                detail="The uploaded PDF is empty.",
            )

        with open(file_path, "wb") as buffer:
            buffer.write(contents)

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to save PDF: {str(error)}",
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
            detail=f"Failed to extract PDF text: {str(error)}",
        )

    # ------------------------------------------------------
    # Validate extracted text
    # ------------------------------------------------------

    if not extracted_text.strip():

        if os.path.exists(file_path):
            os.remove(file_path)

        raise HTTPException(
            status_code=400,
            detail=(
                "No readable text could be extracted from this PDF. "
                "Scanned/image-only PDFs are not supported yet."
            ),
        )

    # ------------------------------------------------------
    # Create MongoDB resource document
    # ------------------------------------------------------

    paper_title = os.path.splitext(
        file.filename
    )[0]

    paper_document = {
        "_id": paper_id,

        "title": paper_title,

        "filename": file.filename,

        "stored_filename": safe_filename,

        "file_path": file_path,

        "page_count": page_count,

        "text": extracted_text,

        "text_length": len(extracted_text),

        # uploaded -> processing -> ready
        "status": "processing",

        "processing_error": None,

        "uploaded_at": datetime.now(timezone.utc),
    }

    # ------------------------------------------------------
    # Save resource to MongoDB
    # ------------------------------------------------------

    try:

        papers_collection.insert_one(
            paper_document
        )

    except Exception as error:

        if os.path.exists(file_path):
            os.remove(file_path)

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to save paper to MongoDB: "
                f"{str(error)}"
            ),
        )

    # ------------------------------------------------------
    # Create chunks + embeddings + Qdrant index
    # ------------------------------------------------------

    try:

        indexed_chunks = index_paper_chunks(
            paper_id=paper_id,
            title=paper_title,
            text=extracted_text,
        )

        if indexed_chunks == 0:

            papers_collection.update_one(
                {"_id": paper_id},
                {
                    "$set": {
                        "status": "error",
                        "processing_error": (
                            "No searchable chunks were created "
                            "from the extracted text."
                        ),
                    }
                },
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "Paper text was extracted, but no searchable "
                    "chunks could be created."
                ),
            )

        # --------------------------------------------------
        # Resource is now ready for Notebook / Graph / Gaps
        # --------------------------------------------------

        papers_collection.update_one(
            {"_id": paper_id},
            {
                "$set": {
                    "status": "ready",
                    "processing_error": None,
                    "indexed_chunks": indexed_chunks,
                }
            },
        )

    except HTTPException:
        raise

    except Exception as error:

        papers_collection.update_one(
            {"_id": paper_id},
            {
                "$set": {
                    "status": "error",
                    "processing_error": str(error),
                }
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Paper was saved, but vector indexing failed: "
                f"{str(error)}"
            ),
        )

    # ------------------------------------------------------
    # Response
    # ------------------------------------------------------

    return {
        "id": paper_id,
        "title": paper_title,
        "filename": file.filename,
        "page_count": page_count,
        "text_length": len(extracted_text),
        "indexed_chunks": indexed_chunks,
        "status": "ready",
        "message": (
            "Paper uploaded, indexed, and is ready "
            "for research."
        ),
    }


# ==========================================================
# GET ALL PAPERS / RESEARCH RESOURCES
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
                    "indexed_chunks": 1,
                    "status": 1,
                    "processing_error": 1,
                    "uploaded_at": 1,
                },
            ).sort(
                "uploaded_at",
                -1,
            )
        )

        result = []

        for paper in papers:

            paper_id = paper.get("_id")

            if isinstance(paper_id, ObjectId):
                paper_id = str(paper_id)

            result.append(
                {
                    "id": paper_id,

                    "title": paper.get(
                        "title",
                        "Untitled Paper",
                    ),

                    "filename": paper.get(
                        "filename",
                        "",
                    ),

                    "page_count": paper.get(
                        "page_count",
                        0,
                    ),

                    "text_length": paper.get(
                        "text_length",
                        0,
                    ),

                    "indexed_chunks": paper.get(
                        "indexed_chunks",
                        0,
                    ),

                    "status": paper.get(
                        "status",
                        "uploaded",
                    ),

                    "processing_error": paper.get(
                        "processing_error",
                    ),

                    "uploaded_at": paper.get(
                        "uploaded_at",
                    ),
                }
            )

        return result

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to fetch papers: {str(error)}"
            ),
        )


# ==========================================================
# GET PAPER STATISTICS
# ==========================================================

@router.get("/stats")
async def get_paper_stats():

    try:

        total_papers = papers_collection.count_documents({})

        ready_papers = papers_collection.count_documents(
            {
                "status": "ready",
            }
        )

        processing_papers = papers_collection.count_documents(
            {
                "status": "processing",
            }
        )

        error_papers = papers_collection.count_documents(
            {
                "status": "error",
            }
        )

        chunk_result = list(
            papers_collection.aggregate(
                [
                    {
                        "$group": {
                            "_id": None,
                            "total_chunks": {
                                "$sum": {
                                    "$ifNull": [
                                        "$indexed_chunks",
                                        0,
                                    ]
                                }
                            },
                        }
                    }
                ]
            )
        )

        total_chunks = (
            chunk_result[0]["total_chunks"]
            if chunk_result
            else 0
        )

        return {
            "total_papers": total_papers,
            "ready_papers": ready_papers,
            "processing_papers": processing_papers,
            "error_papers": error_papers,
            "total_chunks": total_chunks,
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to calculate paper statistics: "
                f"{str(error)}"
            ),
        )


# ==========================================================
# GET SINGLE PAPER
# ==========================================================

@router.get("/{paper_id}")
async def get_paper(paper_id: str):

    paper = papers_collection.find_one(
        {
            "_id": paper_id,
        }
    )

    if not paper:

        raise HTTPException(
            status_code=404,
            detail="Paper not found.",
        )

    return {
        "id": str(
            paper["_id"]
        ),

        "title": paper.get(
            "title",
            "",
        ),

        "filename": paper.get(
            "filename",
            "",
        ),

        "page_count": paper.get(
            "page_count",
            0,
        ),

        "text": paper.get(
            "text",
            "",
        ),

        "text_length": paper.get(
            "text_length",
            0,
        ),

        "indexed_chunks": paper.get(
            "indexed_chunks",
            0,
        ),

        "status": paper.get(
            "status",
            "uploaded",
        ),

        "processing_error": paper.get(
            "processing_error",
        ),

        "uploaded_at": paper.get(
            "uploaded_at",
        ),
    }
    # ==========================================================
# DELETE PAPER
# ==========================================================

@router.delete("/{paper_id}")
async def delete_paper(paper_id: str):

    # ------------------------------------------------------
    # Find the paper
    # ------------------------------------------------------

    paper = papers_collection.find_one(
        {
            "_id": paper_id,
        }
    )

    if not paper:

        raise HTTPException(
            status_code=404,
            detail="Paper not found.",
        )

    # ------------------------------------------------------
    # Delete Qdrant chunks
    # ------------------------------------------------------

    try:

        delete_paper_chunks(
            paper_id=paper_id,
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to remove the paper's "
                f"indexed data from Qdrant: {str(error)}"
            ),
        )

    # ------------------------------------------------------
    # Delete stored PDF
    # ------------------------------------------------------

    file_path = paper.get(
        "file_path"
    )

    if file_path and os.path.exists(file_path):

        try:

            os.remove(file_path)

        except Exception as error:

            raise HTTPException(
                status_code=500,
                detail=(
                    "Paper vectors were removed, but "
                    "the stored PDF could not be deleted: "
                    f"{str(error)}"
                ),
            )

    # ------------------------------------------------------
    # Delete MongoDB document
    # ------------------------------------------------------

    try:

        delete_result = papers_collection.delete_one(
            {
                "_id": paper_id,
            }
        )

        if delete_result.deleted_count == 0:

            raise HTTPException(
                status_code=500,
                detail=(
                    "Paper could not be deleted "
                    "from MongoDB."
                ),
            )

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to delete paper from MongoDB: "
                f"{str(error)}"
            ),
        )

    # ------------------------------------------------------
    # Response
    # ------------------------------------------------------

    return {
        "id": paper_id,
        "message": "Paper deleted successfully.",
    }