-- SYNTHETIC MOCK BANKING SYSTEM — fake legacy-table cleanup migration, not real.
-- Deliberately planted finding — see docs/mock_banking_planted_findings.md.

DROP TABLE legacy_ledger_snapshot;

CREATE TABLE ledger_snapshot (
    id INTEGER PRIMARY KEY,
    balance NUMERIC NOT NULL
);
