import json
import logging
from datetime import datetime
import azure.functions as func

from auth import require_user, AuthError
from db import get_conn

def handle(req: func.HttpRequest) -> func.HttpResponse:
    # Auth
    try:
        _user = require_user(req)
    except AuthError as e:
        return func.HttpResponse(
            json.dumps({"ok": False, "error": e.message}),
            status_code=e.status_code,
            mimetype="application/json",
        )

    mentor_id = req.params.get("mentor_id")
    from_ts = req.params.get("from")
    to_ts = req.params.get("to")

    if not mentor_id or not from_ts or not to_ts:
        return func.HttpResponse(
            json.dumps({"ok": False, "error": "Required params: mentor_id, from, to"}),
            status_code=400,
            mimetype="application/json",
        )

    try:
        from_dt = datetime.fromisoformat(from_ts.replace("Z", "+00:00"))
        to_dt = datetime.fromisoformat(to_ts.replace("Z", "+00:00"))
    except ValueError:
        return func.HttpResponse(
            json.dumps({"ok": False, "error": "Invalid datetime format"}),
            status_code=400,
            mimetype="application/json",
        )

    if to_dt <= from_dt:
        return func.HttpResponse(
            json.dumps({"ok": False, "error": "`to` must be after `from`"}),
            status_code=400,
            mimetype="application/json",
        )

    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    s.slot_id,
                    s.start_time,
                    s.end_time
                FROM mentor_availability_slots s
                LEFT JOIN bookings b
                  ON b.slot_id = s.slot_id
                 AND b.status IN ('requested', 'confirmed')
                WHERE s.mentor_id = %s
                  AND s.start_time >= %s
                  AND s.end_time <= %s
                  AND b.booking_id IS NULL
                ORDER BY s.start_time;
                """,
                (mentor_id, from_dt, to_dt),
            )
            rows = cur.fetchall()
        conn.close()

        slots = [
            {
                "slot_id": str(r[0]),
                "start_time": r[1].isoformat() if r[1] else None,
                "end_time": r[2].isoformat() if r[2] else None,
            }
            for r in rows
        ]

        return func.HttpResponse(
            json.dumps({"ok": True, "mentor_id": str(mentor_id), "count": len(slots), "slots": slots}),
            status_code=200,
            mimetype="application/json",
        )

    except Exception as e:
        logging.exception("Availability lookup failed")
        return func.HttpResponse(
            json.dumps({"ok": False, "error": str(e)}),
            status_code=500,
            mimetype="application/json",
        )
