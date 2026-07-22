# SYNTHETIC TEST FIXTURE — fake customer onboarding/identity code, not real code.

CUSTOMER_RECORD_EXAMPLE = {
    "customer_email": "jane.fake.customer@example-fake-bank.test",
    "date_of_birth": "1990-01-01",
    "national_id_shaped": "123-45-6789",
    "account_number": "IBAN00FAKE0000000000",
}


def validate_kyc(customer):
    return customer.get("national_id_shaped") is not None
