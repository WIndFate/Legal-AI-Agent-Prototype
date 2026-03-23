from fastapi import APIRouter

from backend.eval.evaluator import run_rag_eval

router = APIRouter()


@router.get("/api/eval/rag")
async def eval_rag(k: int = 3):
    """Run RAG retrieval evaluation and return Recall@K and MRR metrics."""
    result = run_rag_eval(k=k)
    return result
