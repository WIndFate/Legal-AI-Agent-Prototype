from backend.services.pii_detector import detect_pii


def test_detect_phone_number():
    text = "連絡先：090-1234-5678 までご連絡ください"
    results = detect_pii(text)
    types = [r["type"] for r in results]
    assert "phone" in types


def test_detect_email():
    text = "メール: tanaka@example.com に送信してください"
    results = detect_pii(text)
    types = [r["type"] for r in results]
    assert "email" in types


def test_detect_postal_code():
    text = "住所：〒100-0001 東京都千代田区"
    results = detect_pii(text)
    types = [r["type"] for r in results]
    assert "postal_code" in types


def test_detect_mynumber():
    text = "マイナンバー：1234 5678 9012"
    results = detect_pii(text)
    types = [r["type"] for r in results]
    assert "mynumber" in types


def test_detect_address():
    text = "東京都新宿区西新宿2丁目8-1"
    results = detect_pii(text)
    types = [r["type"] for r in results]
    assert "address" in types


def test_no_pii_in_clean_text():
    text = "第1条（目的）本契約は業務委託について定める。"
    results = detect_pii(text)
    assert len(results) == 0


def test_multiple_pii_types():
    text = "氏名：田中太郎 電話：03-1234-5678 メール：tanaka@test.com 〒150-0001"
    results = detect_pii(text)
    types = {r["type"] for r in results}
    assert "phone" in types
    assert "email" in types
    assert "postal_code" in types


def test_result_has_position_info():
    text = "連絡先：090-1234-5678"
    results = detect_pii(text)
    assert len(results) > 0
    for r in results:
        assert "start" in r
        assert "end" in r
        assert "text" in r
        assert "type" in r
        assert r["start"] < r["end"]
