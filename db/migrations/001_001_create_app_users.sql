CREATE TABLE IF NOT EXISTS app_users (
  user_id uuid PRIMARY KEY,
  email text UNIQUE,
  app_role text NOT NULL CHECK (app_role IN ('admin','mentor','mentee')),
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

--SELECT * FROM app_users;

UPDATE app_users
SET app_role = 'mentor',
    status = 'active'
WHERE email = 'mentor@example.com';

VALUES (
  ('e1b17b0e-4d04-4061-8f28-8e240d5a6c7c','ce305122-a541-4c88-93de-7701a7e956f8'),
  ('foniakaunti+mentor@gmail.com','foniakaunti+student@gmail.com'),
  ('mentor','mentee')
)
ON CONFLICT (user_id) DO NOTHING;