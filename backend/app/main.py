from fastapi import FastAPI
from sqlalchemy import text

from app.database.postgres import engine
from app.routes.auth import router as auth_router
from fastapi.middleware.cors import CORSMiddleware
from app.routes import papers, admin, notebook, knowledge_graph, research_gaps
from app.routes import gemini_test
from app.routes.sources import router as sources_router
app = FastAPI(
    title="SciBrain API",
    description="Backend API for SciBrain Research Intelligence Platform",
    version="1.0.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(papers.router)
app.include_router(admin.router)
app.include_router(notebook.router)
app.include_router(knowledge_graph.router)
app.include_router(research_gaps.router)
app.include_router(gemini_test.router)
app.include_router(sources_router)

@app.get("/")
def root():
    return {
        "message": "SciBrain API is running"
    }


@app.get("/api/health/db")
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "success",
            "database": "PostgreSQL connected"
        }

    except Exception as e:
        return {
            "status": "error",
            "database": "PostgreSQL connection failed",
            "detail": str(e)
        }
        
