import os
import json
import requests
import azure.functions as func

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_PUBLISHABLE_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

class AuthError(Exception):
    def __init__(self, message, status_code=401):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def require_user(req: func.HttpRequest) -> dict:
    token = req.headers.get("x-supabase-token", "")
    if not token:
        raise AuthError("Missing X-Supabase-Token header", 401)

    if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY:
        raise AuthError("Supabase configuration missing", 500)

    r = requests.get(
        f"{SUPABASE_URL}/auth/v1/user",
        headers={
            "Authorization": f"Bearer {token}",
            "apikey": SUPABASE_PUBLISHABLE_KEY,
        },
        timeout=10,
    )

    if r.status_code != 200:
        raise AuthError("Invalid or expired session", 401)

    user = r.json()
    return {
        "user_id": user.get("id"),
        "email": user.get("email"),
        "supabase_role": user.get("role"),
    }
