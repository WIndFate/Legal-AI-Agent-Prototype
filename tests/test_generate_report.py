from backend.agent import nodes


def test_generate_report_in_japanese_without_translation(monkeypatch):
    called = {"translate": False}

    def fake_translate(*args, **kwargs):
        called["translate"] = True
        raise AssertionError("_translate_report should not be called for ja output")

    monkeypatch.setattr(nodes, "_translate_report", fake_translate)

    state = {
        "risk_analysis": [
            {
                "clause_number": "第1条",
                "risk_level": "高",
                "risk_reason": "高リスク理由",
                "suggestion": "修正案",
                "referenced_law": "民法",
            },
            {
                "clause_number": "第2条",
                "risk_level": "低",
                "risk_reason": "低リスク理由",
                "suggestion": "",
                "referenced_law": "労働基準法",
            },
        ],
        "target_language": "ja",
    }

    result = nodes.generate_report(state)
    report = result["review_report"]

    assert called["translate"] is False
    assert report["overall_risk_level"] == "高"
    assert report["high_risk_count"] == 1
    assert report["low_risk_count"] == 1
    assert report["total_clauses"] == 2
    assert "契約書の審査が完了しました" in report["summary"]


def test_generate_report_uses_translation_for_non_japanese(monkeypatch):
    def fake_translate(summary, risk_analysis, overall_risk, target_lang):
        assert target_lang == "zh-CN"
        assert overall_risk == "中"
        return (
            "合同审查已完成。",
            [
                {
                    "clause_number": "第1条",
                    "risk_level": "中风险",
                    "risk_reason": "存在一定风险",
                    "suggestion": "建议补充说明",
                    "referenced_law": "民法",
                }
            ],
            "中风险",
        )

    monkeypatch.setattr(nodes, "_translate_report", fake_translate)

    state = {
        "risk_analysis": [
            {
                "clause_number": "第1条",
                "risk_level": "中",
                "risk_reason": "日本語の理由",
                "suggestion": "日本語の修正案",
                "referenced_law": "民法",
            }
        ],
        "target_language": "zh-CN",
    }

    result = nodes.generate_report(state)
    report = result["review_report"]

    assert report["overall_risk_level"] == "中风险"
    assert report["summary"] == "合同审查已完成。"
    assert report["clause_analyses"][0]["risk_level"] == "中风险"
    assert report["medium_risk_count"] == 1
    assert report["total_clauses"] == 1
