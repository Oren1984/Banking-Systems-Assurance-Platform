# SYNTHETIC MOCK BANKING SYSTEM — fake authentication/login handler, not real code.
# Deliberate NEGATIVE example: no hardcoded credentials, delegates to a password hasher.
# Expect: no findings from this file.


def authenticate(username, password_hash_input, hasher):
    stored_hash = hasher.lookup(username)
    return hasher.verify(password_hash_input, stored_hash)
