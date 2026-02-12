import json
import logging
import os

import azure.functions as func

from auth import require_user, AuthError
from db import get_conn
from graph_mailer import send_booking_confirmed_email


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
    cancelled_by = body.get("cancelled_by")  # must be 'student' or 'mentor'

    if not booking_id or not cancelled_by:
        return func.HttpResponse(
            json.dumps({"ok": False, "error": "Required fields: booking_id, cancelled_by"}),
            status_code=400,
            mimetype="application/json",
        )

    if cancelled_by not in ("student", "mentor"):
        return func.HttpResponse(
            json.dumps({"ok": False, "error": "cancelled_by must be 'student' or 'mentor'"}),
            status_code=400,
            mimetype="application/json",
        )

    # We'll populate these for email after DB commit
    mentor_name = mentor_email = teams_url = None
    student_name = student_email = None
    start_time = None

    try:
        conn = get_conn()
        with conn.cursor() as cur:
            # Lock booking row and fetch identifiers we need
            cur.execute(
                """
                SELECT booking_id, slot_id, mentor_id, student_id, status
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

            _booking_id, slot_id, mentor_id, student_id, status = row

            # If already cancelled, return slot_id too (no resend)
            if status == "cancelled":
                conn.close()
                return func.HttpResponse(
                    json.dumps(
                        {"ok": True, "booking_id": str(_booking_id), "slot_id": str(slot_id), "status": "cancelled"}
                    ),
                    status_code=200,
                    mimetype="application/json",
                )

            # Cancel the booking
            cur.execute(
                """
                UPDATE bookings
                SET status = 'cancelled',
                    cancelled_at = NOW(),
                    cancelled_by = %s
                WHERE booking_id = %s
                RETURNING booking_id, slot_id, status, cancelled_at;
                """,
                (cancelled_by, booking_id),
            )
            updated = cur.fetchone()

            # Fetch mentor details (name/email/Teams)
            cur.execute(
                """
                SELECT m.display_name, au.email, m.teams_meeting_url
                FROM mentors m
                JOIN app_users au ON au.user_id = m.mentor_id
                WHERE m.mentor_id = %s
                """,
                (mentor_id,),
            )
            m = cur.fetchone()
            if m:
                mentor_name, mentor_email, teams_url = m[0], m[1], m[2]

            # Fetch student details (name/email)
            cur.execute(
                """
                SELECT s.display_name, au.email
                FROM students s
                JOIN app_users au ON au.user_id = s.student_id
                WHERE s.student_id = %s
                """,
                (student_id,),
            )
            s = cur.fetchone()
            if s:
                student_name, student_email = s[0], s[1]

            # Fetch slot start time
            cur.execute(
                """
                SELECT start_time
                FROM mentor_availability_slots
                WHERE slot_id = %s
                """,
                (slot_id,),
            )
            st = cur.fetchone()
            start_time = st[0] if st else None

        conn.commit()
        conn.close()

        # Send cancellation email (best-effort)
        email_status = "not_attempted"
        email_error = None

        if mentor_email and student_email and teams_url and start_time:
            try:
                logging.info(
                    "CANCEL_EMAIL_SEND_START booking_id=%s mentor_email=%s student_email=%s",
                    str(updated[0]),
                    mentor_email,
                    student_email,
                )

                send_booking_confirmed_email(
                    from_user=os.environ["M365_FROM_USER"],
                    to_emails=[student_email, mentor_email],
                    subject="DiveInSTEAM: Session cancelled",
                    body_text=(
                        f"Hi {student_name or 'Student'} and {mentor_name or 'Mentor'},\n\n"
                        f"The mentoring session has been cancelled.\n\n"
                        f"Cancelled by: {cancelled_by}\n"
                        f"When: {start_time.isoformat()}\n"
                        f"Teams link: {teams_url}\n\n"
                        f"You can rebook another time slot when ready.\n\n"
                        "Thanks,\nDiveInSTEAM\n"
                    ),
                )

                logging.info("CANCEL_EMAIL_SEND_DONE booking_id=%s", str(updated[0]))
                email_status = "sent"
            except Exception as e:
                email_status = "failed"
                email_error = str(e)
                logging.exception("CANCEL_EMAIL_SEND_FAILED booking_id=%s", str(updated[0]))
        else:
            email_status = "skipped_missing_data"
            email_error = (
                f"mentor_email={bool(mentor_email)} student_email={bool(student_email)} "
                f"teams_url={bool(teams_url)} start_time={bool(start_time)}"
            )
            logging.warning("CANCEL_EMAIL_SKIPPED booking_id=%s %s", str(updated[0]), email_error)

        return func.HttpResponse(
            json.dumps(
                {
                    "ok": True,
                    "booking_id": str(updated[0]),
                    "slot_id": str(updated[1]),
                    "status": updated[2],
                    "cancelled_at": updated[3].isoformat() if updated[3] else None,
                    "email_status": email_status,
                    "email_error": email_error,
                }
            ),
            status_code=200,
            mimetype="application/json",
        )

    except Exception as e:
        logging.exception("Cancel booking failed")
        return func.HttpResponse(
            json.dumps({"ok": False, "error": str(e)}),
            status_code=500,
            mimetype="application/json",
        )
