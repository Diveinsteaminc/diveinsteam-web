import json
import logging
import azure.functions as func
import psycopg
import uuid

from auth import require_user, AuthError
from db import get_conn


def create(req: func.HttpRequest) -> func.HttpResponse:
    # Auth
    try:
        _user = require_user(req)
    except AuthError as e:
        return func.HttpResponse(
            json.dumps({"ok": False, "error": e.message}),
            status_code=e.status_code,
            mimetype="application/json",
        )

    # Parse JSON
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"ok": False, "error": "Invalid JSON body"}),
            status_code=400,
            mimetype="application/json",
        )

    slot_id = body.get("slot_id")
    student_id = body.get("student_id")
    note = body.get("note")

    if not slot_id or not student_id:
        return func.HttpResponse(
            json.dumps({"ok": False, "error": "Required fields: slot_id, student_id"}),
            status_code=400,
            mimetype="application/json",
        )

    try:
        conn = get_conn()
        with conn.cursor() as cur:
            # 1) Ensure slot exists + get mentor_id
            cur.execute(
                """
                SELECT mentor_id
                FROM mentor_availability_slots
                WHERE slot_id = %s
                """,
                (slot_id,),
            )
            row = cur.fetchone()
            if not row:
                conn.close()
                return func.HttpResponse(
                    json.dumps({"ok": False, "error": "Slot not found"}),
                    status_code=404,
                    mimetype="application/json",
                )

            mentor_id = row[0]

            # 2) Insert booking request
            # Expectation: bookings.slot_id is UNIQUE to prevent double-booking.
            booking_id = uuid.uuid4()

            cur.execute(
                """
                INSERT INTO bookings (booking_id, slot_id, mentor_id, student_id, status, note)
                VALUES (%s, %s, %s, %s, 'requested', %s)
                RETURNING booking_id, status;

                """,
                (booking_id,slot_id, mentor_id, student_id, note),
            )
            booking_id, status = cur.fetchone()

        conn.commit()
        conn.close()

        return func.HttpResponse(
            json.dumps({"ok": True, "booking_id": str(booking_id), "status": status}),
            status_code=201,
            mimetype="application/json",
        )

    except psycopg.errors.UniqueViolation:
        # slot already has a booking (or booking_id collision, depending on constraints)
        return func.HttpResponse(
            json.dumps({"ok": False, "error": "Slot already has a booking"}),
            status_code=409,
            mimetype="application/json",
        )
    except Exception as e:
        logging.exception("Create booking failed")
        return func.HttpResponse(
            json.dumps({"ok": False, "error": str(e)}),
            status_code=500,
            mimetype="application/json",
        )
