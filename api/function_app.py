import os
import json
import logging
import requests
import azure.functions as func

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_PUBLISHABLE_KEY = os.environ.get("SUPABASE_ANON_KEY", "")  # publishable/anon key

app = func.FunctionApp()

@app.route(route="hello", auth_level=func.AuthLevel.ANONYMOUS)
def hello(req: func.HttpRequest) -> func.HttpResponse:
    # Read Supabase session token from custom header (SWA overwrites Authorization)
    token = req.headers.get("x-supabase-token", "")
    if not token:
        return func.HttpResponse(
            json.dumps({"ok": False, "error": "Missing X-Supabase-Token header"}, indent=2),
            status_code=401,
            mimetype="application/json",
        )

    if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY:
        return func.HttpResponse(
            json.dumps({"ok": False, "error": "Missing SUPABASE_URL or SUPABASE_ANON_KEY app setting"}, indent=2),
            status_code=500,
            mimetype="application/json",
        )

    try:
        r = requests.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": SUPABASE_PUBLISHABLE_KEY,
            },
            timeout=10,
        )

        if r.status_code != 200:
            return func.HttpResponse(
                json.dumps(
                    {"ok": False, "error": "Supabase rejected token", "status": r.status_code, "body": r.text},
                    indent=2,
                ),
                status_code=401,
                mimetype="application/json",
            )

        user = r.json()
        return func.HttpResponse(
            json.dumps(
                {"ok": True, "user_id": user.get("id"), "email": user.get("email"), "role": user.get("role")},
                indent=2,
            ),
            status_code=200,
            mimetype="application/json",
        )

    except Exception as e:
        logging.exception("Token validation failed")
        return func.HttpResponse(
            json.dumps({"ok": False, "error": str(e)}, indent=2),
            status_code=500,
            mimetype="application/json",
        )
