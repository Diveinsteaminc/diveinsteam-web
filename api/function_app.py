import azure.functions as func
import datetime
import json
import logging
import os
import requests
import jwt
from jwt import PyJWKClient

SUPABASE_URL = "https://cekzzpatfrnzoymkwfun.supabase.co"
SUPABASE_JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
SUPABASE_ISSUER = f"{SUPABASE_URL}/auth/v1"

app = func.FunctionApp()

@app.route(route="hello", auth_level=func.AuthLevel.ANONYMOUS)
def hello(req: func.HttpRequest) -> func.HttpResponse:
    auth = req.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return func.HttpResponse(
            json.dumps({"error": "Missing Bearer token"}),
            status_code=401,
            mimetype="application/json",
        )

    token = auth.split(" ", 1)[1].strip()

    try:
        jwk_client = PyJWKClient(SUPABASE_JWKS_URL)
        signing_key = jwk_client.get_signing_key_from_jwt(token).key

        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["ES256"],
            issuer=SUPABASE_ISSUER,
            audience="authenticated",
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )

        # Minimal “authorised” response (don’t echo full token)
        return func.HttpResponse(
            json.dumps(
                {
                    "ok": True,
                    "user_id": claims.get("sub"),
                    "email": claims.get("email"),
                    "aud": claims.get("aud"),
                    "iss": claims.get("iss"),
                    "exp": claims.get("exp"),
                },
                indent=2,
            ),
            status_code=200,
            mimetype="application/json",
        )

    except Exception as e:
        return func.HttpResponse(
            json.dumps({"ok": False, "error": str(e)}),
            status_code=401,
            mimetype="application/json",
        )
