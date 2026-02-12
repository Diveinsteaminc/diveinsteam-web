--Seeding profile and booking tables for testing

--Sanity check:make sure there is mentor and student roles

/*SELECT user_id, email, app_role
FROM app_users
ORDER BY created_at;
*/

-- Seed mentor profile

INSERT INTO mentors (
  mentor_id,
  display_name,
  teams_meeting_url,
  timezone
)
VALUES (
  'e1b17b0e-4d04-4061-8f28-8e240d5a6c7c',
  'Jane Mentor',
  'https://teams.microsoft.com/l/meetup-join/REPLACE_WITH_REAL_LINK',
  'Australia/Brisbane'
)
ON CONFLICT (mentor_id) DO NOTHING;


-- Seed student profile

INSERT INTO students (
  student_id,
  display_name,
  grade,
  timezone
)
VALUES (
  'ce305122-a541-4c88-93de-7701a7e956f8',
  'Alex Student',
  10,
  'Australia/Brisbane'
)
ON CONFLICT (student_id) DO NOTHING;


-- seed Assign mentor ↔ student (active)

INSERT INTO mentor_assignments (
  mentor_id,
  student_id,
  status
)
VALUES (
  'e1b17b0e-4d04-4061-8f28-8e240d5a6c7c',
  'ce305122-a541-4c88-93de-7701a7e956f8',
  'active'
)
ON CONFLICT (mentor_id, student_id) DO NOTHING;

--seed mentor availability slots

INSERT INTO mentor_availability_slots (
  slot_id,
  mentor_id,
  start_time,
  end_time,
  status
)
VALUES
(
  '11111111-1111-1111-1111-111111111111',
  'e1b17b0e-4d04-4061-8f28-8e240d5a6c7c',
  '2026-02-12 16:00:00+10',
  '2026-02-12 16:30:00+10',
  'available'
),
(
  '22222222-2222-2222-2222-222222222222',
  'e1b17b0e-4d04-4061-8f28-8e240d5a6c7c',
  '2026-02-13 16:00:00+10',
  '2026-02-13 16:30:00+10',
  'available'
)
ON CONFLICT (slot_id) DO NOTHING;


--Seed a booking request (student books a slot)

INSERT INTO bookings (
  booking_id,
  slot_id,
  mentor_id,
  student_id,
  status,
  note
)
VALUES (
  '33333333-3333-3333-3333-333333333333',
  '11111111-1111-1111-1111-111111111111',
  'e1b17b0e-4d04-4061-8f28-8e240d5a6c7c',
  'ce305122-a541-4c88-93de-7701a7e956f8',
  'requested',
  'Would like help with algebra this week'
)
ON CONFLICT (booking_id) DO NOTHING;


--add constraits to booking id

ALTER TABLE bookings
ADD CONSTRAINT bookings_slot_id_unique UNIQUE (slot_id);

--seed Optional) Simulate mentor confirmation

UPDATE bookings
SET
  status = 'confirmed',
  confirmed_at = now(),
  meeting_url_snapshot = (
    SELECT teams_meeting_url
    FROM mentors
    WHERE mentor_id = 'e1b17b0e-4d04-4061-8f28-8e240d5a6c7c'
  )
WHERE booking_id = '33333333-3333-3333-3333-333333333333';


-- Mark slot as booked

UPDATE mentor_availability_slots
SET status = 'booked'
WHERE slot_id = '11111111-1111-1111-1111-111111111111';


-- Sanity checks

--Student upcoming sessions

SELECT b.booking_id, b.status, s.start_time, b.meeting_url_snapshot
FROM bookings b
JOIN mentor_availability_slots s ON s.slot_id = b.slot_id
WHERE b.student_id = 'ce305122-a541-4c88-93de-7701a7e956f8';

-- Mentor pending requests

SELECT b.booking_id, b.status, b.note, s.start_time
FROM bookings b
JOIN mentor_availability_slots s ON s.slot_id = b.slot_id
WHERE b.mentor_id = 'e1b17b0e-4d04-4061-8f28-8e240d5a6c7c'
ORDER BY b.requested_at DESC;

