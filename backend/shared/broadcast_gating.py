"""M6 broadcast gating: entitlement matrix, marketing opt-in, template-only body JSON."""

from __future__ import annotations

import json
from typing import Any

M6_POLICY_KEY = "m6.broadcast_policy"

DEFAULT_M6_POLICY: dict[str, Any] = {
    "blocked_entitlement_plans": ["trial", "starter"],
    "require_marketing_opt_in": True,
    "template_only": True,
}


def merge_m6_policy(value_json: Any | None) -> dict[str, Any]:
    """Load ``m6.broadcast_policy`` from ``ops_runtime_config.value_json`` with safe defaults."""
    merged = dict(DEFAULT_M6_POLICY)
    if isinstance(value_json, dict):
        for k, v in value_json.items():
            merged[k] = v
    return merged


def plan_allows_broadcast(entitlement_plan: str | None, policy: dict[str, Any]) -> bool:
    raw = policy.get("blocked_entitlement_plans") or []
    blocked = {str(x).strip().lower() for x in raw if str(x).strip()}
    ent = (entitlement_plan or "").strip().lower()
    if not ent:
        return False
    return ent not in blocked


def build_template_outbox_body(
    *,
    template_name: str,
    language: str,
    components: list[dict[str, Any]] | None = None,
) -> str:
    """JSON body for ``wa_outbox.kind = 'TEMPLATE'`` (see ``outbox_sender`` Meta template send)."""
    payload = {
        "template_name": str(template_name).strip(),
        "language": str(language or "en_US").strip(),
        "components": components or [],
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def validate_template_only_body(body_text: str, *, template_only: bool = True) -> tuple[bool, str]:
    """
    Enforce template-only payloads: strict JSON with ``template_name`` + ``language`` keys.
    Free-text bodies are rejected (no silent plain-text marketing sends).
    """
    if not template_only:
        return True, ""
    try:
        data = json.loads(body_text)
    except json.JSONDecodeError as e:
        return False, f"template_only: invalid JSON ({e})"
    if not isinstance(data, dict):
        return False, "template_only: body must be a JSON object"
    name = data.get("template_name")
    lang = data.get("language")
    if not isinstance(name, str) or not name.strip():
        return False, "template_only: missing non-empty template_name"
    if not isinstance(lang, str) or not lang.strip():
        return False, "template_only: missing non-empty language"
    comps = data.get("components", [])
    if comps is not None and not isinstance(comps, list):
        return False, "template_only: components must be an array when present"
    extra = set(data.keys()) - {"template_name", "language", "components"}
    if extra:
        return False, f"template_only: unexpected keys {sorted(extra)}"
    return True, ""
