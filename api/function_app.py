import base64, json
import requests
import azure.functions as func
import logging
import os

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
 # ok to keep in app settings later; for now hardcode for speed

app = func.FunctionApp()



@app.route(route="hello", auth_level=func.AuthLevel.ANONYMOUS)
def hello(req: func.HttpRequest) -> func.HttpResponse:
    auth = req.headers.get("authorization", "")

    if not auth.lower().startswith("bearer "):
        return func.HttpResponse(
            json.dumps(
                {
                    "ok": False,
                    "has_authorization_header": bool(auth),
                    "error": "No Bearer token received",
                },
                indent=2,
            ),
            status_code=401,
            mimetype="application/json",
        )

    token = auth.split(" ", 1)[1].strip()

    parts = token.split(".")
    if len(parts) != 3:
        return func.HttpResponse(
            json.dumps(
                {
                    "ok": False,
                    "error": "Authorization header is not a JWT",
                    "token_length": len(token),
                },
                indent=2,
            ),
            status_code=401,
            mimetype="application/json",
        )

    def b64url_decode(seg: str):
        padding = "=" * (-len(seg) % 4)
        return json.loads(
            base64.urlsafe_b64decode(seg + padding).decode("utf-8")
        )

    header = b64url_decode(parts[0])
    payload = b64url_decode(parts[1])

    return func.HttpResponse(
        json.dumps(
            {
                "ok": True,
                "token_length": len(token),
                "alg": header.get("alg"),
                "kid": header.get("kid"),
                "iss": payload.get("iss"),
                "aud": payload.get("aud"),
                "sub": payload.get("sub"),
            },
            indent=2,
        ),
        status_code=200,
        mimetype="application/json",
    )
