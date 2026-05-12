from __future__ import annotations

import hashlib
import hmac
import json

from backend.apps.billing_api.verify_signatures import (
    paddle_event_id,
    paddle_event_type,
    razorpay_event_id,
    razorpay_event_name,
    verify_paddle_signature,
    verify_razorpay_signature,
)


def test_verify_razorpay_signature_accepts_valid_hex() -> None:
    secret = "whsec_test_razorpay"
    body = b'{"entity":"event","id":"evt_1","event":"subscription.activated"}'
    sig = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256).hexdigest()
    assert verify_razorpay_signature(body, sig, secret) is True
    assert verify_razorpay_signature(body, sig.upper(), secret) is True
    assert verify_razorpay_signature(body, "deadbeef", secret) is False


def test_verify_razorpay_rejects_missing_header_or_secret() -> None:
    body = b"{}"
    assert verify_razorpay_signature(body, None, "secret") is False
    assert verify_razorpay_signature(body, "abc", "") is False


def test_verify_paddle_signature_accepts_ts_h1_format() -> None:
    secret = "pdl_ntfset_testsecret"
    body = b'{"event_id":"evt_pdl_1","event_type":"subscription.updated","data":{"id":"sub_1"}}'
    ts = "1700000000"
    signed = f"{ts}:".encode("utf-8") + body
    h1 = hmac.new(secret.encode("utf-8"), msg=signed, digestmod=hashlib.sha256).hexdigest()
    header = f"ts={ts};h1={h1}"
    assert verify_paddle_signature(body, header, secret) is True
    assert verify_paddle_signature(body, "ts=1", secret) is False


def test_razorpay_event_id_and_name() -> None:
    p = json.loads(
        '{"entity":"event","id":"evt_abc","event":"subscription.charged","payload":{}}'
    )
    assert razorpay_event_id(p) == "evt_abc"
    assert razorpay_event_name(p) == "subscription.charged"


def test_paddle_event_id_and_type() -> None:
    p = json.loads(
        '{"event_id":"evt_xyz","event_type":"subscription.canceled","data":{"id":"sub_1"}}'
    )
    assert paddle_event_id(p) == "evt_xyz"
    assert paddle_event_type(p) == "subscription.canceled"
