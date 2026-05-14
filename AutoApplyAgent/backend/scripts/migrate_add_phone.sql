-- Migration: add phone column to users table
-- Run this once on your Neon PostgreSQL database
-- Needed for WhatsApp digest notifications (Pro/Power tier)

ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR;

-- Verify
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'users' AND column_name = 'phone';
