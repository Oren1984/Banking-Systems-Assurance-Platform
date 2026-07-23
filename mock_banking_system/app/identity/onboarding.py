# SYNTHETIC MOCK BANKING SYSTEM — fake customer onboarding/identity record, not real code.
# Deliberately planted findings — see docs/mock_banking_planted_findings.md.

customer_email = "jane.demo.customer@example-mock-bank.test"  # expect PII-EMAIL
date_of_birth = "1990-01-01"  # expect PII-DATE_OF_BIRTH
national_id_shaped = "123-45-6789"  # expect PII-NATIONAL_ID_SHAPED
account_number = "AB1234567890"  # expect PII-ACCOUNT_NUMBER_FIELD


def validate_kyc(national_id):
    return national_id is not None
