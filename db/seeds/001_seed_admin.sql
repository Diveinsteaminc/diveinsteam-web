INSERT INTO app_users (user_id, email, app_role)
--VALUES ('fe8ba493-bff0-49d9-8971-c28f762a73b8', 'admin@diveinsteam.org.au', 'admin'),
--VALUES ('e1b17b0e-4d04-4061-8f28-8e240d5a6c7c','foniakaunti+mentor@gmail.com','mentor')
VALUES ('ce305122-a541-4c88-93de-7701a7e956f8','foniakaunti+student@gmail.com','mentee')
ON CONFLICT (user_id) DO UPDATE
SET email = EXCLUDED.email,
    app_role = EXCLUDED.app_role,
    updated_at = now();
