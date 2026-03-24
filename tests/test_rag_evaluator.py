from backend.eval.evaluator import (
    _recall_at_k,
    _reciprocal_rank,
    _run_rag_eval_dataset,
)


class FakeStore:
    def __init__(self, responses):
        self.responses = responses

    def search(self, query: str, n_results: int = 3):
        return self.responses[query][:n_results]


def test_recall_at_k():
    assert _recall_at_k(["law-1", "law-2", "law-3"], ["law-2", "law-9"], 2) == 0.5
    assert _recall_at_k(["law-1"], [], 1) == 0.0


def test_reciprocal_rank():
    assert _reciprocal_rank(["law-4", "law-2", "law-8"], ["law-2"]) == 0.5
    assert _reciprocal_rank(["law-4", "law-8"], ["law-2"]) == 0.0


def test_run_rag_eval_dataset_reports_metrics():
    dataset = [
        {
            "id": "sample-1",
            "description": "first sample",
            "query": "query-1",
            "relevant_ids": ["law-2"],
        },
        {
            "id": "sample-2",
            "description": "second sample",
            "query": "query-2",
            "relevant_ids": ["law-9"],
        },
    ]
    store = FakeStore(
        {
            "query-1": [{"id": "law-2"}, {"id": "law-5"}],
            "query-2": [{"id": "law-3"}, {"id": "law-9"}],
        }
    )

    result = _run_rag_eval_dataset(dataset, store, k=2)

    assert result["k"] == 2
    assert result["num_samples"] == 2
    assert result["mean_recall_at_k"] == 1.0
    assert result["mrr"] == 0.75
    assert result["per_sample"][0]["retrieved_ids"] == ["law-2", "law-5"]
    assert result["per_sample"][1]["reciprocal_rank"] == 0.5
