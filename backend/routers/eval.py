from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.eval.evaluator import run_rag_eval
from backend.services.cost_analysis import (
    build_cost_pricing_report,
    load_cost_samples,
    summarize_sample_sources,
)

router = APIRouter()


@router.get("/api/eval/rag")
async def eval_rag(k: int = 3):
    """Run RAG retrieval evaluation and return Recall@K and MRR metrics."""
    result = run_rag_eval(k=k)
    return result


@router.get("/api/eval/costs")
async def eval_costs(
    limit: int = 200,
    payment_fee_rate: float = 0.0325,
    fixed_buffer_jpy: float = 30.0,
    safety_multiplier: float = 2.5,
    db: AsyncSession = Depends(get_db),
):
    """Summarize persisted order costs and return pricing recommendations."""
    samples = await load_cost_samples(db, limit=limit)
    return {
        "sample_limit": limit,
        "samples": len(samples),
        "sample_sources": summarize_sample_sources(samples),
        "report": build_cost_pricing_report(
            samples,
            payment_fee_rate=payment_fee_rate,
            fixed_buffer_jpy=fixed_buffer_jpy,
            safety_multiplier=safety_multiplier,
        ),
    }
