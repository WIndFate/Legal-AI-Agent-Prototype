from types import SimpleNamespace

from backend.agent import nodes


class _FakeTool:
    def __init__(self, func):
        self._func = func

    def invoke(self, args):
        return self._func(args)


class _FakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)

    def invoke(self, _messages):
        if not self._responses:
            raise AssertionError("Unexpected extra LLM invocation")
        return SimpleNamespace(content=self._responses.pop(0))


def test_analyze_risks_only_generates_suggestions_for_medium_or_high(monkeypatch):
    suggestion_calls = []

    monkeypatch.setattr(nodes, "log_model_usage", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        nodes,
        "analysis_llm",
        _FakeLLM([
            '{"clause_number":"第1条","risk_level":"低","risk_reason":"大きな問題はありません","referenced_law":"民法第1条"}',
            '{"clause_number":"第2条","risk_level":"中","risk_reason":"解除条件が一方的です","referenced_law":"民法第548条の2"}',
        ]),
    )
    monkeypatch.setattr(
        nodes,
        "analyze_clause_risk",
        _FakeTool(lambda args: f"根拠:{args['clause_text'][:8]}"),
    )
    monkeypatch.setattr(
        nodes,
        "generate_suggestion",
        _FakeTool(lambda args: suggestion_calls.append(args) or "修正案テキスト"),
    )

    state = {
        "clauses": [
            {"number": "第1条", "title": "目的", "text": "本契約の目的を定める。"},
            {"number": "第2条", "title": "解除", "text": "甲はいつでも解除できる。"},
        ]
    }

    result = nodes.analyze_risks(state)

    assert len(result["risk_analysis"]) == 2
    assert result["risk_analysis"][0]["risk_level"] == "低"
    assert result["risk_analysis"][0]["suggestion"] == ""
    assert result["risk_analysis"][1]["risk_level"] == "中"
    assert result["risk_analysis"][1]["suggestion"] == "修正案テキスト"
    assert len(suggestion_calls) == 1
    assert suggestion_calls[0]["clause_text"] == "甲はいつでも解除できる。"


def test_analyze_risks_falls_back_when_clause_json_is_invalid(monkeypatch):
    monkeypatch.setattr(nodes, "log_model_usage", lambda *args, **kwargs: None)
    monkeypatch.setattr(nodes, "analysis_llm", _FakeLLM(["not-json"]))
    monkeypatch.setattr(
        nodes,
        "analyze_clause_risk",
        _FakeTool(lambda args: f"根拠:{args['clause_text'][:8]}"),
    )
    monkeypatch.setattr(
        nodes,
        "generate_suggestion",
        _FakeTool(lambda args: "should-not-run"),
    )

    state = {
        "clauses": [
            {"number": "第9条", "title": "雑則", "text": "その他必要事項は別途協議する。"},
        ]
    }

    result = nodes.analyze_risks(state)
    analysis = result["risk_analysis"][0]

    assert analysis["clause_number"] == "第9条"
    assert analysis["risk_level"] == "不明"
    assert analysis["suggestion"] == ""
