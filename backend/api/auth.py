from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Set, Any, Dict

from fastapi import Header, HTTPException, status, Request

from backend.api.subscriptions import is_pro_user
from backend.api.supabase_admin import get_supabase_admin_client


@dataclass(frozen=True)
class Principal:
    scheme: str
    subject: str
    claims: Optional[Dict[str, Any]] = None
    is_pro: bool = False


def _parse_api_keys(raw: str) -> Set[str]:
    keys = set()
    for part in (raw or "").split(","):
        k = part.strip()
        if k:
            keys.add(k)
    return keys


def get_configured_api_keys() -> Set[str]:
    """Return configured API keys (empty means auth disabled).

    This is intentionally simple so it can be replaced with JWT validation later.
    """
    return _parse_api_keys(os.getenv("API_KEYS", ""))


def get_principal(api_key: str) -> Principal:
    """Map an authenticated credential to a principal.

    Future JWT migration: replace this with token decode + claims mapping.
    """
    return Principal(scheme="api_key", subject=api_key)


def _parse_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2:
        return None
    if parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def _get_supabase_claims(token: str) -> Optional[Dict[str, Any]]:
    client = get_supabase_admin_client()
    if client is None:
        return None
    try:
        get_claims = getattr(client.auth, "get_claims", None)
        if callable(get_claims):
            claims = get_claims(token)
            if isinstance(claims, dict):
                return claims
    except Exception:
        pass
    try:
        res = client.auth.get_user(token)
        user = getattr(res, "user", None)
        if user is None and isinstance(res, dict):
            user = res.get("user")
        if user and getattr(user, "id", None):
            return {"sub": user.id, "email": getattr(user, "email", None)}
    except Exception:
        return None
    return None


def get_principal_from_request(
    request: Request,
    authorization: Optional[str] = None,
    x_api_key: Optional[str] = None,
) -> Principal:
    token = _parse_bearer_token(authorization)
    if not token:
        token = request.query_params.get("access_token")
    if token:
        claims = _get_supabase_claims(token)
        if claims:
            subject = str(claims.get("sub") or claims.get("user_id") or "")
            if subject:
                return Principal(scheme="supabase", subject=subject, claims=claims, is_pro=is_pro_user(subject))
    keys = get_configured_api_keys()
    if x_api_key and x_api_key in keys:
        return get_principal(x_api_key)
    return Principal(scheme="none", subject="anonymous")


def require_user(
    request: Request,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> Principal:
    principal = get_principal_from_request(request, authorization=authorization, x_api_key=x_api_key)

    enable_auth_guard = os.getenv("ENABLE_AUTH_GUARD", "0") == "1"
    enable_pro_guard = os.getenv("ENABLE_PRO_GUARD", "0") == "1"

    if enable_auth_guard and principal.scheme != "supabase":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    if enable_pro_guard:
        if principal.scheme != "supabase":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        if not principal.is_pro:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Pro subscription required",
            )

    return principal


def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> Principal:
    """FastAPI dependency: validates X-API-Key against API_KEYS.

    - If API_KEYS is empty/unset: no-op (keeps local dev/tests unchanged).
    - If API_KEYS is set: missing/invalid key returns 401.
    """
    keys = get_configured_api_keys()
    # Security guardrail: if LLM is enabled, require API_KEYS to be configured.
    if not keys:
        if (os.getenv("USE_LLM", "0") or "0") == "1":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API_KEYS must be set when USE_LLM=1",
            )
        return Principal(scheme="none", subject="anonymous")

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key",
        )

    if x_api_key not in keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-API-Key",
        )

    return get_principal(x_api_key)
