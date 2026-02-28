from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client


def _import_create_client():
    try:
        from supabase import create_client
    except Exception:
        return None
    return create_client


@lru_cache(maxsize=1)
def get_supabase_admin_client() -> Optional["Client"]:
    url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not service_role_key:
        return None
    create_client = _import_create_client()
    if create_client is None:
        return None
    return create_client(url, service_role_key)
