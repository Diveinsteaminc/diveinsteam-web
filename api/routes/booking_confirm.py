import json
import logging
import azure.functions as func
import os

from graph_mailer import send_booking_confirmed_email
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

    # Parse JSON
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"ok": False, "error": "Invalid JSON body"}),
            status_code=400,
            mimetype="application/json",
        )

    booking_id = body.get("booking_id")
    if not booking_id:
        return func.HttpResponse(
            json.dumps({"ok": False, "error": "Required field: booking_id"}),
            status_code=400,
            mimetype="application/json",
        )

    try:
        conn = get_conn()
        with conn.cursor() as cur:
            # 1) Load booking (and lock it so two confirms can't race)
            cur.execute(
                """
                SELECT booking_id, mentor_id, student_id, status,note
                FROM bookings
                WHERE booking_id = %s
                FOR UPDATE;
                """,
                (booking_id,),
            )
            row = cur.fetchone()
            if not row:
                conn.close()
                return func.HttpResponse(
                    json.dumps({"ok": False, "error": "Booking not found"}),
                    status_code=404,
                    mimetype="application/json",
                )

            _booking_id, mentor_id, student_id, status , note= row

            if status == "confirmed":
                logging.info(
                    "CONFIRM_SKIPPED_ALREADY_CONFIRMED booking_id=%s",
                    str(_booking_id),
                )
                conn.close()
                return func.HttpResponse(
                    json.dumps({"ok": True, "booking_id": str(_booking_id), "status": "confirmed"}),
                    status_code=200,
                    mimetype="application/json",
                )

            if status != "requested":
                conn.close()
                return func.HttpResponse(
                    json.dumps({"ok": False, "error": f"Cannot confirm booking in status '{status}'"}),
                    status_code=409,
                    mimetype="application/json",
                )

            # 2) Fetch mentor Teams link
            cur.execute(
                """
                SELECT teams_meeting_url
                FROM mentors
                WHERE mentor_id = %s
                """,
                (mentor_id,),
            )
            m = cur.fetchone()
            teams_url = m[0] if m else None

            if not teams_url:
                conn.close()
                return func.HttpResponse(
                    json.dumps({"ok": False, "error": "Mentor Teams link missing"}),
                    status_code=409,
                    mimetype="application/json",
                )
            # Mentor name + email + Teams link (teams link already fetched, but we’ll fetch name/email too)
            cur.execute(
                """
                SELECT
                m.display_name,
                au.email,
                m.teams_meeting_url
                FROM mentors m
                JOIN app_users au ON au.user_id = m.mentor_id
                WHERE m.mentor_id = %s
                """,
                (mentor_id,),
            )
            m = cur.fetchone()
            if not m or not m[1] or not m[2]:
                conn.close()
                return func.HttpResponse(
                    json.dumps({"ok": False, "error": "Mentor profile incomplete (name/email/Teams link missing)"}),
                    status_code=409,
                    mimetype="application/json",
                )
            mentor_name, mentor_email, teams_url = m[0], m[1], m[2]
            
            # student details

            cur.execute(
                """
                SELECT
                s.display_name,
                au.email
                FROM students s
                JOIN app_users au ON au.user_id = s.student_id
                WHERE s.student_id = %s
                """,
                (student_id,),
            )
            s = cur.fetchone()
            if not s or not s[1]:
                conn.close()
                return func.HttpResponse(
                    json.dumps({"ok": False, "error": "Student profile incomplete (name/email missing)"}),
                    status_code=409,
                    mimetype="application/json",
                )
            student_name, student_email = s[0], s[1]



            # 3) Confirm booking + snapshot meeting link
            cur.execute(
                """
                UPDATE bookings
                SET status = 'confirmed',
                    confirmed_at = NOW(),
                    meeting_url_snapshot = %s
                WHERE booking_id = %s
                RETURNING booking_id, status, confirmed_at;
                """,
                (teams_url, booking_id),
            )
            updated = cur.fetchone()
            
            cur.execute(
                """
                SELECT s.start_time
                FROM bookings b
                JOIN mentor_availability_slots s ON s.slot_id = b.slot_id
                WHERE b.booking_id = %s
                """,
                (booking_id,),
            )
            start_time = cur.fetchone()[0]


        conn.commit()
        conn.close()
        logging.info(
            "EMAIL_SEND_START booking_id=%s mentor_email=%s student_email=%s",
            str(updated[0]),
            mentor_email,
            student_email,
        )
        send_booking_confirmed_email(
            from_user=os.environ["M365_FROM_USER"],
            to_emails=[student_email, mentor_email],
            subject="DiveInSTEAM: Session confirmed",
            body_text=(
                f"Hi {student_name} and {mentor_name},\n\n"
                f"Your mentoring session is confirmed.\n\n"
                f"When: {start_time.isoformat()}\n"
                f"Teams link: {teams_url}\n"
                + (f"\nStudent note: {note}\n" if note else "")
                + "\nThanks,\nDiveInSTEAM\n"
            ),
        )
        logging.info("EMAIL_SEND_DONE booking_id=%s", str(updated[0]))
        return func.HttpResponse(
            json.dumps(
                {
                    "ok": True,
                    "booking_id": str(updated[0]),
                    "status": updated[1],
                    "confirmed_at": updated[2].isoformat() if updated[2] else None,
                }
            ),
            status_code=200,
            mimetype="application/json",
        )

    except Exception as e:
        logging.exception("Confirm booking failed")
        return func.HttpResponse(
            json.dumps({"ok": False, "error": str(e)}),
            status_code=500,
            mimetype="application/json",
        )
