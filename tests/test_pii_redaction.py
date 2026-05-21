from __future__ import annotations

from backend.shared.pii_redaction import redact_pii_json, redact_pii_text


def test_redact_phone_and_email() -> None:
    raw = "Call me at +919769825350 or email vikas@example.com"
    out = redact_pii_text(raw)
    assert "919769825350" not in (out or "")
    assert "vikas@example.com" not in (out or "")
    assert "[PHONE]" in (out or "")
    assert "[EMAIL]" in (out or "")


def test_redact_card_like() -> None:
    raw = "Card 4111 1111 1111 1111 please"
    out = redact_pii_text(raw)
    assert "4111" not in (out or "")
    assert "[CARD]" in (out or "")


def test_redact_json_nested() -> None:
    payload = {
        "batch_text_preview": "phone 9876543210",
        "nested": {"email": "a@b.co"},
    }
    out = redact_pii_json(payload)
    assert "[PHONE]" in out["batch_text_preview"]
    assert "[EMAIL]" in out["nested"]["email"]
