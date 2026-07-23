-- SYNTHETIC MOCK BANKING SYSTEM — fake schema migration, not real.
-- Deliberate NEGATIVE example: no destructive statement, no plaintext credential.
-- Expect: no findings from this file.

CREATE TABLE accounts (
    id INTEGER PRIMARY KEY,
    holder_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE portfolios (
    id INTEGER PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES accounts(id),
    value NUMERIC NOT NULL DEFAULT 0
);
