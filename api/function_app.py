import os
import json
import logging
import requests
import azure.functions as func
import psycopg
from datetime import datetime


from auth import require_user, AuthError
from db import get_conn
from graph_mailer import send_booking_confirmed_email


from routes.availability import handle as availability_handle
from routes.bookings import create as bookings_create
from routes.booking_confirm import handle as booking_confirm_handle
from routes.booking_cancel import handle as booking_cancel_handle
from routes.bookings_list import handle as bookings_list_handle





SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_PUBLISHABLE_KEY = os.environ.get("SUPABASE_ANON_KEY", "")  # publishable/anon key

IS_LOCAL = os.environ.get("AZURE_FUNCTIONS_ENVIRONMENT") == "Development"


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



@app.route(route="db-ping", auth_level=func.AuthLevel.ANONYMOUS)
def db_ping(req: func.HttpRequest) -> func.HttpResponse:
    try:
        conn = psycopg.connect(
            host=os.environ["PGHOST"],
            user=os.environ["PGUSER"],
            password=os.environ["PGPASSWORD"],
            dbname=os.environ["PGDATABASE"],
            port=int(os.environ.get("PGPORT", 5432)),
            sslmode="require",
            connect_timeout=5,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        conn.close()

        return func.HttpResponse(
            json.dumps({"ok": True, "db": "reachable"}, indent=2),
            status_code=200,
            mimetype="application/json",
        )

    except Exception as e:
        return func.HttpResponse(
            json.dumps({"ok": False, "error": str(e)}, indent=2),
            status_code=500,
            mimetype="application/json",
        )


@app.route(route="me", auth_level=func.AuthLevel.ANONYMOUS)
def me(req: func.HttpRequest) -> func.HttpResponse:
    token = req.headers.get("x-supabase-token", "")
    if not token:
        return func.HttpResponse(
            json.dumps({"ok": False, "error": "Missing X-Supabase-Token"}, indent=2),
            status_code=401,
            mimetype="application/json",
        )

    # Step 1: validate token with Supabase
    
    try:
       user_ctx = require_user(req)
       user_id = user_ctx["user_id"]
       email = user_ctx["email"]
    except AuthError as e:
         return func.HttpResponse(
            json.dumps({"ok": False, "error": e.message}, indent=2),
            status_code=e.status_code,
            mimetype="application/json",
    )


    # Step 2: fetch app role from Postgres
    try:
        conn = psycopg.connect(
            host=os.environ["PGHOST"],
            user=os.environ["PGUSER"],
            password=os.environ["PGPASSWORD"],
            dbname=os.environ["PGDATABASE"],
            port=int(os.environ.get("PGPORT", 5432)),
            sslmode="require",
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT app_role, status
                FROM app_users
                WHERE user_id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
        conn.close()

        if not row:
            return func.HttpResponse(
                json.dumps(
                    {
                        "ok": False,
                        "error": "User not registered in app",
                        "user_id": user_id,
                    },
                    indent=2,
                ),
                status_code=403,
                mimetype="application/json",
            )

        app_role, status = row

        return func.HttpResponse(
            json.dumps(
                {
                    "ok": True,
                    "user_id": user_id,
                    "email": email,
                    "app_role": app_role,
                    "status": status,
                },
                indent=2,
            ),
            status_code=200,
            mimetype="application/json",
        )

    except Exception as e:
        return func.HttpResponse(
            json.dumps({"ok": False, "error": str(e)}, indent=2),
            status_code=500,
            mimetype="application/json",
        )
    


# Availability endpoint

@app.route(route="availability", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_availability(req: func.HttpRequest) -> func.HttpResponse:
    return availability_handle(req)
  
#Booking endpoint

@app.route(route="bookings", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def create_booking(req: func.HttpRequest) -> func.HttpResponse:
    return bookings_create(req)

@app.route(route="bookings/confirm", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def confirm_booking(req: func.HttpRequest) -> func.HttpResponse:
    return booking_confirm_handle(req)

@app.route(route="bookings/cancel", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def cancel_booking(req: func.HttpRequest) -> func.HttpResponse:
    return booking_cancel_handle(req)

@app.route(route="bookings", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def list_bookings(req: func.HttpRequest) -> func.HttpResponse:
    return bookings_list_handle(req)


@app.route(route="email-test", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def email_test(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            '{"ok": false, "error": "Invalid JSON"}',
            status_code=400,
            mimetype="application/json",
        )

    to_email = body.get("to")
    if not to_email:
        return func.HttpResponse(
            '{"ok": false, "error": "Required field: to"}',
            status_code=400,
            mimetype="application/json",
        )

    try:
        send_booking_confirmed_email(
            from_user=os.environ["M365_FROM_USER"],
            to_emails=[to_email],
            subject="DiveInSTEAM Graph Email Test",
            body_text="This is a test email sent via Microsoft Graph.",
        )
        return func.HttpResponse(
            '{"ok": true}',
            status_code=200,
            mimetype="application/json",
        )
    except Exception as e:
        return func.HttpResponse(
            f'{{"ok": false, "error": "{str(e)}"}}',
            status_code=500,
            mimetype="application/json",
        )
