from __future__ import annotations

from typing import Optional

from backend.api.supabase_admin import get_supabase_admin_client


def get_subscription_status(user_id: str) -> Optional[str]:
    client = get_supabase_admin_client()
    if client is None or not user_id:
        return None
    try:
        res = (
            client.table("user_subscriptions")
            .select("status")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        data = getattr(res, "data", None) or []
        if isinstance(data, list) and data:
            return data[0].get("status")
        if isinstance(data, dict):
            return data.get("status")
        return None
    except Exception:
        return None


def is_pro_user(user_id: str) -> bool:
    status = (get_subscription_status(user_id) or "").lower()
    return status in ["active", "trialing"]
