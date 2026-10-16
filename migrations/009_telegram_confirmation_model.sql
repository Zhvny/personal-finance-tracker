-- 009: Telegram NL input & confirmation model (Phase 3)
--
-- Persistent confirmation store replacing the in-memory PENDING_RECEIPTS dict
-- in packages/api/telegram_bot.py / telegram_poll.py, plus per-chat profile
-- bindings (single-user-per-chat model, no login flow).
--
--   1. public.chat_bindings          - chat_id -> profile mapping (per-chat auth)
--   2. public.pending_confirmations  - draft -> confirm/cancel lifecycle
--
-- Confirmation lifecycle:
--   pending   -> created by draft ingestion (photo OCR or NL text parse)
--   confirmed -> one-time token consumption commits the draft into the profile
--                ledger via ledger_engine.record_transaction (idempotency_key =
--                token_hash, making replay safe)
--   cancelled -> user explicitly discarded the draft
--   expired   -> sweep marks drafts whose expires_at (created_at + 24h) passed
--
-- These tables are GLOBAL (not per-profile) because a chat may produce
-- confirmations while any profile is active; the profile column records which
-- profile ledger the draft must be committed into.

CREATE TABLE IF NOT EXISTS public.chat_bindings (
    id            BIGSERIAL PRIMARY KEY,
    chat_id       BIGINT UNIQUE NOT NULL,
    profile       VARCHAR(100) NOT NULL,
    display_name  VARCHAR(255),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_bindings_profile ON public.chat_bindings(profile);

CREATE TABLE IF NOT EXISTS public.pending_confirmations (
    id              BIGSERIAL PRIMARY KEY,
    chat_id         BIGINT NOT NULL,
    profile         VARCHAR(100) NOT NULL,
    token_hash      VARCHAR(64) UNIQUE NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'confirmed', 'cancelled', 'expired')),
    draft_json      JSONB NOT NULL,
    edit_target     VARCHAR(40),
    message_id      BIGINT,
    idempotency_key VARCHAR(120) UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    consumed_at     TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pending_confirmations_chat_status
    ON public.pending_confirmations(chat_id, status);
CREATE INDEX IF NOT EXISTS idx_pending_confirmations_status_expires
    ON public.pending_confirmations(status, expires_at);
