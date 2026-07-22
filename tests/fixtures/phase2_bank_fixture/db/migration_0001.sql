-- SYNTHETIC TEST FIXTURE — fake SQL migration, not real.
DB_PASSWORD=fake_plaintext_pw_1

DROP TABLE legacy_accounts;

CREATE TABLE accounts (
    id INTEGER PRIMARY KEY,
    holder_name TEXT
);
