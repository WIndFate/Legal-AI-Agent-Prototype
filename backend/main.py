import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from backend.agent.graph import run_review
from backend.rag.loader import load_legal_knowledge

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading legal knowledge into RAG store...")
    try:
        count = load_legal_knowledge()
        logger.info(f"Loaded {count} legal knowledge documents.")
    except Exception as e:
        logger.warning(f"Failed to load legal knowledge (will retry on first request): {e}")
    yield


app = FastAPI(
    title="Legal Contract Review Agent",
    description="AI-powered Japanese legal contract review agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReviewRequest(BaseModel):
    contract_text: str


class ReviewResponse(BaseModel):
    overall_risk_level: str
    summary: str
    clause_analyses: list[dict]
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    total_clauses: int


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.post("/api/review", response_model=ReviewResponse)
async def review_contract(request: ReviewRequest):
    report = await run_review(request.contract_text)
    return report
