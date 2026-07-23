# SYNTHETIC MOCK BANKING SYSTEM — fake application logging setup, not real.
# Deliberately planted finding — see docs/mock_banking_planted_findings.md.
import logging

logger = logging.getLogger("mock_bank")


def log_login_attempt(username, password):
    logger.info(f"login attempt username={username} password={password}")
    # expect LOG-001 (HIGH — logging call mentions 'password')
