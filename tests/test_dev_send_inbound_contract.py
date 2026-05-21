from __future__ import annotations

from backend.apps.wa_gateway.meta_payload import extract_inbound_messages
from backend.tools.dev_send_inbound import build_meta_inbound_webhook_payload


def test_dev_payload_roundtrips_through_meta_extract() -> None:
    """Same JSON the CLI posts must parse identically to production webhooks."""
    payload = build_meta_inbound_webhook_payload(
        meta_phone_number_id="111222333",
        from_phone="+919999999999",
        text_body="pytest contract",
        msg_id="wamid.TEST.FIXED",
        timestamp=1700000001,
    )
    msgs = extract_inbound_messages(payload)
    assert len(msgs) == 1
    m = msgs[0]
    assert m.meta_msg_id == "wamid.TEST.FIXED"
    assert m.from_phone == "+919999999999"
    assert m.to_phone_number_id == "111222333"
    assert m.timestamp == 1700000001
    assert m.text == "pytest contract"
    assert m.text_like is True


def test_dev_payload_can_build_image_message() -> None:
    payload = build_meta_inbound_webhook_payload(
        meta_phone_number_id="111222333",
        from_phone="+919999999999",
        text_body="photo caption",
        message_type="image",
        msg_id="wamid.TEST.IMAGE",
        timestamp=1700000002,
    )
    msgs = extract_inbound_messages(payload)
    assert len(msgs) == 1
    assert msgs[0].text == "[image]"
    assert msgs[0].text_like is False
    assert msgs[0].media_metadata["caption"] == "photo caption"
