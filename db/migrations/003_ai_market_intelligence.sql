-- Zerqen AI market intelligence runtime state
-- Safe upgrade: all additions are idempotent.

ALTER TABLE zerqen_paper_state
    ADD COLUMN IF NOT EXISTS ai_mode TEXT NOT NULL DEFAULT 'auto';

ALTER TABLE zerqen_paper_state
    ADD COLUMN IF NOT EXISTS ai_degraded_until TIMESTAMPTZ;

ALTER TABLE zerqen_paper_state
    ADD COLUMN IF NOT EXISTS ai_last_ok_at TIMESTAMPTZ;

ALTER TABLE zerqen_paper_state
    ADD COLUMN IF NOT EXISTS ai_last_error TEXT;

ALTER TABLE zerqen_paper_state
    ADD COLUMN IF NOT EXISTS ai_last_model TEXT;

ALTER TABLE zerqen_paper_state
    ADD COLUMN IF NOT EXISTS ai_last_confidence NUMERIC;

ALTER TABLE zerqen_paper_state
    ADD COLUMN IF NOT EXISTS ai_safe_mode_entries INTEGER NOT NULL DEFAULT 0;

ALTER TABLE zerqen_paper_state
    ADD COLUMN IF NOT EXISTS ai_report_hash TEXT;
