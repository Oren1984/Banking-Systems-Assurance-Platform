# SYNTHETIC TEST DATA — NOT A REAL BANKING SYSTEM

Every file under `tests/fixtures/phase2_bank_fixture/` is fake, synthetic test data created
solely to exercise Phase 2 scanners (`scanners/rules/*.py`) and the domain mapper
(`scanners/domain_mapper.py`) in `tests/integration/test_full_scan_fixture.py`.

- No real customer, account, card, credential, or identity data appears anywhere in this
  directory.
- Every "secret," "password," and "API key" below is a fake placeholder value, deliberately
  shaped to match a detection pattern — never a real credential.
- Some files deliberately model *good* practice (e.g. `loan_approval.py`'s `approve_loan`
  does call an audit function) to give the scanners a true-negative case, not just
  true-positives.

Do not treat anything in this directory as real, and do not add real data to it.
