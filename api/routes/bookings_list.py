import json
import logging
from datetime import datetime, timezone

import azure.functions as func

from auth import require_user, AuthError
from db import get_conn


def _parse_limit(req: func.HttpRequest, default: int = 50, max_limit: int = 200) -> int:
    raw = req.params.get("limit", "")
    if not raw:
        return default
    try:
        n = int(raw)
        if n < 1:
            return default
        return min(n, max_limit)
    except ValueError:
        return default


def handle(req: func.HttpRequest) -> func.HttpResponse:
    # Auth
    try:
        user = require_user(req)
    except AuthError as e:
        return func.HttpResponse(
            json.dumps({"ok": False, "error": e.message}),
            status_code=e.status_code,
            mimetype="application/json",
        )

    role = (req.params.get("role") or "").strip().lower()  # "mentor" or "student"
    status = (req.params.get("status") or "").strip().lower()  # optional: requested/confirmed/cancelled
    limit = _parse_limit(req)

    if role not in ("mentor", "student"):
        return func.HttpResponse(
            json.dumps({"ok": False, "error": "Query param 'role' must be 'mentor' or 'student'"}),
            status_code=400,
            mimetype="application/json",
        )

    if status and status not in ("requested", "confirmed", "cancelled"):
        return func.HttpResponse(
            json.dumps({"ok": False, "error": "Query param 'status' must be requested|confirmed|cancelled"}),
            status_code=400,
            mimetype="application/json",
        )

    # In our model: mentors.mentor_id == app_users.user_id and students.student_id == app_users.user_id
    user_id = user["user_id"]

    try:
        conn = get_conn()
        with conn.cursor() as cur:
            where = []
            params = []

            if role == "mentor":
                where.append("b.mentor_id = %s")
                params.append(user_id)
            else:
                where.append("b.student_id = %s")
                params.append(user_id)

            if status:
                where.append("b.status = %s")
                params.append(status)

            # List newest first; you can later switch to slot time ordering
            sql = f"""
                SELECT
                    b.booking_id,
                    b.slot_id,
                    b.mentor_id,
                    b.student_id,
                    b.status,
                    b.note,
                    b.created_at,
                    b.confirmed_at,
                    b.cancelled_at,
                    b.cancelled_by,
                    s.start_time,
                    s.end_time,
                    m.display_name AS mentor_name,
                    au_m.email     AS mentor_email,
                    m.teams_meeting_url,
                    st.display_name AS student_name,
                    au_s.email      AS student_email
                FROM bookings b
                JOIN mentor_availability_slots s ON s.slot_id = b.slot_id
                LEFT JOIN mentors m ON m.mentor_id = b.mentor_id
                LEFT JOIN app_users au_m ON au_m.user_id = b.mentor_id
                LEFT JOIN students st ON st.student_id = b.student_id
                LEFT JOIN app_users au_s ON au_s.user_id = b.student_id
                WHERE {" AND ".join(where)}
                ORDER BY b.created_at DESC
                LIMIT %s;
            """
            params.append(limit)

            cur.execute(sql, tuple(params))
            rows = cur.fetchall()

        conn.close()

        # Build response objects
        items = []
        for r in rows:
            (
                booking_id,
                slot_id,
                mentor_id,
                student_id,
                b_status,
                note,
                created_at,
                confirmed_at,
                cancelled_at,
                cancelled_by,
                start_time,
                end_time,
                mentor_name,
                mentor_email,
                teams_url,
                student_name,
                student_email,
            ) = r

            items.append(
                {
                    "booking_id": str(booking_id),
                    "slot_id": str(slot_id),
                    "status": b_status,
                    "note": note,
                    "created_at": created_at.isoformat() if created_at else None,
                    "confirmed_at": confirmed_at.isoformat() if confirmed_at else None,
                    "cancelled_at": cancelled_at.isoformat() if cancelled_at else None,
                    "cancelled_by": cancelled_by,
                    "slot": {
                        "start_time": start_time.isoformat() if start_time else None,
                        "end_time": end_time.isoformat() if end_time else None,
                    },
                    "mentor": {
                        "mentor_id": str(mentor_id) if mentor_id else None,
                        "name": mentor_name,
                        "email": mentor_email,
                        "teams_meeting_url": teams_url,
                    },
                    "student": {
                        "student_id": str(student_id) if student_id else None,
                        "name": student_name,
                        "email": student_email,
                    },
                }
            )

        return func.HttpResponse(
            json.dumps(
                {
                    "ok": True,
                    "role": role,
                    "user_id": user_id,
                    "count": len(items),
                    "items": items,
                }
            ),
            status_code=200,
            mimetype="application/json",
        )

    except Exception as e:
        logging.exception("Bookings list failed")
        return func.HttpResponse(
            json.dumps({"ok": False, "error": str(e)}),
            status_code=500,
            mimetype="application/json",
        )
