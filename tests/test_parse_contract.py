from types import SimpleNamespace

import pytest

from backend.agent import nodes


class _FakeLLM:
    def __init__(self, response: str):
        self.response = response

    def invoke(self, _messages):
        return SimpleNamespace(content=self.response)


def test_parse_contract_extracts_clauses_from_contract_payload(monkeypatch):
    monkeypatch.setattr(nodes, "log_model_usage", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        nodes,
        "parse_llm",
        _FakeLLM(
            '{"is_contract": true, "rejection_reason": "", "clauses": '
            '[{"number": "第1条", "title": "目的", "text": "本契約の目的を定める。"}]}'
        ),
    )

    result = nodes.parse_contract({"contract_text": "第1条（目的）本契約の目的を定める。"})

    assert result["clauses"] == [{"number": "第1条", "title": "目的", "text": "本契約の目的を定める。"}]


def test_parse_contract_raises_for_non_contract_document(monkeypatch):
    monkeypatch.setattr(nodes, "log_model_usage", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        nodes,
        "parse_llm",
        _FakeLLM(
            '{"is_contract": false, "rejection_reason": "単なる案内文です", "clauses": []}'
        ),
    )

    with pytest.raises(nodes.NonContractDocumentError) as exc_info:
        nodes.parse_contract({"contract_text": "営業時間変更のお知らせ"})

    assert "案内文" in str(exc_info.value)
