# SYNTHETIC TEST FIXTURE — fake logging code, not real.
import logging

logger = logging.getLogger("fake_bank")


def log_login_attempt(username, password):
    logger.info(f"login attempt username={username} password={password}")
